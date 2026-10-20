#Requires -Version 7.4
<#
.SYNOPSIS
    Deletes the shared Foundry stack, its resource group and the soft-deleted account.

.DESCRIPTION
    The stack is deleted with action-on-unmanage deleteAll: Azure deletes the managed resource group and
    everything in it, including projects, model deployments and resources that other repositories added.
    The script lists that unmanaged content first and asks you to type the account name.
    Afterwards it purges the soft-deleted account. Without the purge, Azure keeps the deleted account
    (with its name) for the soft-delete retention period.

.PARAMETER Location
    Azure region of the stack. Defaults to SHARED_FOUNDRY_LOCATION, then to the region of model-plan.json.

.PARAMETER KeepSoftDeleted
    Skip the purge, so the account can still be recovered during the retention period.

.PARAMETER Force
    Do not ask for confirmation.

.EXAMPLE
    ./Remove-SharedFoundry.ps1 -Location swedencentral
#>
[CmdletBinding()]
param(
    [string]$Location,
    [switch]$KeepSoftDeleted,
    [switch]$Force
)

. "$PSScriptRoot/common.ps1"

Import-DotEnv
Initialize-Tooling
$azAccount = Assert-AzContext

$planPath = Join-Path $script:InfraRoot 'model-plan.json'
if (-not $Location) { $Location = $env:SHARED_FOUNDRY_LOCATION }
if (-not $Location -and (Test-Path -LiteralPath $planPath)) {
    $Location = (Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json -DateKind String).location
}
if (-not $Location) { throw 'Pass -Location or set SHARED_FOUNDRY_LOCATION.' }
$Location = $Location.ToLowerInvariant()
$stackName = Get-StackName $Location

$info = Get-StackOutputs -Location $Location
if (-not $info) { throw "There is no deployment stack named $stackName in this subscription." }
$resourceGroup = $info.ResourceGroupName
$foundry = $info.FoundryName
$managedIds = @($info.Stack.resources | ForEach-Object { $_.id.ToLowerInvariant() })

Write-Step 'Looking for content that the stack does not manage'
$unmanaged = [Collections.Generic.List[string]]::new()
foreach ($resource in @(Invoke-AzJson -AllowFailure -Arguments @('resource', 'list', '--resource-group', $resourceGroup))) {
    if ($resource -and $managedIds -notcontains $resource.id.ToLowerInvariant()) {
        $unmanaged.Add("resource   $($resource.type) $($resource.name)")
    }
}
foreach ($deployment in @(Invoke-AzJson -AllowFailure -Arguments @('cognitiveservices', 'account', 'deployment',
            'list', '--resource-group', $resourceGroup, '--name', $foundry))) {
    if ($deployment -and $managedIds -notcontains $deployment.id.ToLowerInvariant()) {
        $unmanaged.Add("deployment $($deployment.name)")
    }
}
$projectsUrl = "https://management.azure.com/subscriptions/$($azAccount.id)/resourceGroups/$resourceGroup" +
    "/providers/Microsoft.CognitiveServices/accounts/$foundry/projects?api-version=2025-12-01"
$projects = Invoke-AzJson -AllowFailure -Arguments @('rest', '--method', 'get', '--url', $projectsUrl)
foreach ($project in @(Get-Value $projects 'value')) {
    if ($project -and $managedIds -notcontains $project.id.ToLowerInvariant()) {
        $unmanaged.Add("project    $($project.name)")
    }
}
if ($unmanaged.Count -gt 0) {
    Write-Warning 'The stack does not manage these items, but deleting the resource group deletes them too:'
    $unmanaged | ForEach-Object { Write-Host "  - $_" }
}
else {
    Write-Host 'None: everything in the resource group belongs to the stack.'
}

if (-not $Force) {
    Write-Host ''
    Write-Host "This deletes stack $stackName, resource group $resourceGroup and account $foundry." -ForegroundColor Yellow
    $answer = Read-Host "Type the account name ($foundry) to continue"
    if ($answer -ne $foundry) {
        Write-Host 'Cancelled. Nothing was deleted.'
        return
    }
}

Write-Step "Deleting $stackName with its resources and resource group"
Invoke-Az -Arguments @('stack', 'sub', 'delete', '--name', $stackName, '--action-on-unmanage', 'deleteAll',
    '--yes', '--only-show-errors')

if ($KeepSoftDeleted) {
    Write-Host "The account stays soft-deleted and recoverable for the retention period. Purge it later with:"
    Write-Host "  az cognitiveservices account purge --location $Location --resource-group $resourceGroup --name $foundry"
    return
}

Write-Step "Purging the soft-deleted account $foundry"
Invoke-Az -Arguments @('cognitiveservices', 'account', 'purge', '--location', $Location,
    '--resource-group', $resourceGroup, '--name', $foundry, '--only-show-errors')
Write-Host 'Done. No resource of the shared Foundry remains.' -ForegroundColor Green
