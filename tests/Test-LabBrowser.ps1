#Requires -Version 7.4
$ErrorActionPreference = 'Stop'
$original = $env:LOCALAPPDATA
$temporary = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
$stateDirectory = Join-Path $temporary 'Microsoft\Edge\User Data'
[IO.Directory]::CreateDirectory($stateDirectory) | Out-Null
$statePath = Join-Path $stateDirectory 'Local State'
$launches = [Collections.Generic.List[object]]::new()
function Start-Process {
    param([string]$FilePath, [string[]]$ArgumentList)
    if ($ArgumentList.Count -ne 2 -or
        $ArgumentList[0] -ne '--profile-directory="Profile 24"' -or
        $ArgumentList[1] -ne '"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=test&code_challenge_method=S256"') {
        throw 'OAuth URL or requested Edge profile was corrupted.'
    }
    $launches.Add($ArgumentList)
}
try {
    $env:LOCALAPPDATA = $temporary
    '{"profile":{"info_cache":{"Profile 24":{"name":"LaQuantistica"},"Default":{"name":"Personal"}}}}' |
        Set-Content -LiteralPath $statePath
    & "$PSScriptRoot\..\ops\Open-LabBrowser.ps1" -Url 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=test&code_challenge_method=S256'
    if ($launches.Count -ne 1) { throw 'Browser launcher was not invoked exactly once.' }
    foreach ($url in @('http://login.microsoftonline.com/', 'https://other.invalid/')) {
        $rejected = $false
        try { & "$PSScriptRoot\..\ops\Open-LabBrowser.ps1" -Url $url }
        catch { $rejected = $true }
        if (-not $rejected) { throw 'Unapproved browser destination accepted.' }
    }
    '{"profile":{"info_cache":{"Default":{"name":"Personal"}}}}' | Set-Content -LiteralPath $statePath
    $rejected = $false
    try { & "$PSScriptRoot\..\ops\Open-LabBrowser.ps1" -Url 'https://login.microsoftonline.com/' }
    catch { $rejected = $true }
    if (-not $rejected) { throw 'Missing requested Edge profile did not fail closed.' }
    Write-Output 'PASS: exact OAuth URL, named Edge profile, destination checks and missing-profile denial.'
}
finally {
    $env:LOCALAPPDATA = $original
    Remove-Item -LiteralPath $temporary -Recurse
}
