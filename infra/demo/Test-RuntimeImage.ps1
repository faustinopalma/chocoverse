#Requires -Version 7.4
. "$PSScriptRoot\common.ps1"
Initialize-DemoContext
$outputs=Get-DemoDeploymentOutputs
$image=Get-Content -Raw (Join-Path $script:DemoLocal 'business-image.json') | ConvertFrom-Json
$registry=Invoke-AzJson -Arguments @('acr','show','--name',$outputs.registryName.value)
Assert-DemoOwnership $registry
if ($image.image -notmatch "^$([regex]::Escape($registry.loginServer))/giandoria-business@sha256:[a-f0-9]{64}$") {
    throw 'Image check requires a pinned digest in the existing demo registry.'
}
$directory=Join-Path $script:DemoLocal 'runtime-image-check'
[IO.Directory]::CreateDirectory($directory) | Out-Null
$command='set -eu; test "$(id -u)" = 65532; id; dpkg-query -W; ' +
    'python -m pip list --format=json; python -m pip check; ' +
    'python -c "import ssl, sqlite3, azure.identity, azure.eventhub, requests, websocket, giandoria.runtime"'
$task=@{
    version='v1.1.0'
    steps=@(@{cmd="--entrypoint /bin/sh $($image.image) -c '$command'";timeout=120})
}
Write-JsonFile $task (Join-Path $directory 'task.json')
$run=Invoke-AzJson -Arguments @('acr','run','--registry',$registry.name,'--platform','linux/amd64',
    '--file','task.json','--no-logs',$directory)
Write-JsonFile @{image=$image.image;run=$run} (Join-Path $script:DemoLocal 'runtime-image-check.json')
$logs=@(Invoke-Az -Arguments @('acr','task','logs','--registry',$registry.name,'--run-id',$run.runId))
[IO.File]::WriteAllLines((Join-Path $script:DemoLocal 'runtime-image-check.log'),$logs,[Text.UTF8Encoding]::new($false))
if ($run.status -ne 'Succeeded') { throw 'Isolated runtime image check did not succeed; inspect the retained task logs.' }
Write-Host "Non-root package, dependency and import checks passed for $($image.image)."
