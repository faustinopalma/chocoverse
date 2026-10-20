#Requires -Version 7.4
[CmdletBinding()]
param(
    [ValidateSet('Validate', 'Foundation', 'Exemptions', 'Public', 'Fabric')]
    [string]$Stage = 'Validate'
)

. "$PSScriptRoot\common.ps1"
Initialize-DemoContext
$operator = Invoke-AzJson -Arguments @('ad', 'signed-in-user', 'show')
$main = Join-Path $PSScriptRoot 'main.bicep'
$parameters = @("operatorPrincipalId=$($operator.id)", 'storagePublicNetworkAccess=Disabled')

if ($Stage -eq 'Validate') {
    foreach ($file in @('main', 'storage-exemption', 'fabric')) {
        Invoke-Az -Arguments @('bicep', 'build', '--file', (Join-Path $PSScriptRoot "$file.bicep"),
            '--outfile', (Join-Path $script:DemoLocal "demo-$file.json"))
    }
    $validation = Invoke-AzJson -Arguments (@('deployment', 'sub', 'validate',
        '--location', 'swedencentral', '--template-file', $main, '--parameters') + $parameters)
    if ((Get-Value $validation 'properties.provisioningState') -notin @('Succeeded', 'Accepted')) {
        throw 'ARM did not report successful foundation validation.'
    }
    Invoke-Az -Arguments (@('deployment', 'sub', 'what-if', '--location', 'swedencentral',
        '--template-file', $main, '--parameters') + $parameters + @('--no-pretty-print', '--only-show-errors'))
    return
}

if ($Stage -eq 'Foundation') {
    $groups = @(Invoke-AzJson -Arguments @('group', 'list'))
    foreach ($existingGroup in $groups | Where-Object {
        $_.name -in @('rg-giandoria-core-demo', 'rg-giandoria-ops-demo', 'rg-giandoria-fabric-demo')
    }) {
        Assert-DemoOwnership $existingGroup
    }
    $resources = @(Invoke-AzJson -Arguments @('resource', 'list'))
    foreach ($resource in $resources | Where-Object {
        $_.resourceGroup -in @('rg-giandoria-core-demo', 'rg-giandoria-ops-demo', 'rg-giandoria-fabric-demo')
    }) {
        Assert-DemoOwnership $resource
        if ($resource.type -eq 'Microsoft.Storage/storageAccounts') {
            $current = Invoke-AzJson -Arguments @('storage', 'account', 'show', '--ids', $resource.id)
            if ($current.publicNetworkAccess -eq 'Enabled') {
                throw 'Foundation would disable an already-public account. Use the Public stage for redeployment.'
            }
        }
    }
    $result = Invoke-AzJson -Arguments (@('deployment', 'sub', 'create', '--name', 'giandoria-demo-foundation',
        '--location', 'swedencentral', '--template-file', $main, '--parameters') + $parameters)
    Write-JsonFile -InputObject $result -Path (Join-Path $script:DemoLocal 'demo-foundation-deployment.json')
    Write-Host 'Foundation deployed. Storage remains public-network disabled until explicitly exempted.'
    return
}

if ($Stage -in @('Exemptions', 'Public')) {
    $assignment = Get-DemoStorageNetworkAssignment
    $targets = Get-DemoStorageTargets
    foreach ($target in $targets) {
        $account = Get-DemoStorage $target
        if ($Stage -eq 'Exemptions') {
            $existing = Invoke-DemoArm -Method GET -Path (
                "$($account.id)/providers/Microsoft.Authorization/policyExemptions?api-version=2022-07-01-preview"
            )
            $own = @($existing.value | Where-Object {$_.name -eq 'giandoria-public-storage-poc'})
            if ($own.Count -eq 0) {
                if ($account.properties.publicNetworkAccess -ne 'Disabled') {
                    throw 'Refusing to recreate a missing exemption on an already-public account.'
                }
                $exemptionParameters = @("storageAccountName=$($target.Name)",
                    "policyAssignmentId=$($assignment.id)")
                Invoke-AzJson -Arguments (@('deployment', 'group', 'validate',
                    '--resource-group', $target.Group,
                    '--template-file', (Join-Path $PSScriptRoot 'storage-exemption.bicep'),
                    '--parameters') + $exemptionParameters) | Out-Null
                Invoke-Az -Arguments (@('deployment', 'group', 'what-if',
                    '--resource-group', $target.Group,
                    '--template-file', (Join-Path $PSScriptRoot 'storage-exemption.bicep'),
                    '--parameters') + $exemptionParameters + @('--no-pretty-print', '--only-show-errors'))
                Invoke-AzJson -Arguments @('deployment', 'group', 'create',
                    '--name', 'giandoria-storage-exemption', '--resource-group', $target.Group,
                    '--template-file', (Join-Path $PSScriptRoot 'storage-exemption.bicep'),
                    '--parameters', "storageAccountName=$($target.Name)", "policyAssignmentId=$($assignment.id)") |
                    Out-Null
            }
        }
        Assert-DemoStorageExemption -Account $account -AssignmentId $assignment.id | Out-Null
        Write-Host "$($target.Name): individual non-expiring Storage network exemption verified."
    }
    if ($Stage -eq 'Public') {
        $publicParameters = @("operatorPrincipalId=$($operator.id)", 'storagePublicNetworkAccess=Enabled')
        Invoke-AzJson -Arguments (@('deployment', 'sub', 'create', '--name', 'giandoria-demo-foundation',
            '--location', 'swedencentral', '--template-file', $main, '--parameters') + $publicParameters) | Out-Null
        foreach ($target in $targets) {
            $account = Get-DemoStorage $target
            if ($account.properties.publicNetworkAccess -ne 'Enabled' -or
                $account.properties.allowSharedKeyAccess -ne $false -or
                $account.properties.allowBlobPublicAccess -ne $false -or
                $account.properties.supportsHttpsTrafficOnly -ne $true) {
                throw 'Actual Storage security settings differ from the intended PoC.'
            }
        }
        Write-Host 'Public Storage access enabled; shared keys and anonymous blobs remain disabled.'
    }
    return
}

