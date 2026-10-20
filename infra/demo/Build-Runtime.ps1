#Requires -Version 7.4
. "$PSScriptRoot\common.ps1"
Initialize-DemoContext
$outputs=Get-DemoDeploymentOutputs
$files=@('Dockerfile','pyproject.toml','config\demo.json','config\business.json') +
    @((Get-ChildItem -LiteralPath (Join-Path $script:RepoRoot 'src\giandoria') -Filter '*.py').FullName)
$hashes=($files | ForEach-Object { (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash }) -join ''
$digest=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($hashes))).ToLowerInvariant().Substring(0,16)
$refresh=[guid]::NewGuid().ToString('N')
$tag="giandoria-business:$digest-$($refresh.Substring(0,8))"
Invoke-AzJson -Arguments @('acr','build','--registry',$outputs.registryName.value,'--image',$tag,
    '--file','Dockerfile','--platform','linux/amd64','--build-arg',"PACKAGE_REFRESH=$refresh",'--no-logs','.') | Out-Null
$meta=Invoke-AzJson -Arguments @('acr','repository','show','--name',$outputs.registryName.value,'--image',$tag)
$registry=Invoke-AzJson -Arguments @('acr','show','--name',$outputs.registryName.value)
Assert-DemoOwnership $registry
Write-JsonFile @{image="$($registry.loginServer)/giandoria-business@$($meta.digest)";tag=$tag;sourceDigest=$digest} `
    (Join-Path $script:DemoLocal 'business-image.json')
Write-Host "Runtime image built and pinned by digest: $tag."
