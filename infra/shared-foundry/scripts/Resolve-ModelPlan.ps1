#Requires -Version 7.4
<#
.SYNOPSIS
    Turns model-selection.json into model-plan.json for one Azure region.

.DESCRIPTION
    For each family in model-selection.json the script:
      1. lists the models that the region offers to Foundry accounts (kind AIServices);
      2. keeps the models whose name matches the family pattern and whose format matches, that offer the
         selected SKU, that are generally available (or in preview when the family allows it), and that are
         not retired for inference within minDaysToRetirement days;
      3. picks the newest generation (the "gen" group of the pattern), then the newest version;
      4. sizes the deployment to the free quota: limit - used + capacity this stack already holds,
         times -QuotaShare, capped by the SKU maximum.
    model-plan.json works as a lock file: commit it, review its diff, deploy it with Deploy-SharedFoundry.ps1.
    The file is rewritten only when something other than the timestamp changes.

.PARAMETER Location
    Azure region. Defaults to SHARED_FOUNDRY_LOCATION, then to the region of the current plan, then swedencentral.

.PARAMETER QuotaShare
    Share of the free quota to take, from 0.01 to 1. The default 1 takes all of it.

.EXAMPLE
    ./Resolve-ModelPlan.ps1 -Location swedencentral

.EXAMPLE
    ./Resolve-ModelPlan.ps1 -QuotaShare 0.5
#>
[CmdletBinding()]
param(
    [string]$Location,
    [ValidateRange(0.01, 1.0)][double]$QuotaShare = 1.0,
    [string]$SelectionPath,
    [string]$PlanPath
)

. "$PSScriptRoot/common.ps1"

if (-not $SelectionPath) { $SelectionPath = Join-Path $script:InfraRoot 'model-selection.json' }
if (-not $PlanPath) { $PlanPath = Join-Path $script:InfraRoot 'model-plan.json' }

Import-DotEnv
Initialize-Tooling
$null = Assert-AzContext

$currentPlan = $null
if (Test-Path -LiteralPath $PlanPath) {
    $currentPlan = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json -DateKind String
}
if (-not $Location) { $Location = $env:SHARED_FOUNDRY_LOCATION }
if (-not $Location -and $currentPlan) { $Location = $currentPlan.location }
if (-not $Location) { $Location = 'swedencentral' }
$Location = $Location.ToLowerInvariant()

$selection = Get-Content -LiteralPath $SelectionPath -Raw | ConvertFrom-Json -DateKind String
$skuName = $selection.sku
$minDays = [int]((Get-Value $selection 'minDaysToRetirement') ?? 0)
$upgradeOption = Get-Value $selection 'openAiVersionUpgradeOption'
$today = [DateTimeOffset]::UtcNow
$invariant = [Globalization.CultureInfo]::InvariantCulture

function ConvertTo-Generation([string]$Text) {
    if ($Text -notmatch '\.') { $Text += '.0' }
    return [version]$Text
}

function Get-VersionKey([string]$Version) {
    # Date versions ("2026-09-22") sort as text; numeric versions ("1", "2.1") are zero-padded first.
    if ($Version -match '^\d+(\.\d+){0,3}$') {
        return (($Version.Split('.') | ForEach-Object { '{0:D8}' -f [int]$_ }) -join '.')
    }
    return $Version
}

function Get-RetirementDate($Entry, $Sku) {
    $dates = @((Get-Value $Entry 'model.deprecation.inference'), (Get-Value $Sku 'deprecationDate')) |
        Where-Object { $_ } |
        ForEach-Object { [DateTimeOffset]::Parse($_, $invariant) }
    if (-not $dates) { return $null }
    return ($dates | Sort-Object | Select-Object -First 1)
}

function Get-QuotaUnit($Usage) {
    $label = [string](Get-Value $Usage 'name.localizedValue')
    if ($label -like 'One Thousand Tokens Per Minute*') { return '1K TPM' }
    if ($label -like 'Requests Per Minute*') { return 'RPM' }
    return [string](Get-Value $Usage 'unit')
}

Write-Step "Reading the model catalog and the quota for $Location"
$catalog = @(Invoke-AzJson -Arguments @('cognitiveservices', 'model', 'list', '--location', $Location) |
    Where-Object { $_.kind -eq 'AIServices' })
