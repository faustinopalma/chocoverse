#Requires -Version 7.4
[CmdletBinding()]
param([switch]$WriteProbe)

. "$PSScriptRoot\common.ps1"
Initialize-DemoContext
$assignment = Get-DemoStorageNetworkAssignment
$token = Invoke-AzJson -Arguments @('account', 'get-access-token', '--resource', 'https://storage.azure.com/')
$headers = @{
    Authorization = "Bearer $($token.accessToken)"
    'x-ms-version' = '2023-11-03'
    'x-ms-date' = [DateTime]::UtcNow.ToString('R')
}
$probe = '{"project":"giandoria","classification":"synthetic","purpose":"public-endpoint-policy-experiment"}'
$results = @()

function Invoke-StorageProbe {
    param(
        [Parameter(Mandatory)][string]$Uri,
        [ValidateSet('GET', 'PUT')][string]$Method = 'GET',
        [hashtable]$ExtraHeaders = @{},
        [string]$Body
    )
    $requestHeaders = $headers.Clone()
    foreach ($key in $ExtraHeaders.Keys) { $requestHeaders[$key] = $ExtraHeaders[$key] }
    for ($attempt = 0; $attempt -lt 15; $attempt++) {
        $request = @{
            Method = $Method; Uri = $Uri; Headers = $requestHeaders; SkipHttpErrorCheck = $true
        }
        if ($PSBoundParameters.ContainsKey('Body')) {
            $request.Body = [Text.Encoding]::UTF8.GetBytes($Body)
            $request.ContentType = 'application/json'
        }
        $response = Invoke-RecordedWebRequest @request
        if ($response.StatusCode -eq 403 -and
            $response.Content -match 'AuthorizationPermissionMismatch' -and $attempt -lt 14) {
            Write-Warning 'Storage data role is not propagated yet; retrying in 20 seconds.'
            Start-Sleep -Seconds 20
            continue
        }
        return $response
    }
}

foreach ($target in Get-DemoStorageTargets) {
    $account = Get-DemoStorage $target
    $waiver = Assert-DemoStorageExemption -Account $account -AssignmentId $assignment.id
    $p = $account.properties
    if ($p.publicNetworkAccess -ne 'Enabled' -or $p.allowSharedKeyAccess -ne $false -or
        $p.allowBlobPublicAccess -ne $false -or $p.supportsHttpsTrafficOnly -ne $true -or
        $p.networkAcls.defaultAction -ne 'Allow') {
        throw "$($target.Name): Storage settings have changed. No automatic repair will be performed."
    }
    $container = if ($target.Group -eq 'rg-giandoria-core-demo') { 'lab-state' } else { 'exports-demo' }
    $blobUri = "https://$($target.Name).blob.core.windows.net/$container/policy-probe.json"
    if ($WriteProbe) {
        $put = Invoke-StorageProbe -Uri $blobUri -Method PUT -Body $probe -ExtraHeaders @{
            'x-ms-blob-type' = 'BlockBlob'; 'If-None-Match' = '*'
        }
        $alreadyExists = $put.StatusCode -eq 409 -and $put.Content -cmatch '<Code>BlobAlreadyExists</Code>'
        if ([int]$put.StatusCode -notin @(201, 412) -and -not $alreadyExists) {
            throw "Probe creation failed ($([int]$put.StatusCode)): $($put.Content)"
        }
    }
    $get = Invoke-StorageProbe -Uri $blobUri
    if ($get.StatusCode -ne 200 -or $get.Content -cne $probe) {
        throw "$($target.Name): authenticated public Blob probe failed or content differs."
    }
    $anonymous = Invoke-RecordedWebRequest -Uri $blobUri -SkipHttpErrorCheck
    if (-not (Test-DemoAnonymousBlobDenial -StatusCode ([int]$anonymous.StatusCode) -Content $anonymous.Content)) {
        throw "Anonymous Blob access did not return an expected access-denial response ($([int]$anonymous.StatusCode))."
    }
    $tableStatus = $null
    $queueStatus = $null
    if ($target.Group -eq 'rg-giandoria-core-demo') {
        $tableUri = "https://$($target.Name).table.core.windows.net/runs()" + '?$top=1'
        $table = Invoke-StorageProbe -Uri $tableUri -ExtraHeaders @{ Accept = 'application/json;odata=nometadata' }
        $queue = Invoke-StorageProbe -Uri "https://$($target.Name).queue.core.windows.net/lab-requests?comp=metadata"
        if ($table.StatusCode -ne 200 -or $queue.StatusCode -ne 200) {
            throw "Authenticated Table/Queue access failed: $($table.StatusCode)/$($queue.StatusCode)."
        }
        $tableStatus = [int]$table.StatusCode
        $queueStatus = [int]$queue.StatusCode
    }
    $results += [pscustomobject]@{
        Account = $target.Name
        ResourceGroup = $target.Group
        Exemption = $waiver.name
        PolicyReference = 'StorageAccountPublicNetworkModify'
        Category = $waiver.properties.exemptionCategory
        ExpiresOn = Get-Value $waiver 'properties.expiresOn'
        PublicNetworkAccess = $p.publicNetworkAccess
        SharedKeyAccess = $p.allowSharedKeyAccess
        AnonymousBlobAccess = $p.allowBlobPublicAccess
        AuthenticatedBlobStatus = [int]$get.StatusCode
        AnonymousBlobStatus = [int]$anonymous.StatusCode
        AnonymousBlobReason = if ($anonymous.StatusCode -eq 409) { 'PublicAccessNotPermitted' } else { 'Unauthorized' }
        AuthenticatedTableStatus = $tableStatus
        AuthenticatedQueueStatus = $queueStatus
    }
}
$report = [pscustomobject]@{
    CheckedAt = [DateTimeOffset]::UtcNow.ToString('o')
    Mode = if ($WriteProbe) { 'CreateSyntheticProbeAndVerify' } else { 'ReadOnly' }
    Results = $results
    GovernancePersistence = 'Observed now only; no automatic exemption repair or renewal.'
}
Write-JsonFile -InputObject $report -Path (Join-Path $script:DemoLocal 'demo-public-access-check.json')
$report | ConvertTo-Json -Depth 7
