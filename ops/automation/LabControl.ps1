$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($PSVersionTable.PSVersion -lt [version]'7.4') { throw 'Lab runbooks require PowerShell 7.4 or newer.' }
Write-Output (@{
    operation='runtime'; powershell=$PSVersionTable.PSVersion.ToString(); edition=$PSVersionTable.PSEdition
} | ConvertTo-Json -Compress)
Disable-AzContextAutosave -Scope Process | Out-Null
Connect-AzAccount -Identity | Out-Null
$storedConfig = Get-AutomationVariable -Name 'GiandoriaConfig'
$script:Config = if ($storedConfig -is [string]) {
    $storedConfig | ConvertFrom-Json -AsHashtable
} elseif ($storedConfig -is [System.Collections.IDictionary] -or $storedConfig -is [pscustomobject]) {
    $storedConfig | ConvertTo-Json -Depth 10 | ConvertFrom-Json -AsHashtable
} else { throw 'Unsupported Automation configuration value type.' }
if ($script:Config.location -ne 'swedencentral' -or $script:Config.project -ne 'giandoria') {
    throw 'Unexpected control configuration.'
}
Set-AzContext -SubscriptionId $script:Config.subscriptionId -Tenant $script:Config.tenantId | Out-Null
$script:SessionUri = "https://$($script:Config.stateAccount).blob.core.windows.net/lab-state/active-session.json"

function Invoke-ControlHttp {
    param([string]$Method, [string]$Uri, $Body, [hashtable]$ExtraHeaders = @{}, [int[]]$Expected = @(200,201,202,204))
    $target = [uri]$Uri
    if ($target.Scheme -ne 'https' -or $target.Host -notin @(
        'management.azure.com', "$($script:Config.stateAccount).blob.core.windows.net")) {
        throw 'Control request outside recorded endpoints.'
    }
    $audience = if ($target.Host -eq 'management.azure.com') { 'https://management.azure.com/' } else { 'https://storage.azure.com/' }
    $token = Get-AzAccessToken -ResourceUrl $audience -AsSecureString
    $plain = if ($token.Token -is [securestring]) {
        ConvertFrom-SecureString $token.Token -AsPlainText
    } else { $token.Token }
    $headers = @{ Authorization = "Bearer $plain"; 'x-ms-version' = '2023-11-03'; 'x-ms-date' = [datetime]::UtcNow.ToString('R') }
    foreach ($key in $ExtraHeaders.Keys) { $headers[$key] = $ExtraHeaders[$key] }
    $arguments = @{
        Uri=$Uri; Method=$Method; Headers=$headers; SkipHttpErrorCheck=$true
        TimeoutSec=60; MaximumRedirection=0
    }
    if ($Method -in @('POST','PUT')) { $arguments.ContentType='application/json' }
    if ($null -ne $Body) { $arguments.Body = $Body | ConvertTo-Json -Depth 30 -Compress; $arguments.ContentType='application/json' }
    $id = [guid]::NewGuid().ToString()
    Write-Verbose (@{ operation='http'; correlation=$id; method=$Method; path=$target.AbsolutePath; status='Started' } | ConvertTo-Json -Compress) -Verbose
    $response = Invoke-WebRequest @arguments
    Write-Verbose (@{ operation='http'; correlation=$id; code=[int]$response.StatusCode } | ConvertTo-Json -Compress) -Verbose
    if ([int]$response.StatusCode -notin $Expected) {
        $failure = [InvalidOperationException]::new("Control $Method failed: HTTP $([int]$response.StatusCode) at $($target.AbsolutePath).")
        $failure.Data['StatusCode'] = [int]$response.StatusCode
        throw $failure
    }
    return $response
}

