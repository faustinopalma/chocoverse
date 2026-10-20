#Requires -Version 7.4
<#
.SYNOPSIS
    Deploys the shared Foundry account as a subscription-scope deployment stack.

.DESCRIPTION
    Steps:
      1. load .env and check the Azure CLI sign-in (tenant and subscription);
      2. register the Microsoft.CognitiveServices resource provider when needed;
      3. refresh model-plan.json with Resolve-ModelPlan.ps1 (skip with -SkipResolve);
      4. choose who gets the Foundry User role (default: the signed-in user);
      5. lint the Bicep files and build the parameter file;
      6. preview: what-if of the same template, plus the model deployments the stack would delete;
      7. validate the stack;
      8. ask for confirmation (skip with -Force), then create or update the stack.
    Deployment stacks have no what-if yet, so step 6 runs a what-if of a plain subscription deployment.

.PARAMETER Location
    Azure region. Defaults to SHARED_FOUNDRY_LOCATION, then to the region of model-plan.json, then swedencentral.

.PARAMETER SkipResolve
    Deploy model-plan.json as it is, without asking Azure for newer models or more quota.

.PARAMETER QuotaShare
    Passed to Resolve-ModelPlan.ps1: share of the free quota to take, from 0.01 to 1.

.PARAMETER WhatIfOnly
    Stop after the preview and the validation. Nothing is created.

.PARAMETER Force
    Do not ask for confirmation.

.EXAMPLE
    ./Deploy-SharedFoundry.ps1 -WhatIfOnly

.EXAMPLE
    ./Deploy-SharedFoundry.ps1 -Location swedencentral
#>
[CmdletBinding()]
param(
    [string]$Location,
    [switch]$SkipResolve,
    [ValidateRange(0.01, 1.0)][double]$QuotaShare = 1.0,
    [switch]$WhatIfOnly,
    [switch]$Force
)

. "$PSScriptRoot/common.ps1"

Import-DotEnv
Initialize-Tooling
$null = Assert-AzContext

$templateFile = Join-Path $script:InfraRoot 'main.bicep'
$paramFile = Join-Path $script:InfraRoot 'main.bicepparam'
$planPath = Join-Path $script:InfraRoot 'model-plan.json'

if (-not $Location) { $Location = $env:SHARED_FOUNDRY_LOCATION }
if (-not $Location -and (Test-Path -LiteralPath $planPath)) {
    $Location = (Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json -DateKind String).location
}
if (-not $Location) { $Location = 'swedencentral' }
$Location = $Location.ToLowerInvariant()
$stackName = Get-StackName $Location

Write-Step 'Checking the Microsoft.CognitiveServices resource provider'
$state = Invoke-AzJson -Arguments @('provider', 'show', '--namespace', 'Microsoft.CognitiveServices',
    '--query', 'registrationState')
if ($state -ne 'Registered') {
    Invoke-Az -Arguments @('provider', 'register', '--namespace', 'Microsoft.CognitiveServices', '--wait')
}
else {
    Write-Host 'Registered.'
}

if (-not $SkipResolve) {
    Write-Step 'Refreshing model-plan.json'
    & (Join-Path $PSScriptRoot 'Resolve-ModelPlan.ps1') -Location $Location -QuotaShare $QuotaShare
}
$plan = Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json -DateKind String
if ($plan.location -ne $Location) {
    throw "model-plan.json targets $($plan.location), not $Location. Run Resolve-ModelPlan.ps1 -Location $Location."
}
if (@($plan.deployments).Count -eq 0) { throw 'model-plan.json contains no deployments.' }

Write-Step 'Choosing who gets the Foundry User role'
if (-not $env:SHARED_FOUNDRY_USER_OBJECT_IDS -and -not $env:SHARED_FOUNDRY_GROUP_OBJECT_IDS) {
    $me = Invoke-AzJson -Arguments @('ad', 'signed-in-user', 'show', '--query', 'id') -AllowFailure
    if ($me) {
        $env:SHARED_FOUNDRY_USER_OBJECT_IDS = $me
        Write-Host "The signed-in user ($me). Set SHARED_FOUNDRY_USER_OBJECT_IDS in .env to change it."
    }
    else {
        Write-Warning 'No principal configured and the signed-in identity is not a user: nobody gets the role.'
    }
}
else {
    Write-Host "Users: $($env:SHARED_FOUNDRY_USER_OBJECT_IDS)  Groups: $($env:SHARED_FOUNDRY_GROUP_OBJECT_IDS)"
}

