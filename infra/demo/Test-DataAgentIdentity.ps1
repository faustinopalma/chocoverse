#Requires -Version 7.4
. "$PSScriptRoot\common.ps1"
Initialize-DemoContext
$outputs = Get-DemoDeploymentOutputs
$configPath = Join-Path $script:DemoLocal 'data-agent-service.json'
$config = Get-Content -Raw $configPath | ConvertFrom-Json
$identity = Get-Content -Raw (Join-Path $script:DemoLocal 'data-agent-identity.json') | ConvertFrom-Json
if ($config.clientId -ne $identity.clientId -or $config.principalId -ne $identity.principalId -or
    $config.workspaceId -eq $config.originalWorkspaceId) { throw 'Service identity configuration changed.' }
$job = Invoke-AzJson -Arguments @('containerapp','job','show','--resource-group','rg-giandoria-core-demo',
    '--name','job-giandoria-universe-demo')
Assert-DemoOwnership $job
if (@($job.properties.template.containers).Count -ne 1) { throw 'Expected exactly one runtime container.' }
$managed = @($job.identity.userAssignedIdentities.PSObject.Properties.Value)
if ($managed.Count -ne 1 -or $managed[0].clientId -ne $config.managedIdentityClientId) {
    throw 'Job managed identity differs from the exact federation subject.'
}
$image = Get-Content -Raw (Join-Path $script:DemoLocal 'business-image.json') | ConvertFrom-Json
if ($image.image -notmatch "^$([regex]::Escape($outputs.registryName.value))\.azurecr\.io/giandoria-business@sha256:[a-f0-9]{64}$") {
    throw 'Probe image must use the existing registry and a pinned digest.'
}
Invoke-AzJson -Arguments @('storage','blob','upload','--auth-mode','login','--account-name',$outputs.stateAccountName.value,
    '--container-name','lab-state','--name','data-agent-service.json','--file',$configPath,'--overwrite','true') | Out-Null
$container = $job.properties.template.containers[0]
$container.image = $image.image
$container | Add-Member -NotePropertyName command -NotePropertyValue @('python','-m','giandoria.data_agent_auth','probe') -Force
$container | Add-Member -NotePropertyName args -NotePropertyValue @() -Force
$templatePath = Join-Path $script:DemoLocal 'data-agent-probe-template.json'
Write-JsonFile @{containers=@($container)} $templatePath
$execution = $null
$terminal = $false
try {
    $execution = Invoke-AzJson -Arguments @('containerapp','job','start','--resource-group','rg-giandoria-core-demo',
        '--name','job-giandoria-universe-demo','--yaml',$templatePath)
    Write-JsonFile $execution (Join-Path $script:DemoLocal 'data-agent-probe-execution.json')
    if ($execution.name -notmatch '^job-giandoria-universe-demo-[a-z0-9]+$') { throw 'Unexpected probe execution identity.' }
    $until = [datetime]::UtcNow.AddMinutes(8)
    do {
        $state = Invoke-DemoArm GET "$($execution.id)?api-version=2024-03-01"
        if ($state.properties.status -in @('Succeeded','Failed','Stopped')) {
            $terminal = $true
            Write-JsonFile $state (Join-Path $script:DemoLocal 'data-agent-probe-result.json')
            if ($state.properties.status -ne 'Succeeded') {
                throw "Data Agent identity probe $($state.properties.status); inspect its execution logs."
            }
            Write-Host 'Cloud MI-to-application exchange, original-workspace denial and real Data Agent answer succeeded.'
            return
        }
        Start-Sleep -Seconds 10
    } while ([datetime]::UtcNow -lt $until)
    throw 'Data Agent identity probe exceeded its eight-minute execution limit.'
}
finally {
    if ($execution -and -not $terminal) {
        Invoke-AzJson -Arguments @('containerapp','job','stop','--resource-group','rg-giandoria-core-demo',
            '--name','job-giandoria-universe-demo','--job-execution-name',$execution.name) | Out-Null
    }
}