function Get-ControlSession {
    $response = Invoke-ControlHttp GET $script:SessionUri -Expected @(200,404)
    if ($response.StatusCode -eq 404) { return $null }
    $value = $response.Content | ConvertFrom-Json -AsHashtable
    $document = [System.Text.Json.JsonDocument]::Parse([string]$response.Content)
    try {
        # PowerShell 7.4 parses dates automatically; retain exact persisted timestamp strings.
        foreach ($property in $document.RootElement.EnumerateObject()) {
            if ($property.Value.ValueKind -eq [System.Text.Json.JsonValueKind]::String) {
                $value[$property.Name] = $property.Value.GetString()
            }
        }
    }
    finally { $document.Dispose() }
    return @{ value=$value; etag=[string]@($response.Headers.ETag)[0] }
}

function Set-ControlSession {
    param([hashtable]$Value, [string]$ETag)
    $headers = @{ 'x-ms-blob-type'='BlockBlob' }
    if ($ETag) { $headers['If-Match']=$ETag } else { $headers['If-None-Match']='*' }
    Invoke-ControlHttp PUT $script:SessionUri $Value $headers | Out-Null
}

function Write-ControlSessionSummary {
    param([hashtable]$Session)
    Write-Output "SessionId=$($Session.id); state=$($Session.state); Mode=$($Session.mode)."
    Write-Output "Automatic shutdown UTC: $([datetimeoffset]::Parse($Session.expiresAt).ToUniversalTime().ToString('o'))."
    if ($Session.mode -eq 'Continuous') {
        $days = ([double]$Session.speed / 24).ToString('0.##', [cultureinfo]::InvariantCulture)
        Write-Output "Speed=$($Session.speed) simulated seconds per REAL second; target $days simulated days per REAL hour."
        Write-Output 'Hourly simulation ticks; IO/model calls can slow the achieved rate. Downtime is not replayed.'
    }
    elseif ($Session.mode -eq 'Analysis') { Write-Output 'Analysis only: Fabric queries are available; no company time advances. Speed does not apply.' }
    else { Write-Output 'Batch: finite collection, not paced by Speed. Worker completion does not automatically pause Fabric.' }
    Write-Output 'To add time: Extend-GiandoriaLab with ExtensionMinutes. To shut down: Stop-GiandoriaLab.'
}

function Get-ControlCapacity {
    $response = Invoke-ControlHttp GET "https://management.azure.com$($script:Config.capacityId)?api-version=2023-11-01"
    $capacity = $response.Content | ConvertFrom-Json -AsHashtable
    if ($capacity.tags.project -ne 'giandoria' -or $capacity.tags.env -ne 'demo' -or $capacity.sku.name -ne 'F4') {
        throw 'Capacity ownership/SKU mismatch.'
    }
    return $capacity
}

function Edit-ControlSession {
    param([string]$SessionId, [scriptblock]$Change, [scriptblock]$Condition)
    for ($attempt=0; $attempt -lt 8; $attempt++) {
        $current = Get-ControlSession
        if (-not $current -or $current.value.id -ne $SessionId) { return $null }
        if ($Condition -and -not (& $Condition $current.value)) { return $null }
        & $Change $current.value
        try {
            Set-ControlSession $current.value $current.etag
            return $current
        } catch {
            if ($_.Exception.Data['StatusCode'] -ne 412 -or $attempt -eq 7) { throw }
            Start-Sleep -Milliseconds 100
        }
    }
}

function Test-ControlStarterActive {
    param([hashtable]$Session)
    if (-not $Session.ContainsKey('startInProgress') -or -not $Session.startInProgress) { return $false }
    if (-not $Session.startJobId) { throw 'Untracked starter; cannot certify shutdown.' }
    $job = (Invoke-ControlHttp GET "https://management.azure.com$($script:Config.automationId)/jobs/$($Session.startJobId)?api-version=2024-10-23").Content |
        ConvertFrom-Json -AsHashtable
    return $job.properties.status -notin @('Completed','Failed','Stopped','Suspended')
}

function Wait-ControlCapacity {
    param([string]$State)
    $deadline = [datetime]::UtcNow.AddMinutes(5)
    do {
        if ((Get-ControlCapacity).properties.state -eq $State) { return }
        Start-Sleep -Seconds 5
    } while ([datetime]::UtcNow -lt $deadline)
    throw "Capacity did not reach $State."
}

