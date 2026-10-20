#Requires -Version 7.4
[CmdletBinding()]
param([switch]$CheckAzure)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\infra\shared-foundry\scripts\common.ps1"

$configPath = Join-Path $script:RepoRoot 'config\demo.json'
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$expected = @{
    project = 'giandoria'; environment = 'demo'; location = 'swedencentral'; fabricSku = 'F4'
}
foreach ($key in $expected.Keys) {
    if ($config.$key -ne $expected[$key]) { throw "Unapproved demo configuration: $key." }
}
$tools = foreach ($name in @('az', 'bicep', 'fab', 'python', 'gh', 'git')) {
    [pscustomobject]@{ Tool = $name; Available = [bool](Get-Command $name -ErrorAction SilentlyContinue) }
}
$projectPython = Join-Path $script:RepoRoot '.venv\Scripts\python.exe'
$publisherAvailable = $false
if (Test-Path -LiteralPath $projectPython) {
    & $projectPython -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('fabric_cicd') else 1)"
    if ($LASTEXITCODE -notin @(0, 1)) { throw 'Could not check fabric-cicd in the project virtual environment.' }
    $publisherAvailable = $LASTEXITCODE -eq 0
}
$tools = @($tools) + @([pscustomobject]@{ Tool = 'fabric-cicd (project environment)'; Available = $publisherAvailable })
$warnings = [Collections.Generic.List[string]]::new()
foreach ($tool in $tools) {
    if (-not $tool.Available) { $warnings.Add("Missing tool: $($tool.Tool). Cloud deployment is not ready.") }
}
$warnings.Add('Full D16 runtime limits, Fabric item support and runtime caller access still need validation.')
$warnings.Add('Storage exemption/operator connectivity is checked separately by infra/demo/Test-DemoPublicAccess.ps1.')
$warnings.Add('Existing shared subscription resources may have recurring costs; this check does not query billing.')
$assignmentCount = $null
$resources = @()
if ($CheckAzure) {
    Import-DotEnv
    Initialize-Tooling
    if (-not $env:AZURE_TENANT_ID -or -not $env:AZURE_SUBSCRIPTION_ID) {
        throw 'Set AZURE_TENANT_ID and AZURE_SUBSCRIPTION_ID in the untracked .env before Azure preflight.'
    }
    $account = Invoke-AzJson -Arguments @('account', 'show')
    if ($account.tenantId -ne $env:AZURE_TENANT_ID -or $account.id -ne $env:AZURE_SUBSCRIPTION_ID) {
        throw 'The signed-in Azure context does not match the configured demo subscription and tenant.'
    }
    $url = "https://management.azure.com/subscriptions/$($account.id)/providers/" +
        'Microsoft.Authorization/policyAssignments?api-version=2023-04-01'
    $assignments = Invoke-AzJson -Arguments @('rest', '--method', 'get', '--url', $url)
    $assignmentCount = @($assignments.value).Count
    $allResources = Invoke-AzJson -Arguments @('resource', 'list')
    $resources = @(
        $allResources | Where-Object { (Get-Value $_ 'tags.project') -eq 'giandoria' } |
            ForEach-Object {
                [pscustomobject]@{
                    Name = $_.name
                    Type = $_.type
                    Location = $_.location
                    State = Get-Value $_ 'properties.state'
                }
            }
    )
    $warnings.Add('Assignment count is discovery only, not a full evaluation of inherited policy parameters.')
    $warnings.Add('Generic resource state may be absent; it is not proof that a capacity or an app is stopped.')
}
[pscustomobject]@{
    Mode = 'ReadOnly'
    Project = $config.project
    Environment = $config.environment
    Location = $config.location
    FabricSku = $config.fabricSku
    Tools = @($tools)
    EffectivePolicyAssignments = $assignmentCount
    TaggedProjectResources = $resources
    CloudDeploymentReady = $false
    Warnings = @($warnings)
} | ConvertTo-Json -Depth 6
