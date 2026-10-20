#Requires -Version 7.4
[CmdletBinding()]
param()
. "$PSScriptRoot\common.ps1"
Initialize-DemoContext
$capacities = @(Invoke-AzJson -Arguments @('resource', 'list', '--resource-group', 'rg-giandoria-fabric-demo',
    '--resource-type', 'Microsoft.Fabric/capacities'))
if ($capacities.Count -ne 1) { throw 'Expected one existing demo capacity.' }
Assert-DemoOwnership $capacities[0]
$capacity = Invoke-DemoArm -Method GET -Path "$($capacities[0].id)?api-version=2023-11-01"
Write-Host "Capacity: $($capacity.name), $($capacity.sku.name), $($capacity.location), $($capacity.properties.state)"
if ($capacity.sku.name -ne 'F4' -or $capacity.location.ToLowerInvariant().Replace(' ', '') -ne 'swedencentral') {
    throw 'Unexpected demo capacity SKU or region.'
}
$token = Invoke-AzJson -Arguments @('account', 'get-access-token', '--resource', 'https://management.azure.com/')
$costBody = @{
    type = 'ActualCost'; timeframe = 'MonthToDate'
    dataset = @{ granularity = 'None'; aggregation = @{ totalCost = @{ name = 'Cost'; function = 'Sum' } } }
} | ConvertTo-Json -Depth 7
$cost = Invoke-RecordedWebRequest -Method POST -Uri (
    "https://management.azure.com$script:DemoSubscriptionScope/providers/Microsoft.CostManagement/query?api-version=2023-11-01"
) -Headers @{ Authorization = "Bearer $($token.accessToken)"; ClientType = 'GitHubCopilotForAzure' } `
    -Body $costBody -ContentType 'application/json'
$costData = $cost.Content | ConvertFrom-Json -DateKind String
Write-JsonFile -InputObject $costData -Path (Join-Path $script:DemoLocal 'demo-cost-preflight.json')
Write-Host "Lagged subscription MTD: $(($costData.properties.rows | ConvertTo-Json -Compress -Depth 5))"

$filter = "serviceName eq 'Microsoft Fabric' and armRegionName eq 'swedencentral' and priceType eq 'Consumption'"
$uri = "https://prices.azure.com/api/retail/prices?currencyCode='EUR'&`$filter=$([uri]::EscapeDataString($filter))"
$prices = (Invoke-RecordedWebRequest -Uri $uri).Content | ConvertFrom-Json -DateKind String
Write-JsonFile -InputObject $prices -Path (Join-Path $script:DemoLocal 'demo-fabric-retail-eur.json')
if ($prices.NextPageLink) { throw 'Retail price result paginated; inspect before relying on it.' }
Write-Host "Regional retail records: $(@($prices.Items).Count). Full response retained locally; base F4 tariff unresolved."
$apps = @(Invoke-AzJson -Arguments @('resource', 'list', '--tag', 'project=giandoria'))
$workers = @($apps | Where-Object { $_.type -in @('Microsoft.App/containerApps', 'Microsoft.App/jobs') })
Write-Host "Project apps/jobs: $($workers.Count)"
$privateEndpoints = @($apps | Where-Object { $_.type -eq 'Microsoft.Network/privateEndpoints' })
Write-Host "Project private endpoints: $($privateEndpoints.Count)"
$workspace = Get-Content -LiteralPath (Join-Path $script:DemoLocal 'demo-workspace.json') -Raw | ConvertFrom-Json
$fabricToken = Invoke-AzJson -Arguments @('account', 'get-access-token', '--resource', 'https://api.fabric.microsoft.com')
$headers = @{ Authorization = "Bearer $($fabricToken.accessToken)" }
$base = "https://api.fabric.microsoft.com/v1/workspaces/$($workspace.id)"
$items = (Invoke-RecordedWebRequest -Uri "$base/items" -Headers $headers).Content | ConvertFrom-Json
if (Get-Value $items 'continuationToken') { throw 'Fabric item inventory is paginated.' }
$registryPath = Join-Path $script:DemoLocal 'demo-fabric-items.json'
if (Test-Path -LiteralPath $registryPath) {
    $registry = Get-Content -LiteralPath $registryPath -Raw | ConvertFrom-Json
    if ($registry.workspaceId -ne $workspace.id) { throw 'Fabric registry workspace mismatch.' }
    foreach ($property in $registry.items.PSObject.Properties) {
        $matches = @($items.value | Where-Object { $_.displayName -eq $property.Name -and $_.id -eq $property.Value })
        if ($matches.Count -ne 1) { throw 'Recorded Fabric item identity is missing or changed.' }
    }
}
Write-Host "Fabric items: $(($items.value | ForEach-Object { "$($_.displayName) ($($_.type))" }) -join ', ')"
$operator = Invoke-AzJson -Arguments @('ad', 'signed-in-user', 'show')
$roles = (Invoke-RecordedWebRequest -Uri "$base/roleAssignments" -Headers $headers).Content | ConvertFrom-Json
if (Get-Value $roles 'continuationToken') { throw 'Workspace role inventory is paginated.' }
$ownRoles = @($roles.value | Where-Object { $_.principal.id -eq $operator.id })
if ($ownRoles.Count -ne 1 -or $ownRoles[0].role -ne 'Admin') { throw 'Expected current operator workspace Admin role.' }
Write-Host "Current operator workspace role: $($ownRoles[0].role). No role changes."
