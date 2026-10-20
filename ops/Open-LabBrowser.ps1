[CmdletBinding()]
param([Parameter(Mandatory)][uri]$Url)
$ErrorActionPreference = 'Stop'
$allowedHost = $Url.Host -in @('login.microsoftonline.com','app.fabric.microsoft.com') -or
    $Url.Host.EndsWith('.webapp.fabricapps.net', [StringComparison]::OrdinalIgnoreCase)
if ($Url.Scheme -ne 'https' -or -not $Url.IsDefaultPort -or -not $allowedHost) {
    throw 'Lab authentication browser only accepts Microsoft sign-in and Fabric URLs.'
}
$stateFile = Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\User Data\Local State'
$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
$profiles = @($state.profile.info_cache.PSObject.Properties |
    Where-Object { $_.Value.name -eq 'laquantistica' })
if ($profiles.Count -ne 1) { throw 'Expected exactly one Edge profile named laquantistica.' }
$edge = Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'
if (-not (Test-Path $edge)) { throw 'Microsoft Edge executable not found.' }
Start-Process -FilePath $edge -ArgumentList @("--profile-directory=`"$($profiles[0].Name)`"", "`"$($Url.AbsoluteUri)`"")
