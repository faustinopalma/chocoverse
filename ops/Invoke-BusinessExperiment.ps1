#Requires -Version 7.4
[CmdletBinding()]
param(
    [ValidateRange(1,17544)][int]$MinimumTick=384,
    [ValidateRange(1,17544)][int]$TargetTick=384,
    [string]$PreviousLedger
)
. "$PSScriptRoot\..\infra\demo\common.ps1"
Initialize-DemoContext
$deployment=Get-Content -Raw (Join-Path $script:DemoLocal 'runtime-deployment.json') | ConvertFrom-Json
$jobId=$deployment.properties.outputs.jobId.value
$expected="$script:DemoSubscriptionScope/resourceGroups/rg-giandoria-core-demo/providers/Microsoft.App/jobs/job-giandoria-universe-demo"
if ($jobId -ine $expected) { throw 'Unexpected recorded runtime Job.' }
$job=Invoke-DemoArm GET "${jobId}?api-version=2026-01-01"
Assert-DemoOwnership $job
$before=Invoke-DemoArm GET "$jobId/executions?api-version=2026-01-01"
if (Get-Value $before 'nextLink') { throw 'Execution pagination requires explicit handling.' }
if (@($before.value | Where-Object {$_.properties.status -notin @('Succeeded','Failed','Stopped')}).Count) {
    throw 'A business execution is already active.'
}
$previous=@($before.value | ForEach-Object {$_.name})
$session=[guid]::NewGuid()
$control=Join-Path $PSScriptRoot 'Invoke-LabControl.ps1'
$capacity=@(Invoke-AzJson -Arguments @('resource','list','--resource-group','rg-giandoria-fabric-demo',
    '--resource-type','Microsoft.Fabric/capacities'))