$usages = @{}
foreach ($usage in @(Invoke-AzJson -Arguments @('cognitiveservices', 'usage', 'list', '--location', $Location))) {
    $usages[$usage.name.value] = $usage
}
Write-Host "$($catalog.Count) catalog entries, $($usages.Count) quota entries."
if ($catalog.Count -eq 0) { throw "The region $Location offers no models to Foundry accounts." }

# Quota held by deployments of this stack counts as free: an update replaces them.
$ownCapacity = @{}
$stackInfo = Get-StackOutputs -Location $Location
if ($stackInfo) {
    Write-Host "Stack found: account $($stackInfo.FoundryName) in $($stackInfo.ResourceGroupName)."
    $managedIds = @($stackInfo.Stack.resources | ForEach-Object { $_.id.ToLowerInvariant() })
    $existing = @(Invoke-AzJson -AllowFailure -Arguments @(
            'cognitiveservices', 'account', 'deployment', 'list',
            '--resource-group', $stackInfo.ResourceGroupName, '--name', $stackInfo.FoundryName))
    foreach ($deployment in $existing | Where-Object { $_ -and $managedIds -contains $_.id.ToLowerInvariant() }) {
        $model = $deployment.properties.model
        $entry = $catalog |
            Where-Object { $_.model.name -eq $model.name -and $_.model.format -eq $model.format } |
            Sort-Object { $_.model.version -eq $model.version } -Descending |
            Select-Object -First 1
        $sku = $entry ? (@($entry.model.skus) | Where-Object name -eq $deployment.sku.name | Select-Object -First 1) : $null
        if ($sku) {
            $ownCapacity[$sku.usageName] = ($ownCapacity[$sku.usageName] ?? 0) + [int]$deployment.sku.capacity
        }
    }
}

Write-Step 'Resolving model families'
$deployments = [Collections.Generic.List[object]]::new()
$skipped = [Collections.Generic.List[object]]::new()
$allocated = @{}

foreach ($family in $selection.families) {
    $allowPreview = [bool](Get-Value $family 'allowPreview')
    $allowed = @('GenerallyAvailable') + ($allowPreview ? @('Preview') : @())
    $candidates = [Collections.Generic.List[object]]::new()
    $retiringSoon = [Collections.Generic.List[string]]::new()

    foreach ($entry in $catalog) {
        $model = $entry.model
        if ($model.format -ne $family.format) { continue }
        $match = [regex]::Match($model.name, $family.match, 'IgnoreCase')
        if (-not $match.Success) { continue }
        if ($model.lifecycleStatus -notin $allowed) { continue }
        $sku = @($model.skus) | Where-Object name -eq $skuName | Select-Object -First 1
        if (-not $sku) { continue }
        $retires = Get-RetirementDate $entry $sku
        if ($retires -and ($retires - $today).TotalDays -lt $minDays) {
            $retiringSoon.Add("$($model.name)@$($model.version) retires $($retires.ToString('yyyy-MM-dd'))")
            continue
        }
        $candidates.Add([pscustomobject]@{
                Entry      = $entry
                Sku        = $sku
                Generation = ConvertTo-Generation $match.Groups['gen'].Value
                VersionKey = Get-VersionKey $model.version
                Retires    = $retires
            })
    }

    if ($candidates.Count -eq 0) {
        $reason = "no $($allowed -join '/') model offers $skuName in $Location"
        if ($retiringSoon.Count -gt 0) {
            $reason = "every candidate retires within $minDays days: $($retiringSoon -join '; ')"
        }
        $skipped.Add([ordered]@{ family = $family.family; reason = $reason })
        continue
    }

    $pick = $candidates | Sort-Object -Property @(
        @{ Expression = 'Generation'; Descending = $true },
        @{ Expression = 'VersionKey'; Descending = $true }) | Select-Object -First 1
    $model = $pick.Entry.model
    $usageName = $pick.Sku.usageName
    $usage = $usages[$usageName]
    if (-not $usage) {
        $skipped.Add([ordered]@{ family = $family.family; reason = "no quota entry named $usageName in $Location" })
        continue
    }

    $limit = [double]$usage.limit
    $used = [double]$usage.currentValue
    $own = [double]($ownCapacity[$usageName] ?? 0)
    $free = $limit - $used + $own - [double]($allocated[$usageName] ?? 0)
    $capacity = [Math]::Floor($free * $QuotaShare)
    $maximum = Get-Value $pick.Sku 'capacity.maximum'
    if ($maximum) { $capacity = [Math]::Min($capacity, [double]$maximum) }
    $step = Get-Value $pick.Sku 'capacity.step'
    if ($step -and [double]$step -gt 1) { $capacity = [Math]::Floor($capacity / [double]$step) * [double]$step }
    $minimum = Get-Value $pick.Sku 'capacity.minimum'
    if ($capacity -lt 1 -or ($minimum -and $capacity -lt [double]$minimum)) {
        $skipped.Add([ordered]@{
                family = $family.family
                reason = "$($model.name): no free quota (limit $limit, $($used - $own) used by other deployments)"
            })
        continue
    }
    $allocated[$usageName] = [double]($allocated[$usageName] ?? 0) + $capacity

    $item = [ordered]@{
        name  = $model.name
        model = [ordered]@{ format = $model.format; name = $model.name; version = $model.version }
        sku   = [ordered]@{ name = $skuName; capacity = [int]$capacity }
    }
    if ($model.format -eq 'OpenAI' -and $upgradeOption) { $item.versionUpgradeOption = $upgradeOption }
    $item.metadata = [ordered]@{
        family       = $family.family
        purpose      = $family.purpose
        lifecycle    = $model.lifecycleStatus
        retiresOn    = $pick.Retires ? $pick.Retires.ToString('yyyy-MM-dd') : $null
        quotaName    = $usageName
        quotaScope   = (@((Get-Value $usage 'scopeType'), (Get-Value $usage 'scopeId')) | Where-Object { $_ }) -join '/'
        quotaUnit    = Get-QuotaUnit $usage
        quotaLimit   = [int]$limit
        usedByOthers = [int]($used - $own)
    }
    $deployments.Add($item)
}