function Assert-ControlStart {
    param([string]$SessionId)
    $session = Get-ControlSession
    if (-not $session -or $session.value.id -ne $SessionId -or $session.value.desired -ne 'Running' -or
        [datetimeoffset]::Parse($session.value.expiresAt) -le [datetimeoffset]::UtcNow) {
        throw 'Start cancelled, expired or superseded.'
    }
    return $session
}

function Resolve-ControlJobId {
    param([guid]$ControlJobId)
    if ($ControlJobId -eq [guid]::Empty) {
        $metadata = Get-Variable -Name PSPrivateMetadata -ErrorAction SilentlyContinue
        if (-not $metadata) { throw 'An Automation job ID is required to track shutdown ownership.' }
        $ControlJobId = [guid]$metadata.Value.JobId
    }
    return $ControlJobId
}

function Set-ControlDeadline {
    param([string]$SessionId, [datetimeoffset]$Expires, [guid]$ControlJobId)
    $base = "https://management.azure.com$($script:Config.automationId)"
    $schedule = "stop$($SessionId.Replace('-',''))$($ControlJobId.ToString('N'))"
    # Automation truncates schedule seconds; round up so the expiry guard cannot fire too early and no-op.
    $utc=$Expires.ToUniversalTime()
    $scheduledAt=[datetimeoffset]::new($utc.Year,$utc.Month,$utc.Day,$utc.Hour,$utc.Minute,0,[timespan]::Zero)
    if ($scheduledAt -lt $utc) { $scheduledAt=$scheduledAt.AddMinutes(1) }
    Invoke-ControlHttp PUT "$base/schedules/${schedule}?api-version=2024-10-23" @{
        properties=@{startTime=$scheduledAt.ToString('o');frequency='OneTime';timeZone='UTC';isEnabled=$true}
    } | Out-Null
    $actualSchedule=(Invoke-ControlHttp GET "$base/schedules/${schedule}?api-version=2024-10-23").Content |
        ConvertFrom-Json -AsHashtable
    if ([datetimeoffset]$actualSchedule.properties.startTime -ne $scheduledAt) {
        throw 'Shutdown schedule start time differs from its verified minute-aligned deadline.'
    }
    $binding = [guid]::NewGuid().ToString()
    Invoke-ControlHttp PUT "$base/jobSchedules/${binding}?api-version=2024-10-23" @{
        properties=@{
            schedule=@{name=$schedule};runbook=@{name='Stop-GiandoriaLab'}
            parameters=@{SessionId=$SessionId;IfExpired='True'}
        }
    } | Out-Null
    $actual = (Invoke-ControlHttp GET "$base/jobSchedules/${binding}?api-version=2024-10-23").Content |
        ConvertFrom-Json -AsHashtable
    if ($actual.properties.schedule.name -ne $schedule -or
        $actual.properties.runbook.name -ne 'Stop-GiandoriaLab' -or
        $actual.properties.parameters.SessionId -ne $SessionId -or
        $actual.properties.parameters.IfExpired -ne 'True') {
        throw 'Shutdown deadline binding does not match the requested session.'
    }
}

function Wait-ControlWorkerDrained {
    param([string]$SessionId)
    $until = [datetime]::UtcNow.AddMinutes(3)
    do {
        Assert-ControlStart $SessionId | Out-Null
        $response = Invoke-ControlHttp GET "https://management.azure.com$($script:Config.runtimeJobId)/executions?api-version=2024-03-01"
        $result = $response.Content | ConvertFrom-Json -AsHashtable
        if ($result.ContainsKey('nextLink') -and $result.nextLink) { throw 'Worker drain requires explicit execution pagination.' }
        $active = @($result.value | Where-Object { $_.properties.status -notin @('Succeeded','Failed','Stopped') })
        if ($active.Count -eq 0) { return }
        Start-Sleep -Seconds 5
    } while ([datetime]::UtcNow -lt $until)
    throw 'Worker did not checkpoint and drain for extension; refusing overlapping execution.'
}

