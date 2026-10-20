[CmdletBinding()]
param(
    [ValidateRange(1, 1440)][int]$Minutes = 90,
    [guid]$AppId = [guid]::Empty
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\infra\demo\common.ps1"
Initialize-DemoContext
$account = Invoke-AzJson -Arguments @('account','show')
$since = [datetime]::UtcNow.AddMinutes(-$Minutes).ToString('yyyy-MM-ddTHH:mm:ssZ')
$principal = $account.user.name.Replace("'", "''")
$filter = "createdDateTime ge $since and userPrincipalName eq '$principal'"
if ($AppId -ne [guid]::Empty) {
    $filter = "createdDateTime ge $since and appId eq '$AppId'"
}
$url = 'https://graph.microsoft.com/v1.0/auditLogs/signIns?$filter=' +
    [uri]::EscapeDataString($filter) +
    '&$top=50&$select=id,createdDateTime,appDisplayName,appId,resourceDisplayName,status,' +
    'conditionalAccessStatus,correlationId,clientAppUsed,isInteractive'
$token = Invoke-AzJson -Arguments @('account','get-access-token','--resource','https://graph.microsoft.com/')
$response = Invoke-RecordedWebRequest -Method GET -Uri $url -Headers @{
    Authorization = "Bearer $($token.accessToken)"
} -SkipHttpErrorCheck
if ([int]$response.StatusCode -ne 200) {
    throw "Entra sign-in diagnostics failed ($([int]$response.StatusCode)): $($response.Content)"
}
$result = $response.Content | ConvertFrom-Json -DateKind String
$output = @{
    queriedAt = [datetime]::UtcNow.ToString('o')
    since = $since
    hasMore = [bool](Get-Value $result '@odata.nextLink')
    signIns = @($result.value)
}
$suffix = if ($AppId -ne [guid]::Empty) { "-$AppId" } else { '' }
$output | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $script:DemoLocal "entra-auth-diagnostics$suffix.json") -Encoding utf8
$output | ConvertTo-Json -Depth 12
