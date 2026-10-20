#Requires -Version 7.4
. "$PSScriptRoot\..\infra\demo\common.ps1"
Initialize-DemoContext
$control = Join-Path $script:RepoRoot 'ops\Invoke-LabControl.ps1'
$session=[guid]::NewGuid().ToString()
$capacity=@(Invoke-AzJson -Arguments @('resource','list','--resource-group','rg-giandoria-fabric-demo','--resource-type','Microsoft.Fabric/capacities'))[0]
Assert-DemoOwnership $capacity
$stateAccount=(Get-DemoDeploymentOutputs).stateAccountName.value
$automation="$script:DemoSubscriptionScope/resourceGroups/rg-giandoria-ops-demo/providers/Microsoft.Automation/automationAccounts/aa-giandoria-demo"
$probeName="reconcile-test-$session"
$probeBinding=[guid]::NewGuid().ToString()
$probeCreated=$false
$bindingCreated=$false
function Get-DeadlineSession {
    $token=Invoke-AzJson -Arguments @('account','get-access-token','--resource','https://storage.azure.com/')
    $response=Invoke-RecordedWebRequest -Uri "https://$stateAccount.blob.core.windows.net/lab-state/active-session.json" `
        -Headers @{Authorization="Bearer $($token.accessToken)";'x-ms-version'='2023-11-03'}
    return $response.Content | ConvertFrom-Json -DateKind String
}
function Get-DeadlineItems {
    param([string]$Path)
    $page=$Path
    while ($page) {
        $list=Invoke-DemoArm GET $page
        $list.value
        $next=Get-Value $list 'nextLink'
        $page=if ($next) {
            $uri=[uri]$next
            if ($uri.Scheme -ne 'https' -or $uri.Host -ne 'management.azure.com') { throw 'Unexpected test pagination URL.' }
            $uri.PathAndQuery
        } else { '' }
    }
}
$report=@{sessionId=$session;automaticShutdownVerified=$false;startedAt=[datetime]::UtcNow.ToString('o')}
try {
    Invoke-RecordedNative pwsh @('-NoProfile','-File',$control,'-Action','Start','-SessionId',$session,'-MaxWallMinutes','10') -TimeoutSeconds 780
    $record=Get-DeadlineSession
    if ($record.id -ne $session -or $record.state -ne 'Running') { throw 'Test session did not become Running.' }
    $expires=[datetimeoffset]::Parse($record.expiresAt)
    $report.expectedExpiry=$record.expiresAt
    $token=Invoke-AzJson -Arguments @('account','get-access-token','--resource','https://management.azure.com/')
    $headers=@{Authorization="Bearer $($token.accessToken)"}
    $probeAt=[datetimeoffset]::UtcNow.AddMinutes(6)
    if ($probeAt -ge $expires) { throw 'Insufficient time for the scheduled reconciliation probe.' }
    $body=@{properties=@{startTime=$probeAt.ToString('o');frequency='OneTime';timeZone='UTC';isEnabled=$true}}|ConvertTo-Json
    Invoke-RecordedWebRequest -Method PUT -Uri "https://management.azure.com$automation/schedules/${probeName}?api-version=2024-10-23" `
        -Headers $headers -Body $body -ContentType 'application/json' | Out-Null
    $probeCreated=$true
    $body=@{properties=@{runbook=@{name='Stop-GiandoriaLab'};schedule=@{name=$probeName};parameters=@{Reconcile='True'}}}|ConvertTo-Json -Depth 5
    Invoke-RecordedWebRequest -Method PUT -Uri "https://management.azure.com$automation/jobSchedules/${probeBinding}?api-version=2024-10-23" `
        -Headers $headers -Body $body -ContentType 'application/json' | Out-Null
    $bindingCreated=$true
    $binding=Invoke-DemoArm GET "$automation/jobSchedules/${probeBinding}?api-version=2024-10-23"
    if ((Get-Value $binding 'properties.parameters.Reconcile') -ne 'True') { throw 'Reconciliation probe arguments were not retained.' }
    $until=$expires.AddMinutes(6)
    do {
        $actual=Invoke-DemoArm GET "$($capacity.id)?api-version=2023-11-01"
        if ($actual.properties.state -eq 'Paused') {
            if ([datetimeoffset]::UtcNow -lt $expires) { throw 'Capacity paused BEFORE the requested deadline.' }
            $record=Get-DeadlineSession
            if ($record.id -ne $session -or $record.state -ne 'Stopped') { throw 'Capacity paused without a matching completed session shutdown.' }
            $report.pausedObservedAt=[datetimeoffset]::UtcNow.ToString('o')
            $report.session=$record
            break
        }
        Start-Sleep -Seconds 15
    } while ([datetimeoffset]::UtcNow -lt $until)
    if (-not $report.ContainsKey('pausedObservedAt')) { throw 'Automatic shutdown was not confirmed within its bounded verification window.' }
    $jobs=@(Get-DeadlineItems "$automation/jobs?api-version=2024-10-23")
    $probes=@($jobs | Where-Object {$_.name -like "SCH_${probeBinding}_*"})
    if ($probes.Count -ne 1) { throw 'Expected exactly one scheduled reconciliation probe job.' }
    $probeJob=Invoke-DemoArm GET "$automation/jobs/$($probes[0].properties.jobId)?api-version=2024-10-23"
    $streams=@(Get-DeadlineItems "$automation/jobs/$($probes[0].properties.jobId)/streams?api-version=2024-10-23")
    if ($probeJob.properties.status -ne 'Completed' -or
        (Get-Value $probeJob 'properties.parameters.Reconcile') -ne 'True' -or
        [datetimeoffset]::Parse($probeJob.properties.endTime) -ge $expires -or
        -not @($streams | Where-Object {$_.properties.summary -eq 'Session remains within its deadline.'}).Count) {
        throw 'Scheduled reconciliation did not prove a successful no-op within the deadline.'
    }
    $report.reconciliationJob=$probeJob
    $report.reconciliationOutput=@($streams | Where-Object {$_.properties.streamType -in @('Output','Error','Warning')})
    $report.automaticShutdownVerified=$true
    Write-Host 'Scheduled reconciliation preserved the unexpired session; automatic shutdown occurred only after its deadline.'
}
finally {
    try {
        if (-not $report.automaticShutdownVerified) {
            try {
                Invoke-RecordedNative pwsh @('-NoProfile','-File',$control,'-Action','Stop','-SessionId',$session,'-Force') -TimeoutSeconds 780
            }
            finally {
                $actual=Invoke-DemoArm GET "$($capacity.id)?api-version=2023-11-01"
                if ($actual.properties.state -ne 'Paused') {
                    if ((Get-DeadlineSession).id -ne $session) { throw 'Another session owns the capacity; refusing emergency suspend.' }
                    Invoke-DemoArm POST "$($capacity.id)/suspend?api-version=2023-11-01" | Out-Null
                    $report.emergencySuspendRequested=$true
                }
            }
        }
    }
    finally {
        try {
            if ($bindingCreated) {
                Invoke-RecordedWebRequest -Method DELETE -Uri "https://management.azure.com$automation/jobSchedules/${probeBinding}?api-version=2024-10-23" -Headers $headers | Out-Null
            }
            if ($probeCreated) {
                Invoke-RecordedWebRequest -Method DELETE -Uri "https://management.azure.com$automation/schedules/${probeName}?api-version=2024-10-23" -Headers $headers | Out-Null
            }
        }
        finally {
            $report.finishedAt=[datetime]::UtcNow.ToString('o')
            Write-JsonFile $report (Join-Path $script:DemoLocal "automation-deadline-$session.json")
        }
    }
}
