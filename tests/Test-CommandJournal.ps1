#Requires -Version 7.4
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\ops\CommandJournal.ps1"

$secret = 'do-not-record-this-value'
$arguments = @(Get-RecordedArguments @('--password', $secret, '--access-token', $secret, "--sas-token=$secret",
    '--parameters', "client_secret=$secret", "https://example.com/?sig=$secret&comp=list"))
if (($arguments -join ' ') -match [regex]::Escape($secret)) { throw 'Command redaction failed.' }
$jwt = ('a' * 20) + '.' + ('b' * 20) + '.' + ('c' * 20)
if ((Protect-CommandText "Bearer $jwt") -match $jwt) { throw 'JWT redaction failed.' }

$id = [guid]::NewGuid().ToString()
Write-CommandRecord -Operation 'offline journal test' -Status Started -InvocationId $id -Details @{ test = $true }
Write-CommandRecord -Operation 'offline journal test' -Status Succeeded -InvocationId $id -Details @{ test = $true }
$path = Join-Path $PSScriptRoot "..\.local\command-journal\$PID.jsonl"
$records = @(Get-Content -LiteralPath $path | ForEach-Object { $_ | ConvertFrom-Json })
$own = @($records | Where-Object { $_.operation -eq 'offline journal test' })
if ($own.Count -lt 2 -or $own[-2].status -ne 'Started' -or $own[-1].status -ne 'Succeeded') {
    throw 'Append-only journal persistence failed.'
}
if ($own[-2].invocationId -ne $id -or $own[-1].invocationId -ne $id) { throw 'Journal correlation failed.' }

function Invoke-WebRequest {
    param($Uri, $Method, $Headers, $SkipHttpErrorCheck, $TimeoutSec, $Body, $ContentType)
    if ($Uri.AbsolutePath -eq '/transport-failure') { throw "transport failure $secret" }
    return [pscustomobject]@{ StatusCode = 403; Content = $secret }
}
$response = Invoke-RecordedWebRequest -Uri 'https://example.com/denied' -Headers @{
    Authorization = "Bearer $secret"
} -SkipHttpErrorCheck
if ($response.StatusCode -ne 403) { throw 'HTTP response changed.' }
$caught = $false
try { Invoke-RecordedWebRequest -Uri 'https://example.com/transport-failure' | Out-Null }
catch {
    if ($_.Exception.Message -ne "transport failure $secret") { throw }
    $caught = $true
}
if (-not $caught) { throw 'Transport error was swallowed.' }
if ((Get-Content -LiteralPath $path -Raw).Contains($secret)) { throw 'Secret leaked into journal.' }
try {
    Invoke-RecordedNative -FilePath 'pwsh' -Arguments @('-NoProfile', '-Command', 'Start-Sleep -Seconds 5') -TimeoutSeconds 1
    throw 'Expected bounded native command timeout.'
}
catch {
    if ($_.Exception.Message -ne 'Native command exceeded its 1-second limit.') { throw }
}
Write-Host 'Journal redaction, append, correlation, HTTP status and error propagation passed.'
