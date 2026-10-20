<#
.SYNOPSIS
STOP NOW and pause Fabric, preserving company state/history. Change NOTHING for normal use: Force=False,
SessionId/ControlJobId empty, IfExpired=False, Reconcile=False. Click Start to submit this Stop action.
Read job Output for confirmed Fabric Paused. Cancelling an Automation job does NOT stop the lab.
Force=True skips graceful waiting: recovery only. IfExpired/Reconcile are internal schedule controls.
To ADD TIME use Extend-GiandoriaLab; to resume later use Start-GiandoriaLab.
.DESCRIPTION
Start this runbook to shut down the laboratory, not merely cancel a Start Automation job. Normal Stop requests a
checkpoint, waits for the worker and verifies Fabric is Paused. Read job Output for final confirmation.
Azure Automation does not show ValidateSet choices or inline parameter help; see infra/demo/README.md.
.PARAMETER Force
False (default) requests graceful shutdown and allows checkpointing. True skips graceful waiting for recovery.
Both verify the final resource state; Force is not a way to delete data.
.PARAMETER SessionId
Leave empty in the portal to stop the current recorded session. Scripts should pass the session ID returned by Start
so an old command cannot stop a newer session.
.PARAMETER ControlJobId
Internal Automation controller identifier. Leave empty in the portal.
.PARAMETER IfExpired
Internal scheduled-stop guard: False (default) stops on demand. True stops only if the matching session is expired.
Do not set True for an ordinary manual Stop: it may deliberately leave the running lab untouched.
.PARAMETER Reconcile
Internal hourly safety check: False (default) performs manual Stop. True only settles shutdown/expired sessions and
does not stop a healthy session within its deadline. Leave False for manual use.
.EXAMPLE
.\Stop-GiandoriaLab.ps1
In Automation, gracefully stops the current session and pauses Fabric, retaining all data.
#>
[CmdletBinding()]
param(
    [ValidateSet('True','False')][string]$Force='False',
    [guid]$SessionId = [guid]::Empty,
    [guid]$ControlJobId = [guid]::Empty,
    [ValidateSet('True','False')][string]$IfExpired='False',
    [ValidateSet('True','False')][string]$Reconcile='False'
)
. "$PSScriptRoot\LabControl.ps1"

if ($Reconcile -eq 'True') {
    $session = Get-ControlSession
    if (-not $session) { throw 'No recorded session; inspect unexpected active resources manually.' }
    if ($session.value.state -eq 'Stopped' -or
        [datetimeoffset]::Parse($session.value.expiresAt) -le [datetimeoffset]::UtcNow -or
        $session.value.desired -eq 'Stopped') {
        Stop-ControlLab $session.value.id -Force -ControlJobId $ControlJobId `
            -IfExpired:($session.value.desired -ne 'Stopped' -and $session.value.state -ne 'Stopped')
    }
    else { Write-Output 'Session remains within its deadline.' }
}
else {
    Write-Output "Stop requested: Force=$Force; IfExpired=$IfExpired. Company history will be retained."
    if ($IfExpired -eq 'True') { Write-Output 'Expiry guard enabled: a session still within its deadline will NOT stop.' }
    if ($SessionId -eq [guid]::Empty) {
        $session = Get-ControlSession
        if (-not $session) { throw 'No session has been recorded; inspect resource state.' }
        $SessionId = [guid]$session.value.id
    }
    Stop-ControlLab $SessionId.ToString() -Force:($Force -eq 'True') -ControlJobId $ControlJobId `
        -IfExpired:($IfExpired -eq 'True')
}