if (Get-Command bicep -ErrorAction SilentlyContinue) {
    Write-Step 'Linting the Bicep files'
    & bicep lint $templateFile
    if ($LASTEXITCODE -ne 0) { throw 'bicep lint reported errors.' }
    $null = & bicep build-params $paramFile --stdout
    if ($LASTEXITCODE -ne 0) { throw 'bicep build-params reported errors.' }
    Write-Host 'No errors.'
}

Write-Step "What-if in $Location (plain subscription deployment of the same template)"
Invoke-Az -Arguments @('deployment', 'sub', 'what-if', '--name', "shared-ai-$Location-whatif",
    '--location', $Location, '--template-file', $templateFile, '--parameters', $paramFile,
    '--exclude-change-types', 'Ignore', 'NoChange', '--only-show-errors')

$stackInfo = Get-StackOutputs -Location $Location
if ($stackInfo) {
    Write-Step 'Model deployments the stack update would delete'
    $wanted = @($plan.deployments | ForEach-Object { $_.name })
    $toDelete = foreach ($resource in $stackInfo.Stack.resources) {
        if ($resource.id -match '/providers/Microsoft\.CognitiveServices/accounts/[^/]+/deployments/([^/]+)$' -and
            $Matches[1] -notin $wanted) {
            $Matches[1]
        }
    }
    if ($toDelete) { Write-Warning "No longer in the plan, will be deleted: $($toDelete -join ', ')" }
    else { Write-Host 'None.' }
}

$stackArgs = @('--name', $stackName, '--location', $Location, '--template-file', $templateFile,
    '--parameters', $paramFile, '--action-on-unmanage', 'deleteResources', '--deny-settings-mode', 'none')

Write-Step 'Validating the deployment stack'
Invoke-Az -Arguments (@('stack', 'sub', 'validate') + $stackArgs + @('--only-show-errors', '--output', 'none'))
Write-Host 'Valid.'

if ($WhatIfOnly) {
    Write-Host "`nStopped after the preview (-WhatIfOnly). Nothing was created or changed." -ForegroundColor Green
    return
}

Write-Step 'Confirmation'
Write-Host "Stack:    $stackName (subscription scope, metadata stored in $Location)"
Write-Host "Models:   $(@($plan.deployments).Count) deployments of type $($plan.sku), sized from the free quota"
Write-Host 'Cost:     no fixed fee; usage is billed per token or per image when the models are called.'
Write-Host '          Tenant policies can add charges, for example Defender for AI per token after its trial.'
if (-not $Force) {
    $answer = Read-Host "Type 'deploy' to create or update the stack"
    if ($answer -ne 'deploy') {
        Write-Host 'Cancelled. Nothing was created or changed.'
        return
    }
}

Write-Step "Creating or updating $stackName (model deployments run one at a time; this can take a while)"
Invoke-Az -Arguments (@('stack', 'sub', 'create') + $stackArgs + @('--description',
        'Shared Foundry account and model deployments (infra/shared-foundry).', '--yes', '--only-show-errors',
        '--output', 'none'))

$outputs = (Get-StackOutputs -Location $Location).Stack.outputs
Write-Step 'Done'
Write-Host "Resource group: $($outputs.resourceGroupName.value)"
Write-Host "Account:        $($outputs.foundryName.value)"
Write-Host "Endpoint:       $($outputs.endpoint.value)"
foreach ($project in @($outputs.projects.value)) {
    Write-Host "Project:        $($project.name) -> $($project.endpoint)"
}
@($outputs.deployments.value) | Format-Table name, version, sku, capacity -AutoSize | Out-String -Width 200 |
    Write-Host
Write-Host 'New role assignments can take several minutes before data-plane calls succeed.'
