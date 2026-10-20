#Requires -Version 7.4
<#
.SYNOPSIS
    Helpers shared by the shared-Foundry scripts. Dot-source it: . "$PSScriptRoot/common.ps1"
#>

Set-StrictMode -Version 3.0
$ErrorActionPreference = 'Stop'

$script:InfraRoot = Split-Path -Parent $PSScriptRoot
$script:RepoRoot = (Resolve-Path (Join-Path $script:InfraRoot '..\..')).Path

function Write-Step {
    param([Parameter(Mandatory)][string]$Message)
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Import-DotEnv {
    <#
    .SYNOPSIS
        Loads KEY=VALUE lines from the .env file at the repository root into the process environment.
        Variables that already have a value win, so a shell can override the file.
    #>
    param([string]$Path = (Join-Path $script:RepoRoot '.env'))

    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Host "No .env file at $Path; using the current environment only." -ForegroundColor DarkGray
        return
    }
    foreach ($line in Get-Content -LiteralPath $Path) {
        $text = $line.Trim()
        if (-not $text -or $text.StartsWith('#')) { continue }
        $eq = $text.IndexOf('=')
        if ($eq -lt 1) { continue }
        $key = $text.Substring(0, $eq).Trim()
        $value = $text.Substring($eq + 1).Trim()
        if ($value.Length -ge 2 -and $value[0] -eq $value[-1] -and $value[0] -in '"', "'") {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if ([string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($key))) {
            [Environment]::SetEnvironmentVariable($key, $value)
        }
    }
}

function Initialize-Tooling {
    <#
    .SYNOPSIS
        Checks that the Azure CLI exists. When a Bicep CLI is on PATH, makes the Azure CLI use it,
        so lint, build and deployment all run the same Bicep version.
    #>
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        throw 'Azure CLI (az) not found. Install it from https://aka.ms/installazurecli.'
    }
    if (Get-Command bicep -ErrorAction SilentlyContinue) {
        $env:AZURE_BICEP_USE_BINARY_FROM_PATH = 'true'
        $env:AZURE_BICEP_CHECK_VERSION = 'false'
    }
    if ($env:AZURE_CONFIG_DIR) {
        Write-Host "Azure CLI profile: $env:AZURE_CONFIG_DIR" -ForegroundColor DarkGray
    }
}

function Invoke-AzJson {
    <#
    .SYNOPSIS
        Runs an Azure CLI command with JSON output and returns the parsed result.
        Dates stay strings. Throws on failure unless -AllowFailure is set, which returns $null instead.
    #>
    param(
        [Parameter(Mandatory)][string[]]$Arguments,
        [switch]$AllowFailure
    )
    $errFile = New-TemporaryFile
    try {
        $out = & az @Arguments --only-show-errors --output json 2> $errFile.FullName
        $code = $LASTEXITCODE
        if ($code -ne 0) {
            if ($AllowFailure) { return $null }
            $err = (Get-Content -LiteralPath $errFile.FullName -Raw)
            throw "az $($Arguments -join ' ') failed with exit code ${code}: $err"
        }
        $json = ($out | Out-String).Trim()
        if (-not $json) { return $null }
        return $json | ConvertFrom-Json -DateKind String
    }
    finally {
        Remove-Item -LiteralPath $errFile.FullName -ErrorAction SilentlyContinue
    }
}

function Invoke-Az {
    <#
    .SYNOPSIS
        Runs an Azure CLI command and streams its output. Throws when the exit code is not zero.
    #>
    param([Parameter(Mandatory)][string[]]$Arguments)
    & az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "az $($Arguments[0..([Math]::Min(2, $Arguments.Count - 1))] -join ' ') failed with exit code $LASTEXITCODE."
    }
}

function Assert-AzContext {
    <#
    .SYNOPSIS
        Checks that the Azure CLI is signed in to the tenant and subscription named in .env.
        It never switches the subscription itself, to avoid surprising changes to the profile.
    #>
    $account = Invoke-AzJson -Arguments @('account', 'show') -AllowFailure
    if (-not $account) {
        throw ('The Azure CLI is not signed in. Run: az login --tenant <tenant-id> ' +
            '(with AZURE_CONFIG_DIR set as in .env). See infra/shared-foundry/README.md.')
    }
    if ($env:AZURE_TENANT_ID -and $account.tenantId -ne $env:AZURE_TENANT_ID) {
        throw "Signed in to tenant $($account.tenantId), but .env expects $env:AZURE_TENANT_ID."
    }
    if ($env:AZURE_SUBSCRIPTION_ID -and $account.id -ne $env:AZURE_SUBSCRIPTION_ID) {
        throw ("The active subscription is $($account.id), but .env expects $env:AZURE_SUBSCRIPTION_ID. " +
            "Run: az account set --subscription $env:AZURE_SUBSCRIPTION_ID")
    }
    Write-Host "Subscription: $($account.name) ($($account.id))" -ForegroundColor DarkGray
    return $account
}

function Get-StackName {
    param([Parameter(Mandatory)][string]$Location)
    return "stack-shared-ai-$Location"
}

function Get-StackOutputs {
    <#
    .SYNOPSIS
        Returns the outputs of the shared-Foundry deployment stack in a region, or $null if there is no stack.
    #>
    param([Parameter(Mandatory)][string]$Location)
    $stack = Invoke-AzJson -Arguments @('stack', 'sub', 'show', '--name', (Get-StackName $Location)) -AllowFailure
    if (-not $stack -or -not $stack.PSObject.Properties['outputs'] -or -not $stack.outputs) { return $null }
    return [pscustomobject]@{
        Stack             = $stack
        ResourceGroupName = $stack.outputs.resourceGroupName.value
        FoundryName       = $stack.outputs.foundryName.value
    }
}

function Get-Value {
    <#
    .SYNOPSIS
        Reads a dotted property path ("model.deprecation.inference") and returns $null when any part is missing.
        Strict mode would otherwise throw on missing properties.
    #>
    param($Object, [Parameter(Mandatory)][string]$Path)
    $current = $Object
    foreach ($part in $Path.Split('.')) {
        if ($null -eq $current) { return $null }
        $property = $current.PSObject.Properties[$part]
        if (-not $property) { return $null }
        $current = $property.Value
    }
    return $current
}

function Write-JsonFile {
    <#
    .SYNOPSIS
        Writes an object as JSON with UTF-8 (no BOM) and CRLF line endings.
    #>
    param(
        [Parameter(Mandatory)][object]$InputObject,
        [Parameter(Mandatory)][string]$Path
    )
    $json = $InputObject | ConvertTo-Json -Depth 20
    $json = ($json -replace "`r?`n", "`r`n") + "`r`n"
    [IO.File]::WriteAllText($Path, $json, [Text.UTF8Encoding]::new($false))
}
