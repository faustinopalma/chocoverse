#Requires -Version 7.4
param([ValidateSet('Validate','Deploy')][string]$Stage = 'Validate', [switch]$RemoveUnusedBuildGroup)
. "$PSScriptRoot\common.ps1"
Initialize-DemoContext
$name = 'app-giandoria-data-agent-demo'
$marker = 'Giandoria demo; managed by Deploy-DataAgentIdentity; federated runtime access only.'
$path = Join-Path $script:DemoLocal 'data-agent-identity.json'
$identity = Invoke-AzJson -Arguments @('identity','show','--resource-group','rg-giandoria-core-demo',
    '--name','id-giandoria-runtime-demo')
Assert-DemoOwnership $identity
$token = Invoke-AzJson -Arguments @('account','get-access-token','--resource','https://graph.microsoft.com/')
$headers = @{ Authorization = "Bearer $($token.accessToken)" }
function Invoke-IdentityGraph {
    param([string]$Method, [string]$Route, $Body)
    if ($Route -notmatch '^/(applications|servicePrincipals)([/?]|$)') { throw 'Graph route outside application identity scope.' }
    $args = @{ Method=$Method; Uri="https://graph.microsoft.com/v1.0$Route"; Headers=$headers }
    if ($null -ne $Body) { $args.Body=$Body | ConvertTo-Json -Depth 12; $args.ContentType='application/json' }
    $response = Invoke-RecordedWebRequest @args
    if ($response.Content) { return $response.Content | ConvertFrom-Json -Depth 30 }
}
$apps = @(Invoke-AzJson -Arguments @('ad','app','list','--display-name',$name) |
    Where-Object displayName -eq $name)
