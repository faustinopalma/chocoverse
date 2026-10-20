#Requires -Version 7.4
$ErrorActionPreference='Stop'
$global:FakeSession=$null
$global:FakeVersion=0
$global:FakeCapacity='Paused'
$global:FakeSchedule=$false
$global:FailSchedule=$false
$global:CancelDuringResume=$false
$global:PSPrivateMetadata=@{JobId=[guid]::NewGuid()}
$global:FakeRuntimeJob=$false
$global:FakeRuntimeStarted=$false
$global:FakeWorkerState='Running'
$global:FakeStopReads=0
$global:FakeConflict=$false
$global:FakeObjectConfig=$false
$global:FakeControllerStatus='Running'
$global:FakeBindings=@{}
$global:FakeSchedules=@{}
$global:FakeInvalidSchedule=$false
$global:FakeDrainGeneration=''
$global:FakeWorkerStarts=0
$global:FakeWorkerStops=0
$global:ExtendOnConflict=$false
$global:CancelDuringDrain=$false
function Disable-AzContextAutosave { param($Scope) }
function Connect-AzAccount { param([switch]$Identity) }
function Set-AzContext { param($SubscriptionId,$Tenant) }
function Get-AzAccessToken { param($ResourceUrl,[switch]$AsSecureString); return @{Token='offline-test'} }
function Get-AutomationVariable {
    param($Name)
    $config=@{
        project='giandoria';location='swedencentral';subscriptionId='test';tenantId='test'
        automationId='/subscriptions/test/aa';capacityId='/subscriptions/test/f4'
        stateAccount='stgiandoriatest';runtimeJobId=$(if ($global:FakeRuntimeJob) {'/subscriptions/test/runtime'} else {''})
    }
    if ($global:FakeObjectConfig) { return $config }
    return ($config | ConvertTo-Json)
}
function Start-Sleep { param($Seconds,$Milliseconds) }
function Write-Verbose { param($Message,[switch]$Verbose) }
function Invoke-WebRequest {
    param($Uri,$Method,$Headers,$Body,$ContentType,$SkipHttpErrorCheck,$TimeoutSec,$MaximumRedirection)
    $code=200; $content='{}'
    if ($Uri -like '*active-session.json') {
        if ($Method -eq 'GET') {
            if ($global:FakeSession) { $content=$global:FakeSession | ConvertTo-Json } else { $code=404 }
        } else {
            if ($global:FakeConflict) {
                $global:FakeConflict=$false
                if ($global:ExtendOnConflict) {
                    $global:FakeSession.expiresAt=[datetimeoffset]::UtcNow.AddHours(4).ToString('o')
                    $global:FakeVersion++
                    $global:ExtendOnConflict=$false
                }
                $code=412
            }
            elseif (($Headers.ContainsKey('If-Match') -and $Headers['If-Match'] -ne "v$global:FakeVersion") -or
                ($Headers.ContainsKey('If-None-Match') -and $global:FakeSession)) { $code=412 }
            else { $global:FakeSession=$Body | ConvertFrom-Json -AsHashtable; $global:FakeVersion++; $code=201 }
        }
    }
    elseif ($Uri -like '*/schedules/*') {
        if ($global:FailSchedule) { $code=403 }
        elseif ($Method -eq 'PUT') {
            $record=$Body|ConvertFrom-Json -AsHashtable
            if ($global:FakeInvalidSchedule) {
                $record.properties.startTime=([datetimeoffset]$record.properties.startTime).AddMinutes(-1).ToString('o')
            }
            $global:FakeSchedules[$Uri]=$record|ConvertTo-Json
            $global:FakeSchedule=$true
        }
        else { $content=$global:FakeSchedules[$Uri] }
    }
    elseif ($Uri -like '*/jobSchedules/*') {
        if ($Method -eq 'PUT') { $global:FakeBindings[$Uri]=$Body }
        else { $content=$global:FakeBindings[$Uri] }
    }
    elseif ($Uri -like '*/resume?*') {
        if (-not $global:FakeSchedule) { throw 'Resumed before arming shutdown.' }
        if ($global:CancelDuringResume) {
            & $global:FakeStopPath -SessionId $global:FakeSession.id -Force 'True' 6>$null | Out-Null
            if ($global:FakeSession.state -ne 'Stopping') { throw 'Stop released a session with its starter still active.' }
        }
        $global:FakeCapacity='Active';$code=202
    }
    elseif ($Uri -like '*/suspend?*') { $global:FakeCapacity='Paused';$code=202 }
    elseif ($Uri -like '*/f4?*') {
        $content=@{tags=@{project='giandoria';env='demo'};sku=@{name='F4'};properties=@{state=$global:FakeCapacity}} | ConvertTo-Json
    }
    elseif ($Uri -like '*/jobs/*') { $content=@{properties=@{status=$global:FakeControllerStatus}} | ConvertTo-Json }
    elseif ($Uri -like '*/runtime/start?*') {
        if ($ContentType -ne 'application/json') { throw 'Job start requires JSON content type even without a body.' }
        $global:FakeRuntimeStarted=$true
        $global:FakeWorkerStarts++
        $global:FakeWorkerState='Running'
        $code=202
    }
    elseif ($Uri -like '*/runtime/executions?*') {
        $global:FakeStopReads++
        if ($global:CancelDuringDrain) {
            $global:CancelDuringDrain=$false
            & $global:FakeStopPath -SessionId $global:FakeSession.id -Force 'True' 6>$null | Out-Null
        }
        if ($global:FakeDrainGeneration -and $global:FakeSession.workerGeneration -ne $global:FakeDrainGeneration) {
            $global:FakeWorkerState='Succeeded'
        }
        $content=@{value=@(@{properties=@{status=$global:FakeWorkerState}})} | ConvertTo-Json -Depth 5
    }
    elseif ($Uri -like '*/runtime/stop?*') { $global:FakeWorkerState='Stopped';$global:FakeWorkerStops++;$code=202 }
    return [pscustomobject]@{StatusCode=$code;Content=$content;Headers=@{ETag=@("v$global:FakeVersion")}}
}
$start=Join-Path $PSScriptRoot '..\ops\automation\Start-GiandoriaLab.ps1'
$extend=Join-Path $PSScriptRoot '..\ops\automation\Extend-GiandoriaLab.ps1'
$stop=Join-Path $PSScriptRoot '..\ops\automation\Stop-GiandoriaLab.ps1'
$global:FakeStopPath=$stop
$id=[guid]::NewGuid()
$startOutput=& $start -SessionId $id -ControlJobId ([guid]::NewGuid()) 6>$null
if (($startOutput -join "`n") -notmatch '240 REAL minutes' -or
    ($startOutput -join "`n") -notmatch 'Speed=8760 simulated seconds per REAL second' -or
    ($startOutput -join "`n") -notmatch 'Automatic shutdown UTC:') { throw 'Start output does not explain effective duration, speed and deadline.' }
