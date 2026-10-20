#Requires -Version 7.4

<#
.SYNOPSIS
Start, extend, stop or inspect the Giandoria cloud lab. Defaults: Status; new sessions last 240 REAL minutes.
.DESCRIPTION
Uses the recorded Azure context and Automation runbooks. Start does not reset the company or automatically extend
an existing session. Extend adds real minutes to the previous deadline and keeps speed/mode; at most 24 hours remain.
Status is read-only: it prints a readable summary to the host and retains raw session JSON on the output stream.
For input examples and all portal/internal parameters see infra/demo/README.md.
.PARAMETER Action
Status (default) reads the saved control record, not a full resource-health check. Start activates the saved company.
Extend adds time to a running Continuous/Analysis session. Stop shuts down that specific session and preserves data.
Reconcile is an advanced safety check, not a manual Stop for a healthy session.
.PARAMETER SessionId
Start generates one if omitted. Stop/Extend require the ID returned by Start to protect against stale commands.
.PARAMETER MaxWallMinutes
Start only: real session duration, 10-1440 minutes, default 240 (4 hours). Startup time is included.
.PARAMETER ExtensionMinutes
Extend only: real minutes added to the existing deadline, 10-1440, default 240 (4 hours).
.PARAMETER Speed
Start/Continuous only: simulated seconds per real second, 1-8760. 8760 ~ year/hour; 730 ~ month/hour; 24 = day/hour;
1 = real-time. IO/model calls can slow actual progress. Independent of MaxWallMinutes; Extend cannot change it.
.PARAMETER Mode
Start only: Continuous (default) generates live events; Analysis enables queries without advancing the company;
Batch is the advanced finite collector and is not paced by Speed.
.PARAMETER Force
Stop/Reconcile only: skip graceful worker waiting for recovery; still verify shutdown and retain stored data.
.EXAMPLE
.\ops\Invoke-LabControl.ps1 -Action Start -Mode Continuous -Speed 730 -MaxWallMinutes 180
Three real hours, targeting about one simulated month per hour.
.EXAMPLE
.\ops\Invoke-LabControl.ps1 -Action Extend -SessionId '<recorded-guid>' -ExtensionMinutes 240
Add four real hours to the session's existing deadline.
.EXAMPLE
.\ops\Invoke-LabControl.ps1 -Action Status
Read the saved session/deadline without changing the running lab.
#>
[CmdletBinding()]
param(
    [ValidateSet('Start','Extend','Stop','Status','Reconcile')][string]$Action='Status',
    [guid]$SessionId=[guid]::Empty,
    [ValidateRange(10,1440)][int]$MaxWallMinutes=240,
    [ValidateRange(10,1440)][int]$ExtensionMinutes=240,
    [ValidateRange(1,8760)][int]$Speed=8760,
    [ValidateSet('Continuous','Batch','Analysis')][string]$Mode='Continuous',
    [switch]$Force
)
if ($Force -and $Action -notin @('Stop','Reconcile')) { throw 'Force applies only to Stop/Reconcile; it cannot replace or restart a running session.' }
$applicable = switch ($Action) {
    'Start' { @('MaxWallMinutes','Speed','Mode') }
    'Extend' { @('ExtensionMinutes') }
    default { @() }
}
$ignored = @('MaxWallMinutes','ExtensionMinutes','Speed','Mode') |
    Where-Object { $PSBoundParameters.ContainsKey($_) -and $_ -notin $applicable }