if ($apps.Count -gt 1) { throw 'Multiple dedicated applications; refusing ambiguous identity.' }
$record = if (Test-Path -LiteralPath $path) { Get-Content -Raw $path | ConvertFrom-Json } else { $null }
if ($record -and ($record.tenantId -ne $script:DemoAccount.tenantId -or
    $record.managedIdentityPrincipalId -ne $identity.principalId -or $record.managedIdentityClientId -ne $identity.clientId)) {
    throw 'Recorded tenant or managed identity changed.'
}
if ($apps.Count -eq 1) {
    $app = Invoke-IdentityGraph GET "/applications/$($apps[0].id)"
    if (-not $record -or $record.applicationObjectId -ne $app.id -or $app.notes -ne $marker -or
        $app.signInAudience -ne 'AzureADMyOrg') { throw 'Refusing to adopt an unrecorded or foreign application.' }
    if (@($app.passwordCredentials).Count -or @($app.keyCredentials).Count -or @($app.requiredResourceAccess).Count) {
        throw 'Dedicated application has unexpected credentials or API application permissions.'
    }
}
elseif ($record) { throw 'Recorded application disappeared; refusing replacement.' }
if ($Stage -eq 'Validate') {
    Write-Host 'Identity context verified. Plan: single-tenant app, no passwords/certificates/Graph roles, exact MI federation.'
    return
}
if ($apps.Count -eq 0) {
    $app = Invoke-IdentityGraph POST '/applications' @{
        displayName=$name; signInAudience='AzureADMyOrg'; notes=$marker
        requiredResourceAccess=@(); tags=@('giandoria','demo')
    }
    $record = [pscustomobject]@{
        tenantId=$script:DemoAccount.tenantId; applicationObjectId=$app.id; clientId=$app.appId
        managedIdentityPrincipalId=$identity.principalId; managedIdentityClientId=$identity.clientId
        authentication='ManagedIdentityFederation'; marker=$marker
    }
    Write-JsonFile $record $path
}
$sps = @(Invoke-AzJson -Arguments @('ad','sp','list','--filter',"appId eq '$($record.clientId)'"))
if ($sps.Count -gt 1) { throw 'Ambiguous application service principal.' }
if ($sps.Count -eq 0) {
    if (Get-Value $record 'principalId') { throw 'Recorded service principal disappeared.' }
    $sp = Invoke-IdentityGraph POST '/servicePrincipals' @{appId=$record.clientId; tags=@('giandoria','demo')}
}
else {
    $sp = $sps[0]
    if ((Get-Value $record 'principalId') -and $record.principalId -ne $sp.id) { throw 'Service principal identity changed.' }
}
if (-not $sp.accountEnabled -or $sp.appOwnerOrganizationId -ne $record.tenantId) {
    throw 'Service principal is disabled or belongs to a different tenant.'
}
$record | Add-Member -NotePropertyName principalId -NotePropertyValue $sp.id -Force
Write-JsonFile $record $path
$route = "/applications/$($record.applicationObjectId)/federatedIdentityCredentials"
$federation = @{
    name='giandoria-runtime'; issuer="https://login.microsoftonline.com/$($record.tenantId)/v2.0"
    subject=$identity.principalId; audiences=@('api://AzureADTokenExchange')
    description='Only the Giandoria demo runtime user-assigned managed identity may authenticate as this application.'
}
$credentials = Invoke-IdentityGraph GET $route
if (Get-Value $credentials '@odata.nextLink') { throw 'Federated credentials require pagination review.' }
if (@($credentials.value).Count -eq 0) {
    Invoke-IdentityGraph POST $route $federation | Out-Null
}
elseif (@($credentials.value).Count -ne 1) { throw 'Unexpected additional federation trusts.' }
$credentials = Invoke-IdentityGraph GET $route
$actual = @($credentials.value)
if ($actual.Count -ne 1 -or $actual[0].name -ne $federation.name -or
    $actual[0].issuer -cne $federation.issuer -or $actual[0].subject -cne $federation.subject -or
    @($actual[0].audiences).Count -ne 1 -or $actual[0].audiences[0] -cne $federation.audiences[0]) {
    throw 'Persisted federation differs from the exact single-identity trust.'
}
if (Get-Value $record 'modelAccessGroupId') {
    if (-not $RemoveUnusedBuildGroup) { throw 'Obsolete Build-only group remains; use explicit cleanup after reviewing the service workspace.' }
    $groupId = [guid]::Parse($record.modelAccessGroupId).ToString()
    $groupToken = Invoke-AzJson -Arguments @('account','get-access-token','--resource','https://graph.microsoft.com/')
    $groupHeaders = @{Authorization="Bearer $($groupToken.accessToken)"}
    $response = Invoke-RecordedWebRequest -Uri "https://graph.microsoft.com/v1.0/groups/$groupId`?`$expand=members" -Headers $groupHeaders
    $group = $response.Content | ConvertFrom-Json -Depth 15
    if ($group.displayName -ne 'grp-giandoria-agent-model-demo' -or
        $group.description -ne 'Giandoria demo; managed by Deploy-DataAgentIdentity; Build on enterprise agent model only.' -or
        @($group.members).Count -ne 1 -or $group.members[0].id -ne $record.principalId) {
        throw 'Obsolete group ownership/membership differs; refusing cleanup.'
    }
    $service = Get-Content -Raw (Join-Path $script:DemoLocal 'data-agent-service.json') | ConvertFrom-Json
    if ($service.clientId -ne $record.clientId -or $service.workspaceId -eq $service.originalWorkspaceId) {
        throw 'Service boundary changed; refusing obsolete grant cleanup.'
    }
    $powerToken = Invoke-AzJson -Arguments @('account','get-access-token','--resource','https://analysis.windows.net/powerbi/api')
    $powerHeaders = @{Authorization="Bearer $($powerToken.accessToken)"}
    $url = "https://api.powerbi.com/v1.0/myorg/groups/$($service.workspaceId)/datasets/$($service.modelId)/users"
    $users = (Invoke-RecordedWebRequest -Uri $url -Headers $powerHeaders).Content | ConvertFrom-Json -Depth 15
    $grant = @($users.value | Where-Object identifier -eq $groupId)
    if ($grant.Count -gt 1 -or ($grant.Count -eq 1 -and $grant[0].datasetUserAccessRight -ne 'ReadExplore')) {
        throw 'Unexpected obsolete model grant.'
    }
    if ($grant.Count -eq 1) {
        $body = @{identifier=$groupId;principalType='Group';datasetUserAccessRight='None'} | ConvertTo-Json
        Invoke-RecordedWebRequest -Method PUT -Uri $url -Headers $powerHeaders -ContentType 'application/json' -Body $body | Out-Null
    }
    $users = (Invoke-RecordedWebRequest -Uri $url -Headers $powerHeaders).Content | ConvertFrom-Json -Depth 15
    if (@($users.value | Where-Object identifier -eq $groupId).Count) { throw 'Obsolete group model grant removal not confirmed.' }
    Invoke-RecordedWebRequest -Method DELETE -Uri "https://graph.microsoft.com/v1.0/groups/$groupId" -Headers $groupHeaders | Out-Null
    Write-JsonFile @{groupId=$groupId;state='Removed';reason='Viewer plus group Build did not support application query access.'} `
        (Join-Path $script:DemoLocal 'data-agent-unused-group-cleanup.json')
    $record.PSObject.Properties.Remove('modelAccessGroupId')
    Write-JsonFile $record $path
}
Write-Host 'Dedicated service principal and exact managed-identity federation verified; no secret or Key Vault needed.'