if ($global:FakeCapacity -ne 'Active' -or $global:FakeSession.state -ne 'Running') { throw 'Start did not complete.' }
if ($global:FakeSession.speed -ne 8760 -or $global:FakeSession.mode -ne 'Continuous') {
    throw 'Default Start does not request paced continuous operation.'
}
$remaining=([datetimeoffset]::Parse($global:FakeSession.expiresAt)-[datetimeoffset]::UtcNow).TotalMinutes
if ($remaining -lt 239 -or $remaining -gt 240) { throw 'Default session is not four hours.' }
foreach ($body in $global:FakeSchedules.Values) {
    $scheduledAt=[datetimeoffset](($body|ConvertFrom-Json -AsHashtable).properties.startTime)
    $expires=[datetimeoffset]$global:FakeSession.expiresAt
    if ($scheduledAt -lt $expires -or $scheduledAt -ge $expires.AddMinutes(1)) {
        throw 'Default shutdown schedule must round up by less than one minute, never down.'
    }
}
$readback=& {
    . "$PSScriptRoot\..\ops\automation\LabControl.ps1" 6>$null | Out-Null
    Get-ControlSession
}
if ($readback.value.expiresAt -isnot [string] -or
    [datetimeoffset]::Parse($readback.value.expiresAt) -ne [datetimeoffset]$global:FakeSession.expiresAt) {
    throw 'Session JSON parsing changed deadline precision or converted persisted timestamp strings.'
}
$caught=$false
try { & $start -SessionId ([guid]::NewGuid()) -ControlJobId ([guid]::NewGuid()) 6>$null | Out-Null }
catch {
    $caught=$true
    if ($_.Exception.Message -notmatch 'Extend-GiandoriaLab' -or $_.Exception.Message -notmatch 'no changes made') {
        throw 'Duplicate Start must explain how to extend and report that it made no changes.'
    }
}
if (-not $caught) { throw 'Concurrent start accepted.' }
& $stop -SessionId ([guid]::NewGuid()) 6>$null | Out-Null
if ($global:FakeCapacity -ne 'Active') { throw 'Stale session stopped current resources.' }
& $stop -SessionId $id 6>$null | Out-Null
$global:FakeConflict=$true
& $stop -SessionId $id 6>$null | Out-Null
if ($global:FakeCapacity -ne 'Paused' -or $global:FakeSession.state -ne 'Stopped') { throw 'Stop not idempotent.' }
$global:FailSchedule=$true
$caught=$false
try { & $start -SessionId ([guid]::NewGuid()) -ControlJobId ([guid]::NewGuid()) 6>$null | Out-Null } catch { $caught=$true }
if (-not $caught -or $global:FakeCapacity -ne 'Paused') { throw 'Failed schedule did not prevent paid activation.' }
$global:FailSchedule=$false; $global:CancelDuringResume=$true
$caught=$false
try { & $start -SessionId ([guid]::NewGuid()) -ControlJobId ([guid]::NewGuid()) 6>$null | Out-Null } catch { $caught=$true }
if (-not $caught -or $global:FakeCapacity -ne 'Paused' -or $global:FakeSession.state -ne 'Stopped' -or $global:FakeSession.startInProgress) {
    throw 'Cancellation during activation was not settled safely.'
}
$global:CancelDuringResume=$false; $global:FakeRuntimeJob=$true
$global:FakeObjectConfig=$true
$id=[guid]::NewGuid()
& $start -SessionId $id -ControlJobId ([guid]::NewGuid()) -MaxWallMinutes 10 6>$null | Out-Null
if (-not $global:FakeRuntimeStarted) { throw 'Configured runtime was not started.' }
& $stop -SessionId $id -Force 'True' 6>$null | Out-Null
if ($global:FakeWorkerState -ne 'Stopped' -or $global:FakeStopReads -lt 2 -or $global:FakeSession.state -ne 'Stopped') {
    throw 'Runtime shutdown was not independently read back.'
}
$global:FakeSession.stopClaims=@{other=[guid]::NewGuid().ToString()}
& $stop -SessionId $id -Force 'True' 6>$null | Out-Null
if ($global:FakeSession.state -ne 'Stopping') { throw 'Another active stop controller was ignored.' }
$caught=$false
try { & $start -SessionId ([guid]::NewGuid()) -ControlJobId ([guid]::NewGuid()) 6>$null | Out-Null } catch { $caught=$true }
if (-not $caught) { throw 'A new generation started before all stop controllers settled.' }
$global:FakeControllerStatus='Completed'
& $stop -Reconcile 'True' 6>$null | Out-Null
if ($global:FakeSession.state -ne 'Stopped' -or $global:FakeSession.stopClaims.Count) { throw 'Orphan shutdown claim was not reconciled.' }
$id=[guid]::NewGuid()
& $start -SessionId $id -ControlJobId ([guid]::NewGuid()) -MaxWallMinutes 10 6>$null | Out-Null
$global:FakeSession.expiresAt=[datetimeoffset]::UtcNow.AddMinutes(-1).ToString('o')
& $stop -Reconcile 'True' 6>$null | Out-Null
if ($global:FakeSession.state -ne 'Stopped' -or $global:FakeCapacity -ne 'Paused') { throw 'Expired session was not stopped.' }
$global:FakeRuntimeStarted=$false
$analysisOutput=& $start -MaxWallMinutes 10 -Speed 730 -Mode Analysis 6>$null
if (($analysisOutput -join "`n") -notmatch 'no company time advances. Speed does not apply') {
    throw 'Analysis output misleadingly suggests Speed generates company activity.'
}
if ($global:FakeRuntimeStarted -or $global:FakeSession.speed -ne 730 -or $global:FakeSession.mode -ne 'Analysis') {
    throw 'Analysis-only Start invoked simulation or lost the requested speed.'
}
& $stop 6>$null | Out-Null
if ($global:FakeSession.state -ne 'Stopped') { throw 'Portal Stop did not resolve the active session.' }