if ($Stage -eq 'Fabric') {
    $group = 'rg-giandoria-fabric-demo'
    $groupResource = Invoke-AzJson -Arguments @('group', 'show', '--name', $group)
    Assert-DemoOwnership $groupResource
    $skus = Invoke-DemoArm -Method GET -Path (
        "$script:DemoSubscriptionScope/providers/Microsoft.Fabric/skus?api-version=2023-11-01"
    )
    $f4 = @($skus.value | Where-Object {
        $_.name -eq 'F4' -and @($_.locations | Where-Object {
            $_.ToLowerInvariant().Replace(' ', '') -eq 'swedencentral'
        }).Count -gt 0 -and @($_.restrictions).Count -eq 0
    })
    if ($f4.Count -eq 0) { throw 'F4 is not listed as available in Sweden Central. No SKU/region fallback.' }
    $template = Join-Path $PSScriptRoot 'fabric.bicep'
    Invoke-AzJson -Arguments @('deployment', 'group', 'validate', '--resource-group', $group,
        '--template-file', $template, '--parameters', "adminMember=$($operator.userPrincipalName)") | Out-Null
    Invoke-Az -Arguments @('deployment', 'group', 'what-if', '--resource-group', $group,
        '--template-file', $template, '--parameters', "adminMember=$($operator.userPrincipalName)",
        '--no-pretty-print', '--only-show-errors')
    try {
        $deployment = Invoke-AzJson -Arguments @('deployment', 'group', 'create',
            '--name', 'giandoria-demo-fabric', '--resource-group', $group,
            '--template-file', $template, '--parameters', "adminMember=$($operator.userPrincipalName)")
        $capacityId = $deployment.properties.outputs.capacityResourceId.value
        $capacity = Invoke-DemoArm -Method GET -Path "${capacityId}?api-version=2023-11-01"
        Assert-DemoOwnership $capacity
        $fabricToken = Invoke-AzJson -Arguments @('account', 'get-access-token',
            '--resource', 'https://api.fabric.microsoft.com')
        $headers = @{ Authorization = "Bearer $($fabricToken.accessToken)" }
        $capacityResponse = Invoke-RecordedWebRequest -Uri 'https://api.fabric.microsoft.com/v1/capacities' -Headers $headers
        $available = $capacityResponse.Content | ConvertFrom-Json -DateKind String
        if (Get-Value $available 'continuationToken') { throw 'Fabric capacity discovery is paginated.' }
        $fabricCapacities = @($available.value | Where-Object {
            $_.displayName -eq $capacity.name -and $_.sku -eq 'F4'
        })
        if ($fabricCapacities.Count -ne 1) { throw 'Cannot resolve the new F4 to exactly one accessible Fabric capacity.' }
        $response = Invoke-RecordedWebRequest -Uri 'https://api.fabric.microsoft.com/v1/workspaces' -Headers $headers
        $workspaces = $response.Content | ConvertFrom-Json -DateKind String
        if (Get-Value $workspaces 'continuationToken') {
            throw 'Workspace discovery is paginated; refusing incomplete ownership discovery.'
        }
        $workspace = @($workspaces.value | Where-Object {$_.displayName -eq 'ws-giandoria-demo'})
        $recordPath = Join-Path $script:DemoLocal 'demo-workspace.json'
        if ($workspace.Count -gt 1) { throw 'Multiple demo workspaces exist; refusing to choose one.' }
        if ($workspace.Count -eq 1) {
            if (-not (Test-Path -LiteralPath $recordPath)) { throw 'Refusing to adopt an unrecorded existing workspace.' }
            $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
            if ($record.id -ne $workspace[0].id) { throw 'Workspace identity differs from the recorded deployment.' }
        }
        else {
            $body = @{
                displayName = 'ws-giandoria-demo'
                description = 'Giandoria synthetic-data demo; managed by the infra/demo scripts.'
                capacityId = $fabricCapacities[0].id
            } | ConvertTo-Json
            $response = Invoke-RecordedWebRequest -Method POST -Uri 'https://api.fabric.microsoft.com/v1/workspaces' `
                -Headers $headers -ContentType 'application/json' -Body $body
            $created = $response.Content | ConvertFrom-Json -DateKind String
            Write-JsonFile -InputObject $created -Path $recordPath
        }
        Write-Host 'Fabric capacity and empty demo workspace prepared. No business items have been published.'
    }
    finally {
        $capacities = @(Invoke-AzJson -Arguments @('resource', 'list', '--resource-group', $group,
            '--resource-type', 'Microsoft.Fabric/capacities'))
        foreach ($item in $capacities) {
            Assert-DemoOwnership $item
            $current = Invoke-DemoArm -Method GET -Path "$($item.id)?api-version=2023-11-01"
            if ($current.properties.state -ne 'Paused') {
                Invoke-DemoArm -Method POST -Path "$($item.id)/suspend?api-version=2023-11-01" | Out-Null
                for ($attempt = 0; $attempt -lt 30; $attempt++) {
                    $current = Invoke-DemoArm -Method GET -Path "$($item.id)?api-version=2023-11-01"
                    if ($current.properties.state -eq 'Paused') { break }
                    Start-Sleep -Seconds 10
                }
                if ($current.properties.state -ne 'Paused') { throw 'F4 suspension not confirmed. Immediate action required.' }
            }
            Write-Host "$($item.name): Paused."
        }
    }
}