if ($capacity.Count -ne 1) { throw 'Expected one existing F4.' }
Assert-DemoOwnership $capacity[0]
$capacityId=$capacity[0].id
$current=Invoke-DemoArm GET "${capacityId}?api-version=2023-11-01"
if ($current.properties.state -ne 'Paused' -or $current.sku.name -ne 'F4') { throw 'Expected Paused F4.' }
$report=[ordered]@{sessionId=$session.ToString();status='Running';capacityState='Unknown';execution=$null}
$stateAccount=(Get-DemoDeploymentOutputs).stateAccountName.value
$storageToken=Invoke-AzJson -Arguments @('account','get-access-token','--resource','https://storage.azure.com/')
$storageHeaders=@{Authorization="Bearer $($storageToken.accessToken)";'x-ms-version'='2023-11-03'}
function Get-BusinessProgress {
    $r=Invoke-RecordedWebRequest -Uri "https://$stateAccount.blob.core.windows.net/lab-state/business-summary.json" `
        -Headers $storageHeaders -SkipHttpErrorCheck
    if ($r.StatusCode -eq 404) { return 0 }
    if ($r.StatusCode -ne 200) { throw "Progress read failed: HTTP $($r.StatusCode)." }
    $summary=$r.Content | ConvertFrom-Json
    Write-JsonFile $summary (Join-Path $script:DemoLocal 'business-observed-summary.json')
    return [int]$summary.tick
}
try {
    Invoke-RecordedNative -FilePath 'pwsh' -Arguments @('-NoProfile','-File',$control,'-Action','Start',
        '-SessionId',$session.ToString(),'-MaxWallMinutes','120','-Mode','Batch') -TimeoutSeconds 750
    $sessionDeadline=[datetime]::UtcNow.AddMinutes(105)
    $lastTick=Get-BusinessProgress
    $batch=0
    do {
        $batch++
        $deadline=[datetime]::UtcNow.AddMinutes(12)
        do {
            $executions=Invoke-DemoArm GET "$jobId/executions?api-version=2026-01-01"
            if (Get-Value $executions 'nextLink') { throw 'Execution pagination requires explicit handling.' }
            $new=@($executions.value | Where-Object name -notin $previous)
            if ($new.Count -gt 1) { throw 'Unexpected concurrent business executions.' }
            if ($new.Count -eq 1) {
                $report.execution=$new[0].name
                Write-JsonFile $new[0] (Join-Path $script:DemoLocal 'business-last-execution.json')
                Write-JsonFile $new[0] (Join-Path $script:DemoLocal "business-execution-$($new[0].name).json")
                if ($new[0].properties.status -in @('Succeeded','Failed','Stopped')) { break }
            }
            $tick=Get-BusinessProgress
            Write-Host "Observed batch $batch, tick $tick / $TargetTick."
            Start-Sleep -Seconds 20
        } while ([datetime]::UtcNow -lt $deadline)
        if ($new.Count -ne 1 -or $new[0].properties.status -ne 'Succeeded') {
            throw 'Business execution did not succeed; inspect retained execution and console records.'
        }
        $tick=Get-BusinessProgress
        if ($tick -le $lastTick -and $tick -lt $TargetTick) { throw 'Successful job made no business progress.' }
        Write-Host "Completed batch $batch, tick $tick / $TargetTick."
        $lastTick=$tick
        if ($tick -ge $TargetTick) { break }
        if ([datetime]::UtcNow -ge $sessionDeadline -or $batch -ge 48) {
            throw 'Collection session limit reached; checkpoint retained for continuation.'
        }
        $previous=@($executions.value | ForEach-Object {$_.name})
        $active=Invoke-RecordedWebRequest -Uri "https://$stateAccount.blob.core.windows.net/lab-state/active-session.json" `
            -Headers $storageHeaders
        $activeSession=$active.Content|ConvertFrom-Json
        if ($activeSession.id -ne $session.ToString() -or $activeSession.desired -ne 'Running') {
            throw 'Collection session no longer owns activation.'
        }
        $token=Invoke-AzJson -Arguments @('account','get-access-token','--resource','https://management.azure.com/')
        Invoke-RecordedWebRequest -Method POST -Uri "https://management.azure.com$jobId/start?api-version=2026-01-01" `
            -Headers @{Authorization="Bearer $($token.accessToken)"} -ContentType 'application/json' | Out-Null
    } while ($true)
    $oldAccount=$env:GIANDORIA_STATE_ACCOUNT
    $env:GIANDORIA_STATE_ACCOUNT=$stateAccount
    try {
        $arguments=@('-m','giandoria.business_verify','--minimum-tick',"$MinimumTick")
        if ($PreviousLedger) { $arguments+=@('--previous-ledger',$PreviousLedger) }
        Invoke-RecordedNative -FilePath (Join-Path $script:RepoRoot '.venv\Scripts\python.exe') `
            -Arguments $arguments -TimeoutSeconds 900
    }
    finally { $env:GIANDORIA_STATE_ACCOUNT=$oldAccount }
    $report.status='Succeeded'
}
catch {
    $report.status='Failed'
    throw
}
finally {
    try {
        Invoke-RecordedNative -FilePath 'pwsh' -Arguments @('-NoProfile','-File',$control,'-Action','Stop',
            '-SessionId',$session.ToString(),'-Force') -TimeoutSeconds 750
    }
    finally {
        $current=Invoke-DemoArm GET "${capacityId}?api-version=2023-11-01"
        $report.capacityState=$current.properties.state
        $executions=Invoke-DemoArm GET "$jobId/executions?api-version=2026-01-01"
        Write-JsonFile $report (Join-Path $script:DemoLocal "business-experiment-$session.json")
        if ($current.properties.state -ne 'Paused' -or
            @($executions.value | Where-Object {$_.properties.status -notin @('Succeeded','Failed','Stopped')}).Count) {
            throw 'Business cleanup did not independently confirm Paused F4 and terminal executions.'
        }
    }
}
Write-Host 'Business experiment verified; F4 Paused and no active runtime execution.'