& $start -Mode Continuous -MaxWallMinutes 240 6>$null | Out-Null
$id=[guid]$global:FakeSession.id
$oldExpiry=[datetimeoffset]::Parse($global:FakeSession.expiresAt)
$oldGeneration=$global:FakeSession.workerGeneration
$oldStarted=$global:FakeSession.startedAt
$beforeStarts=$global:FakeWorkerStarts
$beforeStops=$global:FakeWorkerStops
$global:FakeDrainGeneration=$oldGeneration
& $extend -ExtensionMinutes 240 6>$null | Out-Null
if ([datetimeoffset]::Parse($global:FakeSession.expiresAt) -ne $oldExpiry.AddMinutes(240) -or
    $global:FakeSession.id -ne $id.ToString() -or $global:FakeSession.startedAt -ne $oldStarted -or
    $global:FakeSession.speed -ne 8760 -or $global:FakeSession.mode -ne 'Continuous' -or
    $global:FakeSession.workerGeneration -eq $oldGeneration -or $global:FakeSession.startInProgress -or
    $global:FakeCapacity -ne 'Active' -or $global:FakeWorkerStarts -ne $beforeStarts+1 -or
    $global:FakeWorkerStops -ne $beforeStops) { throw 'Extension did not preserve session and checkpoint-drain the worker.' }
