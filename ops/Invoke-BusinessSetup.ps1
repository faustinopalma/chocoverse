#Requires -Version 7.4
. "$PSScriptRoot\..\infra\demo\common.ps1"
Initialize-DemoContext
$session=[guid]::NewGuid().ToString()
$control=Join-Path $PSScriptRoot 'Invoke-LabControl.ps1'
try {
    Invoke-RecordedNative pwsh @('-NoProfile','-File',$control,'-Action','Start','-SessionId',$session,'-MaxWallMinutes','15') -TimeoutSeconds 780
    Invoke-RecordedNative pwsh @('-NoProfile','-File',(Join-Path $script:RepoRoot 'infra\demo\Deploy-BusinessFabric.ps1')) -TimeoutSeconds 780
}
finally {
    Invoke-RecordedNative pwsh @('-NoProfile','-File',$control,'-Action','Stop','-SessionId',$session,'-Force') -TimeoutSeconds 780
}