if ($ignored) { Write-Warning "Ignored for ${Action}: $($ignored -join ', '). See Get-Help .\ops\Invoke-LabControl.ps1 -Full." }
. "$PSScriptRoot\..\infra\demo\common.ps1"
Initialize-DemoContext
$base = "$script:DemoSubscriptionScope/resourceGroups/rg-giandoria-ops-demo/providers/Microsoft.Automation/automationAccounts/aa-giandoria-demo"
$account = Invoke-DemoArm GET "${base}?api-version=2024-10-23"
Assert-DemoOwnership $account
$token = Invoke-AzJson -Arguments @('account','get-access-token','--resource','https://management.azure.com/')
$headers = @{ Authorization="Bearer $($token.accessToken)" }
if ($Action -eq 'Status') {
    $storage = (Get-DemoDeploymentOutputs).stateAccountName.value
    $token = Invoke-AzJson -Arguments @('account','get-access-token','--resource','https://storage.azure.com/')
    $response = Invoke-RecordedWebRequest -Uri "https://$storage.blob.core.windows.net/lab-state/active-session.json" `
        -Headers @{Authorization="Bearer $($token.accessToken)";'x-ms-version'='2023-11-03'} -SkipHttpErrorCheck
    if ($response.StatusCode -eq 404) { Write-Host 'No session has been created.'; return }
    if ($response.StatusCode -ne 200) { throw "Session read failed: HTTP $($response.StatusCode)." }
    $session = $response.Content | ConvertFrom-Json -DateKind String
    $expires = [datetimeoffset]::Parse($session.expiresAt)
    Write-Host "Recorded session: $($session.id); state=$($session.state); desired=$($session.desired)."
    Write-Host "Automatic shutdown UTC: $($expires.ToUniversalTime().ToString('o'))."
    if ($session.desired -eq 'Running') {
        $minutes = [math]::Max(0, [math]::Ceiling(($expires - [datetimeoffset]::UtcNow).TotalMinutes))
        Write-Host "Time to deadline: approximately $minutes REAL minutes; this is not a worker-health check."
    }
    $mode = Get-Value $session 'mode'
    if ($mode -eq 'Continuous') {
        Write-Host "Mode=Continuous; Speed=$($session.speed) simulated seconds per REAL second (8760 ~ year/hour; 730 ~ month/hour; 24 = day/hour)."
    }
    elseif ($mode -eq 'Analysis') { Write-Host 'Mode=Analysis: queries only, no company time advances; Speed does not apply.' }
    elseif ($mode -eq 'Batch') { Write-Host 'Mode=Batch: advanced finite collector, not paced by Speed.' }
    $response.Content
    return
}
if ($Action -eq 'Start' -and $SessionId -eq [guid]::Empty) { $SessionId=[guid]::NewGuid() }
if ($Action -in @('Stop','Extend') -and $SessionId -eq [guid]::Empty) { throw "$Action requires the recorded SessionId." }
$name = switch ($Action) {
    'Start' { 'Start-GiandoriaLab' }
    'Extend' { 'Extend-GiandoriaLab' }
    default { 'Stop-GiandoriaLab' }
}
$parameters = if ($Action -eq 'Reconcile') { @{Reconcile='True'} } else { @{SessionId=$SessionId.ToString()} }
if ($Action -eq 'Start') {
    $parameters.MaxWallMinutes="$MaxWallMinutes"
    $parameters.Speed="$Speed"
    $parameters.Mode=$Mode
}
if ($Action -eq 'Extend') {
    $parameters.ExtensionMinutes="$ExtensionMinutes"
}
if ($Force) { $parameters.Force='True' }
$job = [guid]::NewGuid().ToString()
$parameters.ControlJobId=$job
$body = @{properties=@{runbook=@{name=$name};parameters=$parameters}} | ConvertTo-Json -Depth 6
Invoke-RecordedWebRequest -Method PUT -Uri "https://management.azure.com$base/jobs/${job}?api-version=2024-10-23" `
    -Headers $headers -Body $body -ContentType 'application/json' | Out-Null
Write-JsonFile @{action=$Action;sessionId=$SessionId.ToString();jobId=$job;startedAt=[datetime]::UtcNow.ToString('o')} `
    (Join-Path $script:DemoLocal 'last-control-operation.json')
Write-Host "$Action submitted. Automation JobId=$job; waiting for its result. Queueing and activation may take several minutes."
$deadline=[datetime]::UtcNow.AddMinutes(12)
do {
    Start-Sleep -Seconds 10
    $result=Invoke-DemoArm GET "$base/jobs/${job}?api-version=2024-10-23"
    if ($result.properties.status -in @('Completed','Failed','Stopped','Suspended')) {
        Write-JsonFile $result (Join-Path $script:DemoLocal "control-$job.json")
        $streams=Invoke-DemoArm GET "$base/jobs/$job/streams?api-version=2024-10-23"
        Write-JsonFile $streams (Join-Path $script:DemoLocal "control-$job-streams.json")
        foreach ($stream in $streams.value) { Write-Host "$($stream.properties.streamType): $($stream.properties.summary)" }
        if ($result.properties.status -ne 'Completed') { throw "Automation job $job ended $($result.properties.status): $($result.properties.exception)" }
        Write-Host "$Action completed. SessionId=$SessionId"
        return
    }
} while ([datetime]::UtcNow -lt $deadline)
throw "Automation job wait exceeded 12 minutes; job $job may still be running. Inspect and invoke Stop; do not assume cancellation."