function Extend-ControlLab {
    param([guid]$SessionId, [int]$ExtensionMinutes, [guid]$ControlJobId)
    $existing = Get-ControlSession
    if (-not $existing) { throw 'No session exists to extend. Use Start-GiandoriaLab to start the saved company.' }
    if ($SessionId -eq [guid]::Empty) { $SessionId = [guid]$existing.value.id }
    $id = $SessionId.ToString()
    $current = Assert-ControlStart $id
    if ($current.value.state -ne 'Running' -or $current.value.startInProgress) {
        throw 'Only a fully running session can be extended. Wait for the current Start/Extend/Stop job to settle, then inspect its Output.'
    }
    if (-not $current.value.ContainsKey('workerGeneration')) {
        throw 'This session predates extension support; Stop and Start once before extending.'
    }
    if ($current.value.mode -notin @('Continuous','Analysis')) { throw 'Finite Batch collection cannot be extended.' }
    if ((Get-ControlCapacity).properties.state -ne 'Active') { throw 'Extension requires active F4.' }
    $expires = [datetimeoffset]::Parse($current.value.expiresAt).AddMinutes($ExtensionMinutes)
    if ($expires -gt [datetimeoffset]::UtcNow.AddHours(24)) {
        throw "Extension would exceed 24 real hours remaining. Reduce ExtensionMinutes; current shutdown UTC: $($current.value.expiresAt)."
    }
    Write-Output "Extend requested: add $ExtensionMinutes REAL minutes to shutdown UTC $($current.value.expiresAt)."
    Write-Output 'Company state, speed and model budget are preserved; worker replacement may briefly pause new events.'
    Set-ControlDeadline $id $expires $ControlJobId
    $current.value.expiresAt = $expires.ToString('o')
    $current.value.workerGeneration = [guid]::NewGuid().ToString()
    $current.value.startInProgress = $true
    $current.value.startJobId = $ControlJobId.ToString()
    Set-ControlSession $current.value $current.etag
    $success = $false
    try {
        if ($script:Config.runtimeJobId -and $current.value.mode -eq 'Continuous') {
            Wait-ControlWorkerDrained $id
            Assert-ControlStart $id | Out-Null
            Invoke-ControlHttp POST "https://management.azure.com$($script:Config.runtimeJobId)/start?api-version=2024-03-01" | Out-Null
        }
        $current = Assert-ControlStart $id
        $current.value.startInProgress = $false
        Set-ControlSession $current.value $current.etag
        $success = $true
        Write-Output "Lab extended by $ExtensionMinutes REAL minutes."
        Write-ControlSessionSummary $current.value
    }
    finally {
        if (-not $success) {
            Edit-ControlSession $id { param($value) $value.startInProgress=$false } | Out-Null
            Stop-ControlLab $id -Force -ControlJobId $ControlJobId
        }
    }
}

