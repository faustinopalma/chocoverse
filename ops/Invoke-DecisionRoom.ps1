#Requires -Version 7.4
[CmdletBinding()]
param(
    [ValidateSet('Prepare','Preview','Dev','Deploy','Status','Query','Login','Sources')][string]$Action = 'Preview',
    [string]$QueryFile
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\infra\demo\common.ps1"
Initialize-DemoContext
$root = Split-Path $PSScriptRoot -Parent
$app = Join-Path $root 'apps\giandoria-decision-room'
$python = Join-Path $root '.venv\Scripts\python.exe'
& "$PSScriptRoot\Invoke-RecordedCommand.ps1" -FilePath $python -Arguments @('-m','giandoria.decision_room')
$source = Get-Content (Join-Path $root '.local\data-agent.json') -Raw | ConvertFrom-Json
$workspace = Get-Content (Join-Path $root '.local\demo-workspace.json') -Raw | ConvertFrom-Json
if ($source.workspaceId -ne $workspace.id -or $workspace.displayName -ne 'ws-giandoria-demo') {
    throw 'Decision Room requires the recorded enterprise workspace.'
}
if ($Action -eq 'Prepare') { return }
$deploymentFile = Join-Path $app 'rayfin\.deployments.json'
if (Test-Path $deploymentFile) {
    $record = Get-Content $deploymentFile -Raw | ConvertFrom-Json
    $target = $record.deployments.($record.active)
    if ($target.fabricWorkspaceId -ne $workspace.id) { throw 'Rayfin deployment workspace changed.' }
}
$priorToken = $env:RAYFIN_TOKEN
$priorBrowser = $env:BROWSER
if ($Action -in @('Query','Login')) {
    Remove-Item Env:RAYFIN_TOKEN -ErrorAction SilentlyContinue
} else {
    $token = Invoke-AzJson -Arguments @('account','get-access-token','--resource','https://api.fabric.microsoft.com')
    $env:RAYFIN_TOKEN = $token.accessToken
}
$env:BROWSER = Join-Path $PSScriptRoot 'Open-LabBrowser.cmd'
$env:RAYFIN_TELEMETRY_OPTOUT = '1'
$env:GIANDORIA_MODEL_WORKSPACE_ID = $source.workspaceId
$env:GIANDORIA_MODEL_ID = $source.modelId
$cli = @('exec','--yes','--package=node@22.23.3','--','node',
         '.\node_modules\@microsoft\rayfin-cli\scripts\main')
$arguments = switch ($Action) {
    'Preview' { @('up','-n','--workspace-id',$workspace.id,'--json') }
    'Dev' { @('dev','--provider','fabric','--workspace-id',$workspace.id) }
    'Deploy' { @('up','--workspace-id',$workspace.id,'--json') }
    'Status' { @('up','status','--json') }
    'Login' { @('login','--tenant',$env:AZURE_TENANT_ID) }
    'Sources' { @() }
    'Query' {
        if (-not $QueryFile) { throw 'Query requires a project-relative JSON QueryFile.' }
        @('connector','invoke','enterprise','executeQuery','--file',$QueryFile,'--json')
    }
}
Push-Location $app
try {
    if ($Action -eq 'Sources') {
        & "$PSScriptRoot\Invoke-RecordedCommand.ps1" -FilePath npm.cmd -Arguments @('run','typecheck')
        & "$PSScriptRoot\Invoke-RecordedCommand.ps1" -FilePath npm.cmd -Arguments @(
            'exec','--yes','--package=node@22.23.3','--','node','scripts\verify-source-contracts.mjs')
    } else {
        & "$PSScriptRoot\Invoke-RecordedCommand.ps1" -FilePath npm.cmd -Arguments ($cli + $arguments)
    }
}
finally {
    Pop-Location
    if ($priorToken) { $env:RAYFIN_TOKEN = $priorToken } else { Remove-Item Env:RAYFIN_TOKEN -ErrorAction SilentlyContinue }
    if ($priorBrowser) { $env:BROWSER = $priorBrowser } else { Remove-Item Env:BROWSER -ErrorAction SilentlyContinue }
}
