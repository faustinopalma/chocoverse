<#
.SYNOPSIS
START the saved company. MaxWallMinutes: REAL duration, 240 = 4h (default), 180 = 3h; allowed 10-1440.
Mode: Continuous = live events, Analysis = history only, Batch = finite collector.
Speed: simulated seconds per REAL second, NOT duration. 8760 ~ year/hour, 730 ~ month/hour, 24 = day/hour.
Leave other fields at defaults and IDs empty. Already running? ADD TIME with Extend-GiandoriaLab; STOP with Stop-GiandoriaLab.
Completed means ready, not stopped. History is retained.
.DESCRIPTION
Start resumes saved company state; it never resets history. Extend keeps the current mode, speed and model budget.
Extend briefly checkpoints/replaces the worker while Fabric stays active. At most 24 real hours may remain.
Use Extend-GiandoriaLab for ordinary extensions; Operation/ExtensionMinutes are retained only for older scripts.
Azure Automation does not display this parameter help in input tooltips. Open Runbook settings > Description for
the quick guide, or use Get-Help locally. Inspect job Output for intent and UTC shutdown time.
.PARAMETER Operation
Compatibility control: leave Start in the portal. Older scripts can still pass Extend with ExtensionMinutes.
For ordinary use choose Extend-GiandoriaLab directly. A duplicate Start does not extend an active session.
.PARAMETER MaxWallMinutes
Start only. Real minutes until automatic shutdown, 10-1440; default 240 (4 hours), 180 = 3 hours.
Independent of Speed. Startup time is included. Ignored by Extend.
.PARAMETER ExtensionMinutes
Compatibility input for Operation=Extend only. Leave 240 for ordinary Start; this field is ignored.
Use Extend-GiandoriaLab instead to add 10-1440 real minutes to an existing deadline.
.PARAMETER Mode
Start only. Continuous (default) resumes the company and generates live events. Analysis activates Fabric for
queries without advancing the company. Batch is the advanced finite collector, not a live demonstration.
.PARAMETER Speed
Start/Continuous only: simulated seconds per real second, 1-8760; default 8760.
8760 targets one 365-day year per real hour; 730 about one month/hour; 24 one day/hour; 1 real-time.
The engine advances in hourly simulated ticks (3600/Speed real seconds per tick), with observations about every
five real seconds. IO and model calls can slow the achieved rate. Speed does not change the real shutdown deadline,
does not replay downtime, and cannot be changed through Extend. Analysis ignores it; Batch is not paced by it.
.PARAMETER SessionId
Technical identifier. Leave empty in the portal: Start generates it; Extend selects the current session.
Scripts should pass the recorded ID to Extend to avoid selecting a newer session. IDs cannot be reused for Start.
.PARAMETER ControlJobId
Internal Automation job identifier used to track controller ownership. Leave empty in the portal.
.EXAMPLE
.\Start-GiandoriaLab.ps1 -MaxWallMinutes 180 -Mode Continuous -Speed 730
Starts a three-real-hour session targeting about one simulated month per real hour.
.EXAMPLE
.\Start-GiandoriaLab.ps1 -Operation Extend -ExtensionMinutes 240
Legacy compatibility only; prefer Extend-GiandoriaLab. Adds four hours to the existing deadline in Automation.
#>
[CmdletBinding()]
param(
    [ValidateRange(10,1440)][int]$MaxWallMinutes = 240,
    [ValidateSet('Continuous','Batch','Analysis')][string]$Mode = 'Continuous',
    [ValidateRange(1,8760)][int]$Speed = 8760,
    [guid]$SessionId = [guid]::Empty,
    [guid]$ControlJobId = [guid]::Empty,
    [ValidateSet('Start','Extend')][string]$Operation = 'Start',
    [ValidateRange(10,1440)][int]$ExtensionMinutes = 240
)
$suppliedParameters = @($PSBoundParameters.Keys)
. "$PSScriptRoot\LabControl.ps1"
$ControlJobId = Resolve-ControlJobId $ControlJobId

$existing = Get-ControlSession
if ($Operation -eq 'Extend') {
    $ignored = @('MaxWallMinutes','Mode','Speed') | Where-Object { $_ -in $suppliedParameters }
    if ($ignored) { Write-Warning "Ignored on Extend: $($ignored -join ', '). The current mode and speed are preserved." }
    Extend-ControlLab -SessionId $SessionId -ExtensionMinutes $ExtensionMinutes -ControlJobId $ControlJobId
    return
}
$ignored = @('ExtensionMinutes') | Where-Object { $_ -in $suppliedParameters }
if ($ignored) { Write-Warning 'ExtensionMinutes is ignored on Start. Use MaxWallMinutes for a new session, or Extend-GiandoriaLab for a running lab.' }
if ($SessionId -eq [guid]::Empty) { $SessionId = [guid]::NewGuid() }
$id = $SessionId.ToString()
if ($existing -and $existing.value.id -eq $id) {
    throw 'Session IDs cannot be reused for Start. Leave SessionId empty for a new session; use Extend-GiandoriaLab to prolong a running one.'
}
if ($existing -and $existing.value.state -notin @('Stopped')) {
    throw "Existing session $($existing.value.id) is $($existing.value.state); no changes made. To add time use Extend-GiandoriaLab and ExtensionMinutes (legacy scripts: Operation=Extend); otherwise wait for its controller or inspect job Output."
}
if ((Get-ControlCapacity).properties.state -ne 'Paused') { throw 'Start requires F4 Paused.' }
Write-Output "Start requested: Mode=$Mode; maximum $MaxWallMinutes REAL minutes, including startup. Existing company history is retained."
Write-Output 'Activation can take several minutes. A completed Start job leaves the laboratory running until Stop or its deadline.'
$expires = [datetimeoffset]::UtcNow.AddMinutes($MaxWallMinutes)
$record = @{
    id=$id; desired='Running'; state='Starting'; startedAt=[datetime]::UtcNow.ToString('o')
    expiresAt=$expires.ToString('o')
    startInProgress=$true; startJobId=$ControlJobId.ToString()
    speed=$Speed; mode=$Mode; workerGeneration=[guid]::NewGuid().ToString()
}
Set-ControlSession $record $(if ($existing) { $existing.etag } else { '' })
$success = $false
try {
    Set-ControlDeadline $id $expires $ControlJobId
    Assert-ControlStart $id | Out-Null
    Invoke-ControlHttp POST "https://management.azure.com$($script:Config.capacityId)/resume?api-version=2023-11-01" | Out-Null
    Wait-ControlCapacity 'Active'
    Assert-ControlStart $id | Out-Null
    if ($script:Config.runtimeJobId -and $Mode -ne 'Analysis') {
        Invoke-ControlHttp POST "https://management.azure.com$($script:Config.runtimeJobId)/start?api-version=2024-03-01" | Out-Null
    }
    $current = Assert-ControlStart $id
    $current.value.state='Running'
    $current.value.startInProgress=$false
    Set-ControlSession $current.value $current.etag
    $success=$true
    Write-Output 'Lab Running; automatic shutdown is armed.'
    Write-ControlSessionSummary $current.value
}
finally {
    if (-not $success) {
        Edit-ControlSession $id { param($value) $value.startInProgress=$false } | Out-Null
        Stop-ControlLab $id -Force -ControlJobId $ControlJobId
    }
}