$plan = [ordered]@{
    generatedBy         = 'infra/shared-foundry/scripts/Resolve-ModelPlan.ps1 from model-selection.json'
    generatedAt         = $today.ToString('yyyy-MM-ddTHH:mm:ssZ')
    location            = $Location
    sku                 = $skuName
    quotaShare          = $QuotaShare
    minDaysToRetirement = $minDays
    deployments         = $deployments.ToArray()
    skipped             = $skipped.ToArray()
}

# Compare without the timestamp, after a JSON round trip so both sides have the same types.
$newPlan = $plan | ConvertTo-Json -Depth 20 | ConvertFrom-Json -DateKind String
$comparable = { param($p) $p | Select-Object -Property * -ExcludeProperty generatedAt | ConvertTo-Json -Depth 20 -Compress }
if ($currentPlan -and ((& $comparable $currentPlan) -eq (& $comparable $newPlan))) {
    Write-Host "`nmodel-plan.json is already up to date." -ForegroundColor Green
}
else {
    Write-JsonFile -InputObject $plan -Path $PlanPath
    Write-Host "`nWrote $PlanPath. Review the diff before deploying." -ForegroundColor Green
}

$deployments | ForEach-Object {
    [pscustomobject]@{
        Deployment = $_.name
        Version    = $_.model.version
        Lifecycle  = $_.metadata.lifecycle
        Capacity   = "$($_.sku.capacity) $($_.metadata.quotaUnit)"
        Quota      = "$($_.metadata.quotaLimit) ($($_.metadata.quotaScope))"
        Retires    = $_.metadata.retiresOn
    }
} | Format-Table -AutoSize | Out-String -Width 200 | Write-Host

foreach ($s in $skipped) { Write-Warning "Skipped $($s.family): $($s.reason)" }
$preview = @($deployments | Where-Object { $_.metadata.lifecycle -eq 'Preview' })
if ($preview.Count -gt 0) {
    $names = ($preview | ForEach-Object { $_.name }) -join ', '
    Write-Warning "Preview models have no SLA and can change or retire quickly: $names."
}