$global:FakeDrainGeneration=''
& $stop -SessionId $id -IfExpired True 6>$null | Out-Null
if ($global:FakeSession.desired -ne 'Running' -or $global:FakeCapacity -ne 'Active') {
    throw 'Stale scheduled shutdown ignored the extended deadline.'
}
$expiry=$global:FakeSession.expiresAt
$generation=$global:FakeSession.workerGeneration
$global:FailSchedule=$true
$caught=$false
try { & $extend -SessionId $id 6>$null | Out-Null } catch { $caught=$true }
$global:FailSchedule=$false
if (-not $caught -or $global:FakeSession.expiresAt -ne $expiry -or
    $global:FakeSession.workerGeneration -ne $generation -or $global:FakeCapacity -ne 'Active') {
    throw 'Failed extension schedule changed the existing deadline or stopped a healthy session.'
}
foreach ($parameters in @(@{ExtensionMinutes=1440},@{SessionId=[guid]::NewGuid()},@{ExtensionMinutes=9})) {
    $caught=$false
    try { & $extend @parameters 6>$null | Out-Null } catch { $caught=$true }
    if (-not $caught -or $global:FakeSession.expiresAt -ne $expiry) { throw 'Invalid/stale/over-limit extension was accepted.' }
}
$global:FakeSession.expiresAt=[datetimeoffset]::UtcNow.AddMinutes(-1).ToString('o')
$global:FakeConflict=$true;$global:ExtendOnConflict=$true
& $stop -SessionId $id -IfExpired True 6>$null | Out-Null
if ($global:FakeSession.desired -ne 'Running' -or $global:FakeCapacity -ne 'Active') {
    throw 'Scheduled Stop failed to recheck expiry after an ETag extension race.'
}
& $stop -SessionId $id -Force True 6>$null | Out-Null
& $start -Mode Analysis 6>$null | Out-Null
$beforeStarts=$global:FakeWorkerStarts
& $extend -ExtensionMinutes 60 6>$null | Out-Null
if ($global:FakeWorkerStarts -ne $beforeStarts -or $global:FakeSession.mode -ne 'Analysis') {
    throw 'Analysis extension generated a business worker.'
}
& $stop -Force True 6>$null | Out-Null
$caught=$false
try { & $extend 6>$null | Out-Null } catch { $caught=$true }
if (-not $caught) { throw 'Stopped session was resurrected by extension.' }
& $start -Mode Continuous 6>$null | Out-Null
$beforeStarts=$global:FakeWorkerStarts
$global:CancelDuringDrain=$true
$caught=$false
try { & $extend 6>$null | Out-Null } catch { $caught=$true }
if (-not $caught -or $global:FakeWorkerStarts -ne $beforeStarts -or
    $global:FakeSession.state -ne 'Stopped' -or $global:FakeCapacity -ne 'Paused') {
    throw 'Extension restarted a worker after concurrent Stop.'
}
Write-Host 'Four-hour defaults, guarded extensions, worker drain, deadline races and existing lifecycle regressions passed.'

