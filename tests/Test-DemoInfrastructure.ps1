#Requires -Version 7.4
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\infra\demo\common.ps1"

function Assert-Rejected {
    param([scriptblock]$Action, [string]$Expected)
    try { & $Action | Out-Null }
    catch {
        if ($_.Exception.Message -notlike $Expected) { throw }
        return
    }
    throw "Expected rejection: $Expected"
}

Assert-DemoOwnership ([pscustomobject]@{ tags = [pscustomobject]@{ project = 'giandoria'; env = 'demo' } })
Assert-Rejected {
    Assert-DemoOwnership ([pscustomobject]@{ tags = [pscustomobject]@{ project = 'other'; env = 'demo' } })
} 'Refusing to adopt*'
Assert-Rejected {
    Assert-DemoOwnership ([pscustomobject]@{ tags = [pscustomobject]@{ project = 'giandoria'; env = 'prod' } })
} 'Refusing to adopt*'
Assert-Rejected {
    Invoke-DemoArm -Method GET -Path 'https://example.com'
} 'ARM paths must*'

foreach ($status in @(401, 403)) {
    if (-not (Test-DemoAnonymousBlobDenial -StatusCode $status -Content '')) {
        throw "Expected HTTP $status to be recognized as access denial."
    }
}
if (-not (Test-DemoAnonymousBlobDenial -StatusCode 409 -Content '<Error><Code>PublicAccessNotPermitted</Code></Error>')) {
    throw 'The observed Storage public-access denial was not recognized.'
}
foreach ($response in @(
    @{ Status = 200; Body = '<Code>PublicAccessNotPermitted</Code>' }
    @{ Status = 409; Body = '<Code>BlobAlreadyExists</Code>' }
    @{ Status = 404; Body = '<Code>BlobNotFound</Code>' }
)) {
    if (Test-DemoAnonymousBlobDenial -StatusCode $response.Status -Content $response.Body) {
        throw 'Unrelated HTTP result was incorrectly accepted as proof of access denial.'
    }
}

function New-TestWaiver {
    return [pscustomobject]@{
        name = 'giandoria-public-storage-poc'
        properties = [pscustomobject]@{
            policyAssignmentId = 'test-assignment'
            exemptionCategory = 'Waiver'
            policyDefinitionReferenceIds = @('StorageAccountPublicNetworkModify')
            metadata = [pscustomobject]@{ project = 'giandoria'; environment = 'demo' }
        }
    }
}
function Invoke-DemoArm {
    param($Method, $Path)
    return $script:TestWaiver
}
$account = [pscustomobject]@{ id = '/test-account' }
$script:TestWaiver = New-TestWaiver
Assert-DemoStorageExemption -Account $account -AssignmentId 'test-assignment' | Out-Null
Assert-Rejected {
    Assert-DemoStorageExemption -Account $account -AssignmentId 'other-assignment'
} 'Storage exemption differs*'

$script:TestWaiver = New-TestWaiver
$script:TestWaiver.properties.policyDefinitionReferenceIds += 'OtherSecurityPolicy'
Assert-Rejected {
    Assert-DemoStorageExemption -Account $account -AssignmentId 'test-assignment'
} 'Storage exemption differs*'

$script:TestWaiver = New-TestWaiver
$script:TestWaiver.properties | Add-Member -NotePropertyName expiresOn -NotePropertyValue '2099-01-01T00:00:00Z'
Assert-Rejected {
    Assert-DemoStorageExemption -Account $account -AssignmentId 'test-assignment'
} 'Storage exemption differs*'

$script:TestWaiver = New-TestWaiver
$script:TestWaiver.properties.exemptionCategory = 'Mitigated'
Assert-Rejected {
    Assert-DemoStorageExemption -Account $account -AssignmentId 'test-assignment'
} 'Storage exemption differs*'

Write-Host 'Demo ownership, ARM-host, exact-policy, no-expiration and no-broadening guards passed.'

function New-NetworkTestWaiver {
    return [pscustomobject]@{
        id='/test-account/providers/Microsoft.Authorization/policyExemptions/giandoria-public-network'
        properties=[pscustomobject]@{
            policyAssignmentId='test-assignment'
            exemptionCategory='Waiver'
            policyDefinitionReferenceIds=@('network-a','network-b')
            metadata=[pscustomobject]@{project='giandoria';environment='demo'}
        }
    }
}
$waiver=New-NetworkTestWaiver
Assert-DemoNetworkExemption $waiver '/test-account' 'test-assignment' @('network-b','network-a')
foreach ($change in @(
    {param($w) $w.id='/other-account/providers/Microsoft.Authorization/policyExemptions/giandoria-public-network'}
    {param($w) $w.properties.policyAssignmentId='other-assignment'}
    {param($w) $w.properties.policyDefinitionReferenceIds+=@('authentication-control')}
    {param($w) $w.properties.policyDefinitionReferenceIds=@('network-a')}
    {param($w) $w.properties.policyDefinitionReferenceIds=@('network-a','network-a')}
    {param($w) $w.properties.exemptionCategory='Mitigated'}
    {param($w) $w.properties.metadata.project='other'}
    {param($w) $w.properties | Add-Member -NotePropertyName expiresOn -NotePropertyValue '2099-01-01'}
)) {
    $waiver=New-NetworkTestWaiver
    & $change $waiver
    Assert-Rejected { Assert-DemoNetworkExemption $waiver '/test-account' 'test-assignment' @('network-a','network-b') } `
        'Network exemption differs*'
}
$errors=$null
$publisher=[System.Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $PSScriptRoot '..\infra\demo\Deploy-Automation.ps1'),[ref]$null,[ref]$errors)
if ($errors) { throw 'Automation publisher does not parse.' }
$encryption=$publisher.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.HashtableAst] -and
        @($node.KeyValuePairs | Where-Object {$_.Item1.Value -eq 'isEncrypted'}).Count -gt 0
},$true)
if ($encryption.Count -ne 1 -or
    ($encryption[0].KeyValuePairs | Where-Object {$_.Item1.Value -eq 'isEncrypted'}).Item2.SafeGetValue() -ne $true) {
    throw 'Automation publication must explicitly request encrypted configuration.'
}
Write-Host 'Exact-resource network waiver guards and encrypted Automation publication passed.'
