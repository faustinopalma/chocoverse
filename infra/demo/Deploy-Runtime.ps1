#Requires -Version 7.4
param([ValidateSet('Validate','Deploy')][string]$Stage='Validate')
. "$PSScriptRoot\common.ps1"
Initialize-DemoContext
$outputs=Get-DemoDeploymentOutputs
$image=Get-Content -Raw (Join-Path $script:DemoLocal 'business-image.json') | ConvertFrom-Json
$fabric=Get-Content -Raw (Join-Path $script:DemoLocal 'business-fabric.json') | ConvertFrom-Json
$foundry=Get-Content -Raw (Join-Path $script:DemoLocal 'business-foundry-target.json') | ConvertFrom-Json
$automation=Get-Content -Raw (Join-Path $script:DemoLocal 'automation-deployment.json') | ConvertFrom-Json
$shared=Get-StackOutputs -Location 'swedencentral'
if ($shared.FoundryName -ne $foundry.name -or $shared.ResourceGroupName -ne $foundry.group) { throw 'Shared model scope changed.' }
$identity=Invoke-AzJson -Arguments @('identity','show','--resource-group','rg-giandoria-core-demo','--name','id-giandoria-runtime-demo')
Assert-DemoOwnership $identity
if ($identity.principalId -ne $fabric.runtimePrincipalId) { throw 'Runtime identity changed after Fabric configuration.' }
$models=@(Invoke-AzJson -Arguments @('cognitiveservices','account','deployment','list','--resource-group',$foundry.group,'--name',$foundry.name))
$model=@($models | Where-Object { $_.name -eq 'gpt-5.6-terra' -and $_.properties.provisioningState -eq 'Succeeded' })
if ($model.Count -ne 1 -or $model[0].properties.model.version -ne '2026-07-09') { throw 'Pinned shared model unavailable.' }
if ($image.image -notmatch "^$($outputs.registryName.value)\.azurecr\.io/giandoria-business@sha256:[a-f0-9]{64}$") {
    throw 'Runtime image is not pinned to the existing registry digest.'
}
$existing=@(Invoke-AzJson -Arguments @('resource','list','--resource-group','rg-giandoria-core-demo','--resource-type','Microsoft.App/jobs'))
foreach($job in $existing | Where-Object name -eq 'job-giandoria-universe-demo') { Assert-DemoOwnership $job }
$parameters=@(
    "image=$($image.image)","stateAccountName=$($outputs.stateAccountName.value)","registryName=$($outputs.registryName.value)",
    "environmentName=$($outputs.environmentName.value)","automationPrincipalId=$($automation.properties.outputs.principalId.value)",
    "runtimePrincipalId=$($identity.principalId)",
    "foundryGroup=$($foundry.group)","foundryName=$($foundry.name)","model=$($model[0].name)",
    "modelVersion=$($model[0].properties.model.version)","streamNamespace=$($fabric.streamNamespace)","streamHub=$($fabric.streamHub)"
)
$template=Join-Path $PSScriptRoot 'runtime.bicep'
if ($Stage -eq 'Validate') {
    Invoke-AzJson -Arguments @('bicep','build','--file',$template,'--outfile',(Join-Path $script:DemoLocal 'runtime-template.json')) | Out-Null
    Invoke-AzJson -Arguments (@('deployment','sub','validate','--location','swedencentral','--template-file',$template,'--parameters')+$parameters) | Out-Null
    $whatif=Invoke-AzJson -Arguments (@('deployment','sub','what-if','--location','swedencentral','--template-file',$template,'--parameters')+$parameters+@('--no-pretty-print'))
    Write-JsonFile $whatif (Join-Path $script:DemoLocal 'runtime-what-if.json')
    Write-Host 'Runtime compiled and ARM validation/what-if completed; no job started.'
    return
}
$result=Invoke-AzJson -Arguments (@('deployment','sub','create','--name','giandoria-demo-runtime','--location','swedencentral','--template-file',$template,'--parameters')+$parameters)
Write-JsonFile $result (Join-Path $script:DemoLocal 'runtime-deployment.json')
Write-Host 'Manual Consumption job deployed; no execution started.'
