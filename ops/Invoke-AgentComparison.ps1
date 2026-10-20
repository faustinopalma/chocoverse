#Requires -Version 7.4
[CmdletBinding()]
param([Parameter(Mandatory)][ValidatePattern('^[a-z0-9][a-z0-9-]{0,63}$')][string]$Experiment)

. "$PSScriptRoot\..\infra\demo\common.ps1"
Initialize-DemoContext
$directory = Join-Path $script:DemoLocal "agent-comparisons\$Experiment"
if (Test-Path -LiteralPath $directory) { throw 'Experiment already reserved; inspect it before a new explicit trial.' }
$foundry = Get-Content -LiteralPath (Join-Path $script:DemoLocal 'business-foundry-target.json') -Raw |
    ConvertFrom-Json
$runtime = Get-Content -LiteralPath (Join-Path $script:DemoLocal 'runtime-deployment.json') -Raw |
    ConvertFrom-Json
$parameters = $runtime.properties.parameters
$model = Invoke-DemoArm GET "$($foundry.id)/deployments/$($parameters.model.value)?api-version=2024-10-01"
if ($model.properties.provisioningState -ne 'Succeeded' -or
    $model.properties.model.version -ne $parameters.modelVersion.value) {
    throw 'The existing model deployment differs from the recorded runtime contract.'
}
$control = Join-Path $PSScriptRoot 'Invoke-LabControl.ps1'
$session = [guid]::NewGuid().ToString()
$python = Join-Path $script:RepoRoot '.venv\Scripts\python.exe'
try {
    Invoke-RecordedNative -FilePath pwsh -Arguments @(
        '-NoProfile','-File',$control,'-Action','Start','-SessionId',$session,'-Mode','Analysis','-MaxWallMinutes','45'
    ) -TimeoutSeconds 780
    Invoke-RecordedNative -FilePath $python -Arguments @(
        '-m','giandoria.agent_comparison','--experiment',$Experiment
    ) -TimeoutSeconds 1900
}
finally {
    Invoke-RecordedNative -FilePath pwsh -Arguments @(
        '-NoProfile','-File',$control,'-Action','Stop','-SessionId',$session,'-Force'
    ) -TimeoutSeconds 780
    $capacity = Invoke-DemoArm GET "$script:DemoSubscriptionScope/resourceGroups/rg-giandoria-fabric-demo/providers/Microsoft.Fabric/capacities/fcgiandoriademoepo4?api-version=2023-11-01"
    $executions = Invoke-DemoArm GET "$script:DemoSubscriptionScope/resourceGroups/rg-giandoria-core-demo/providers/Microsoft.App/jobs/job-giandoria-universe-demo/executions?api-version=2024-03-01"
    $running = @($executions.value | Where-Object { $_.properties.status -in @('Running','Pending','Processing') })
    if ($capacity.properties.state -ne 'Paused' -or $running.Count) {
        throw 'Experiment cleanup did not verify paused capacity and terminal workers.'
    }
}