function Stop-ControlLab {
    param([string]$SessionId, [switch]$Force, [guid]$ControlJobId=[guid]::Empty, [switch]$IfExpired)
    $ControlJobId = Resolve-ControlJobId $ControlJobId
    $claim=[guid]::NewGuid().ToString()
    $session = Get-ControlSession
    if (-not $session -or $session.value.id -ne $SessionId) {
        Write-Output 'No matching session; no resource changes.'
        return
    }
    $session = Edit-ControlSession $SessionId {
        param($value)
        $value.desired = 'Stopped'
        $value.state = 'Stopping'
        if (-not $value.ContainsKey('stopClaims')) { $value.stopClaims=@{} }
        $value.stopClaims[$claim]=$ControlJobId.ToString()
    } -Condition {
        param($value)
        -not $IfExpired -or [datetimeoffset]::Parse($value.expiresAt) -le [datetimeoffset]::UtcNow
    }
    if (-not $session) {
        Write-Output 'No matching session eligible for Stop; no resource changes. Check SessionId and the IfExpired guard.'
        return
    }
    $failures = [System.Collections.Generic.List[string]]::new()
    if ($script:Config.runtimeJobId) {
        try {
            $base = "https://management.azure.com$($script:Config.runtimeJobId)"
            $response = Invoke-ControlHttp GET "$base/executions?api-version=2024-03-01"
            $executions = ($response.Content | ConvertFrom-Json -AsHashtable).value
            if (-not $Force) {
                $until = [datetime]::UtcNow.AddSeconds(60)
                do {
                    if (@($executions | Where-Object { $_.properties.status -in @('Running','Processing','Pending') }).Count -eq 0) { break }
                    Start-Sleep -Seconds 5
                    $executions = ((Invoke-ControlHttp GET "$base/executions?api-version=2024-03-01").Content | ConvertFrom-Json -AsHashtable).value
                } while ([datetime]::UtcNow -lt $until)
            }
            if (@($executions | Where-Object { $_.properties.status -in @('Running','Processing','Pending') }).Count) {
                Invoke-ControlHttp POST "$base/stop?api-version=2024-03-01" | Out-Null
                $until = [datetime]::UtcNow.AddMinutes(3)
                do {
                    $executions = ((Invoke-ControlHttp GET "$base/executions?api-version=2024-03-01").Content | ConvertFrom-Json -AsHashtable).value
                    if (@($executions | Where-Object { $_.properties.status -notin @('Succeeded','Failed','Stopped') }).Count -eq 0) { break }
                    Start-Sleep -Seconds 5
                } while ([datetime]::UtcNow -lt $until)
                if (@($executions | Where-Object { $_.properties.status -notin @('Succeeded','Failed','Stopped') }).Count) {
                    throw 'Runtime executions did not reach a terminal state.'
                }
            }
        } catch { $failures.Add("Runtime stop failed: $($_.Exception.Message)") }
    }
    try {
        $capacity = Get-ControlCapacity
        if ($capacity.properties.state -ne 'Paused') {
            Invoke-ControlHttp POST "https://management.azure.com$($script:Config.capacityId)/suspend?api-version=2023-11-01" | Out-Null
        }
        Wait-ControlCapacity 'Paused'
    } catch { $failures.Add("Capacity stop failed: $($_.Exception.Message)") }
    $starterActive = $true
    try { $starterActive = Test-ControlStarterActive (Get-ControlSession).value }
    catch { $failures.Add("Starter verification failed: $($_.Exception.Message)") }
    $finishedClaims=@($claim)
    foreach ($entry in (Get-ControlSession).value.stopClaims.GetEnumerator()) {
        if ($entry.Key -eq $claim) { continue }
        try {
            $job = (Invoke-ControlHttp GET "https://management.azure.com$($script:Config.automationId)/jobs/$($entry.Value)?api-version=2024-10-23").Content |
                ConvertFrom-Json -AsHashtable
            if ($job.properties.status -in @('Completed','Failed','Stopped','Suspended')) { $finishedClaims += $entry.Key }
        } catch { $failures.Add("Concurrent shutdown verification failed: $($_.Exception.Message)") }
    }
    $current = Edit-ControlSession $SessionId {
        param($value)
        foreach ($finished in $finishedClaims) { $value.stopClaims.Remove($finished) }
        $value.state = if ($failures.Count) { 'StopFailed' } elseif ($starterActive -or $value.stopClaims.Count) { 'Stopping' } else { 'Stopped' }
        if (-not $starterActive) { $value.startInProgress=$false }
        if ($value.state -eq 'Stopped') { $value.stoppedAt = [datetime]::UtcNow.ToString('o') }
    }
    if ($failures.Count) { throw ($failures -join '; ') }
    if ($current.value.state -ne 'Stopped') { Write-Output 'Shutdown requested; concurrent controller still settling; reconciliation will verify completion.'; return }
    Write-Output 'Lab stopped; F4 Paused; retained data unchanged.'
}