& $start -Mode Analysis -ExtensionMinutes 60 -WarningVariable warnings 3>$null 6>$null | Out-Null
if (($warnings -join "`n") -notmatch 'ExtensionMinutes is ignored on Start') { throw 'Start silently ignored ExtensionMinutes.' }
$before=$global:FakeSession.expiresAt
& $start -Operation Extend -Speed 1 -Mode Continuous -MaxWallMinutes 10 -ExtensionMinutes 60 `
    -WarningVariable warnings 3>$null 6>$null | Out-Null
if (($warnings -join "`n") -notmatch 'Ignored on Extend' -or
    $global:FakeSession.mode -ne 'Analysis' -or $global:FakeSession.speed -ne 8760 -or
    [datetimeoffset]$global:FakeSession.expiresAt -ne ([datetimeoffset]$before).AddMinutes(60)) {
    throw 'Extend did not explain ignored inputs while retaining its effective settings.'
}
& $stop -Force True 6>$null | Out-Null
Write-Host 'Operator summaries, actionable duplicate Start and ignored-input warnings passed.'
& {
    . "$PSScriptRoot\..\ops\automation\LabControl.ps1" 6>$null | Out-Null
    foreach ($case in @(
        @{input='2030-01-01T12:00:00+00:00';expected='2030-01-01T12:00:00+00:00'}
        @{input='2030-01-01T12:00:00.0000001+00:00';expected='2030-01-01T12:01:00+00:00'}
        @{input='2030-01-01T23:59:59.9999999+00:00';expected='2030-01-02T00:00:00+00:00'}
        @{input='2030-01-01T14:00:30+02:00';expected='2030-01-01T12:01:00+00:00'}
    )) {
        $controller=[guid]::NewGuid()
        Set-ControlDeadline ([guid]::NewGuid().ToString()) ([datetimeoffset]$case.input) $controller
        $key=$controller.ToString('N')
        $stored=($global:FakeSchedules.GetEnumerator() | Where-Object {$_.Key -like "*${key}*"}).Value |
            ConvertFrom-Json -AsHashtable
        if ([datetimeoffset]$stored.properties.startTime -ne [datetimeoffset]$case.expected) {
            throw "UTC minute ceiling failed for $($case.input)."
        }
    }
    $global:FakeInvalidSchedule=$true
    $caught=$false
    try { Set-ControlDeadline ([guid]::NewGuid().ToString()) ([datetimeoffset]::UtcNow.AddHours(4)) ([guid]::NewGuid()) }
    catch {
        if ($_.Exception.Message -notmatch 'minute-aligned deadline') { throw }
        $caught=$true
    }
    finally { $global:FakeInvalidSchedule=$false }
    if (-not $caught -or $global:FakeCapacity -ne 'Paused') { throw 'Invalid persisted deadline was accepted.' }
}
Write-Host 'Minute-aligned UTC shutdown, fractional/offset/day-boundary cases and strict schedule readback passed.'
