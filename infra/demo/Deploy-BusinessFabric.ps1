#Requires -Version 7.4
. "$PSScriptRoot\common.ps1"
Initialize-DemoContext
$workspace=Get-Content -Raw (Join-Path $script:DemoLocal 'demo-workspace.json') | ConvertFrom-Json
if ($workspace.displayName -ne 'ws-giandoria-demo') { throw 'Unexpected workspace.' }
$base="/v1/workspaces/$($workspace.id)"
$fabricToken=Invoke-AzJson -Arguments @('account','get-access-token','--resource','https://api.fabric.microsoft.com')
$headers=@{Authorization="Bearer $($fabricToken.accessToken)"}
$env:GIANDORIA_FABRIC_TOKEN=$fabricToken.accessToken
$env:GIANDORIA_FABRIC_TOKEN_EXPIRES=[string]$fabricToken.expires_on
try {
    Invoke-RecordedNative (Join-Path $script:RepoRoot '.venv\Scripts\python.exe') @('-m','giandoria.fabric_deploy') -TimeoutSeconds 330
    $env:GIANDORIA_PUBLISH_BUSINESS='1'
    Invoke-RecordedNative (Join-Path $script:RepoRoot '.venv\Scripts\python.exe') @('-m','giandoria.fabric_deploy') -TimeoutSeconds 330
}
finally {
    Remove-Item Env:GIANDORIA_FABRIC_TOKEN,Env:GIANDORIA_FABRIC_TOKEN_EXPIRES,Env:GIANDORIA_PUBLISH_BUSINESS -ErrorAction SilentlyContinue
}
function Invoke-BusinessFabric {
    param([string]$Method,[string]$Path,$Body)
    if (-not $Path.StartsWith("$base/") -and $Path -notmatch '^/v1/operations/[a-fA-F0-9-]{36}(/result)?$') {
        throw 'Fabric operation outside the recorded workspace.'
    }
    $args=@{Method=$Method;Uri="https://api.fabric.microsoft.com$Path";Headers=$headers;TimeoutSec=60}
    if ($null -ne $Body) { $args.Body=$Body | ConvertTo-Json -Depth 15; $args.ContentType='application/json' }
    $response=Invoke-RecordedWebRequest @args
    if ($response.StatusCode -eq 202) {
        $location=[uri]$response.Headers.Location[0]
        if ($location.AbsolutePath -notmatch '^/v1/operations/[a-fA-F0-9-]{36}$') { throw 'Unexpected Fabric operation route.' }
        $until=[datetime]::UtcNow.AddMinutes(3)
        do {
            Start-Sleep -Seconds 3
            $operation=Invoke-BusinessFabric GET $location.AbsolutePath
            if ($operation.status -eq 'Failed') { throw 'Fabric async operation failed.' }
            if ($operation.status -eq 'Succeeded') { return Invoke-BusinessFabric GET "$($location.AbsolutePath)/result" }
        } while ([datetime]::UtcNow -lt $until)
        throw 'Fabric async operation timed out.'
    }
    if ($response.Content) { return $response.Content | ConvertFrom-Json -DateKind String }
}
$registry=Get-Content -Raw (Join-Path $script:DemoLocal 'demo-fabric-items.json') | ConvertFrom-Json
if ($registry.workspaceId -ne $workspace.id) { throw 'Fabric item registry mismatch.' }
$stream=$registry.items.es_giandoria_business
$definition=Invoke-BusinessFabric POST "$base/eventstreams/$stream/getDefinition"
$part=@($definition.definition.parts | Where-Object path -eq 'eventstream.json')
if ($part.Count -ne 1) { throw 'Missing Eventstream topology.' }
$topology=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($part[0].payload)) | ConvertFrom-Json
$source=@($topology.sources | Where-Object { $_.name -eq 'business' -and $_.type -eq 'CustomEndpoint' })
if ($source.Count -ne 1 -or -not (Get-Value $source[0] 'id')) { throw 'Missing custom source identity.' }
$connection=Invoke-BusinessFabric GET "$base/eventstreams/$stream/sources/$($source[0].id)/connection"
if ($connection.fullyQualifiedNamespace -notmatch '^[a-zA-Z0-9.-]+\.servicebus\.windows\.net$' -or
    $connection.eventHubName -notmatch '^[a-zA-Z0-9_.-]+$') { throw 'Unexpected custom endpoint connection.' }
$identity=Invoke-AzJson -Arguments @('identity','show','--resource-group','rg-giandoria-core-demo','--name','id-giandoria-runtime-demo')
Assert-DemoOwnership $identity
$roles=Invoke-BusinessFabric GET "$base/roleAssignments"
if (Get-Value $roles 'continuationToken') { throw 'Workspace roles need pagination review.' }
$existing=@($roles.value | Where-Object {$_.principal.id -eq $identity.principalId})
if ($existing.Count -eq 0) {
    Invoke-BusinessFabric POST "$base/roleAssignments" @{principal=@{id=$identity.principalId;type='ServicePrincipal'};role='Member'} | Out-Null
}
elseif ($existing.Count -ne 1 -or $existing[0].role -ne 'Member') { throw 'Runtime workspace role differs from the planned Member scope.' }
$database=Invoke-BusinessFabric GET "$base/kqlDatabases/$($registry.items.kqldb_giandoria)"
Write-JsonFile @{
    workspaceId=$workspace.id;streamId=$stream;sourceId=$source[0].id;databaseId=$database.id
    queryServiceUri=$database.properties.queryServiceUri
    streamNamespace=$connection.fullyQualifiedNamespace;streamHub=$connection.eventHubName
    runtimePrincipalId=$identity.principalId;transport='Eventstream custom endpoint; Entra AMQP over WebSockets'
} (Join-Path $script:DemoLocal 'business-fabric.json')
Write-Host 'Business Eventstream and scoped runtime membership configured; no SAS keys retained or used.'
