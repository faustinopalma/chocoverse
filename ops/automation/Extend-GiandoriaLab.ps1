<#
.SYNOPSIS
ADD TIME to the running lab. ExtensionMinutes adds REAL minutes to the EXISTING shutdown time:
240 = +4h (default), 60 = +1h, 10 = +10min. Allowed 10-1440, with at most 24h remaining afterwards.
Example: shutdown at 18:00 plus 240 minutes becomes 22:00, not four hours from now.
Leave SessionId/ControlJobId empty. Mode, speed, history and model budget stay unchanged.
The worker briefly checkpoints/restarts; Fabric stays active. Lab stopped? Use Start-GiandoriaLab.
.DESCRIPTION
Select this runbook and click Start to submit an extension, not to start a new laboratory session.
Change only ExtensionMinutes. Empty SessionId selects the current session; scripts should pass its recorded ID.
A stopped, expired, starting or stopping session cannot be extended; finite Batch mode cannot be extended.
Read job Output for the previous and new UTC shutdown times. Completed means the extension has finished.
Azure's parameter tooltip does not display this help; open Runbook settings > Description for the quick guide.
.PARAMETER ExtensionMinutes
Real minutes to add to the EXISTING shutdown deadline, not a new duration measured from now.
Default 240 adds four hours. Range 10-1440; the resulting time remaining must not exceed 24 hours.
.PARAMETER SessionId
Leave empty in the portal to select the current running session. Scripts should pass its recorded ID to reject
stale commands. This is not a company identifier; extension preserves the existing session.
.PARAMETER ControlJobId
Internal Automation controller identifier. Leave empty in the portal.
.EXAMPLE
.\Extend-GiandoriaLab.ps1 -ExtensionMinutes 240
In Automation, adds four real hours to the running session's existing shutdown deadline.
.EXAMPLE
.\Extend-GiandoriaLab.ps1 -ExtensionMinutes 60 -SessionId '<recorded-session-guid>'
In Automation, adds one real hour only if that session is still running.
#>
[CmdletBinding()]
param(
    [ValidateRange(10,1440)][int]$ExtensionMinutes = 240,
    [guid]$SessionId = [guid]::Empty,
    [guid]$ControlJobId = [guid]::Empty
)
. "$PSScriptRoot\LabControl.ps1"
$ControlJobId = Resolve-ControlJobId $ControlJobId
Extend-ControlLab -SessionId $SessionId -ExtensionMinutes $ExtensionMinutes -ControlJobId $ControlJobId
