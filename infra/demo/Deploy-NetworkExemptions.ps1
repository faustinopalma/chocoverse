#Requires -Version 7.4
[CmdletBinding()]
param([ValidateSet('Validate','Deploy')][string]$Stage='Validate')
. "$PSScriptRoot\common.ps1"
Initialize-DemoContext

$networkMembers=@{
    storage=@(
        '34c877ad-507e-4c82-993e-3452a6e0ad3c'
        '2a1a9cdf-e04d-429a-8416-3bfb72a1b26f'
        '6edd7eda-6dd8-40f7-810d-67160c639cd9'
    )
    registry=@('d0793b48-0edc-4296-a390-4c75d1bdfd71','e8eef0a8-67cf-4eb4-9386-14b0e78733d4')
    foundry=@('037eea7a-bd0a-46c5-9a66-03aea78705d3','d6759c02-b87f-42b7-892e-71b3f471d782')
}
$reasons=@{
    storage='Synthetic business events and restart state do not require a private-only perimeter. Entra RBAC, HTTPS/TLS 1.2, disabled Shared Key and anonymous blobs remain enforced. Public routing avoids standing network cost and private DNS/worker connectivity complexity in an on-demand lab. Network exposure is accepted, not equivalent isolation. Reassess before confidential data, production use, new consumers or weaker controls.'
    registry='This nonproduction registry holds lab code and dependency images, not confidential business datasets. Entra RBAC, disabled admin credentials and anonymous pulls, and digest-pinned deployments remain enforced. Basic public ACR avoids the SKU and private-connectivity overhead of Private Link. Only network isolation is waived; vulnerability findings and image integrity are not waived. Reassess for confidential code, production use, new consumers or weaker controls.'
    foundry='This shared nonproduction model endpoint supports low-sensitivity experiments; Giandoria sends synthetic enterprise summaries. Entra-only authentication, RBAC and HTTPS remain enforced. Authenticated public inference avoids private DNS and network coupling between experimental clients. This account-scoped waiver covers all consumers: each must review data classification before confidential or production use. Only network isolation is waived, not model access, diagnostics or usage controls.'
}
$controls=@{
    storage='Entra RBAC; HTTPS/TLS 1.2; no Shared Key; no anonymous blobs; retained checkpoints'
    registry='Entra RBAC; no admin account; no anonymous pulls; digest-pinned deployment; Defender scanning unchanged'
    foundry='Entra-only authentication; scoped model roles; HTTPS; diagnostics and Defender settings unchanged'
}
$assignments=Invoke-DemoArm GET (
    "$script:DemoSubscriptionScope/providers/Microsoft.Authorization/policyAssignments?api-version=2023-04-01"
)
if (Get-Value $assignments 'nextLink') { throw 'Effective assignment discovery requires pagination review.' }
$baseline=@($assignments.value | Where-Object {
    $_.properties.policyDefinitionId -ieq
        '/providers/Microsoft.Authorization/policySetDefinitions/1f3afdf9-d0c9-4c3d-847f-89da613e70a8'
})
if ($baseline.Count -ne 1) { throw 'Expected one effective built-in security baseline assignment.' }
$assignment=$baseline[0]
$initiative=Invoke-DemoArm GET "$($assignment.properties.policyDefinitionId)?api-version=2023-04-01"
$refs=@{}
foreach ($kind in $networkMembers.Keys) {
    $refs[$kind]=@(
        foreach ($definition in $networkMembers[$kind]) {
            $members=@($initiative.properties.policyDefinitions | Where-Object {
                $_.policyDefinitionId -ieq "/providers/Microsoft.Authorization/policyDefinitions/$definition"
            })
            if ($members.Count -ne 1) { throw "Network policy $definition no longer has one exact initiative member." }
            $rule=Invoke-DemoArm GET "$($members[0].policyDefinitionId)?api-version=2023-04-01"
            $effect=$rule.properties.policyRule.then.effect
            if ($effect -notin @('Audit','AuditIfNotExists',"[parameters('effect')]")) {
                throw 'The reviewed audit rule changed; no automatic exemption broadening is permitted.'
            }
            $members[0].policyDefinitionReferenceId
        }
    )
}
$outputs=Get-DemoDeploymentOutputs
$resources=@(Invoke-AzJson -Arguments @('resource','list'))
$targets=@(
    [pscustomobject]@{kind='storage';name=$outputs.stateAccountName.value;group='rg-giandoria-core-demo'}
    [pscustomobject]@{kind='storage';name=$outputs.opsAccountName.value;group='rg-giandoria-ops-demo'}
    [pscustomobject]@{kind='registry';name=$outputs.registryName.value;group='rg-giandoria-core-demo'}
)
$shared=@($resources | Where-Object {
    $_.type -ieq 'Microsoft.CognitiveServices/accounts' -and $_.resourceGroup -eq 'rg-shared-ai-swedencentral'
})
if ($shared.Count -ne 1 -or $shared[0].name -notmatch '^aif-shared-swedencentral-[a-z0-9]{6}$' -or
    (Get-Value $shared[0] 'tags.scope') -ne 'shared' -or
    (Get-Value $shared[0] 'tags.workload') -ne 'ai-models' -or
    (Get-Value $shared[0] 'tags.managed-by') -ne 'bicep') {
    throw 'Shared Foundry ownership or identity differs from the reviewed experimental account.'
}
$targets+=[pscustomobject]@{kind='foundry';name=$shared[0].name;group=$shared[0].resourceGroup}
$modifyAssignment=Get-DemoStorageNetworkAssignment
$plan=@()
$priorFile=Join-Path $script:DemoLocal 'network-waiver-deployment.json'
$prior=if (Test-Path -LiteralPath $priorFile) { @(Get-Content -Raw $priorFile | ConvertFrom-Json) } else { @() }
foreach ($target in $targets) {
    $type=@{storage='Microsoft.Storage/storageAccounts';registry='Microsoft.ContainerRegistry/registries'
        foundry='Microsoft.CognitiveServices/accounts'}[$target.kind]
    $versions=@{storage='2025-01-01';registry='2025-04-01';foundry='2025-06-01'}
    $id="$script:DemoSubscriptionScope/resourceGroups/$($target.group)/providers/$type/$($target.name)"
    $resource=Invoke-DemoArm GET "${id}?api-version=$($versions[$target.kind])"
    if ($target.kind -ne 'foundry') { Assert-DemoOwnership $resource }
    if ($resource.location -ne 'swedencentral' -or $resource.properties.publicNetworkAccess -ne 'Enabled') {
        throw 'Resource region or public-network design changed; review before exempting.'
    }
    if ($target.kind -eq 'storage' -and ($resource.properties.allowSharedKeyAccess -ne $false -or
        $resource.properties.allowBlobPublicAccess -ne $false -or
        $resource.properties.supportsHttpsTrafficOnly -ne $true -or
        $resource.properties.minimumTlsVersion -ne 'TLS1_2')) {
        throw 'Storage retained authentication/transport controls are not satisfied.'
    }
    if ($target.kind -eq 'registry' -and ($resource.sku.name -ne 'Basic' -or
        $resource.properties.adminUserEnabled -ne $false -or
        $resource.properties.anonymousPullEnabled -ne $false)) {
        throw 'Registry retained authentication/SKU controls are not satisfied.'
    }
    if ($target.kind -eq 'foundry' -and $resource.properties.disableLocalAuth -ne $true) {
        throw 'Shared model inference must remain Entra-only.'
    }
    $existing=Invoke-DemoArm GET "$id/providers/Microsoft.Authorization/policyExemptions?api-version=2022-07-01-preview"
    if (Get-Value $existing 'nextLink') { throw 'Resource exemption list requires pagination review.' }
    $own=@($existing.value | Where-Object name -eq 'giandoria-public-network')
    if ($own.Count -gt 1) { throw 'Duplicate named network exemptions.' }
    if ($own.Count) {
        Assert-DemoNetworkExemption $own[0] $id $assignment.id $refs[$target.kind]
    } elseif (@($prior | Where-Object resourceId -ieq $id).Count) {
        throw 'A previously deployed network exemption is missing. Do not automatically recreate it.'
    }
    $params=@{
        targetKind=@{value=$target.kind}; targetName=@{value=$target.name}
        policyAssignmentId=@{value=$assignment.id}; policyDefinitionReferenceIds=@{value=$refs[$target.kind]}
        justification=@{value=$reasons[$target.kind]}; retainedControls=@{value=$controls[$target.kind]}
    }
    $parameterPath=Join-Path $script:DemoLocal "network-waiver-$($target.name).parameters.json"
    Write-JsonFile @{parameters=$params} $parameterPath
    $plan+=@{resourceId=$id;group=$target.group;template='network-exemption.bicep'
        parameters=$parameterPath;references=$refs[$target.kind];assignmentId=$assignment.id
        exemptionName='giandoria-public-network';existed=[bool]$own.Count}
    if ($target.kind -eq 'storage') {
        Assert-DemoStorageExemption $resource $modifyAssignment.id | Out-Null
        $modifyPath=Join-Path $script:DemoLocal "storage-waiver-$($target.name).parameters.json"
        Write-JsonFile @{parameters=@{storageAccountName=@{value=$target.name}
            policyAssignmentId=@{value=$modifyAssignment.id}}} $modifyPath
        $plan+=@{resourceId=$id;group=$target.group;template='storage-exemption.bicep';parameters=$modifyPath
            references=@('StorageAccountPublicNetworkModify');assignmentId=$modifyAssignment.id
            exemptionName='giandoria-public-storage-poc';existed=$true}
    }
}
foreach ($entry in $plan) {
    $arguments=@('--resource-group',$entry.group,'--template-file',(Join-Path $PSScriptRoot $entry.template),
        '--parameters',"@$($entry.parameters)")
    $validation=Invoke-AzJson -Arguments (@('deployment','group','validate')+$arguments)
    if ($validation.properties.provisioningState -notin @('Succeeded','Accepted')) {
        throw 'Policy exemption ARM validation failed.'
    }
    $whatIf=Invoke-AzJson -Arguments (@('deployment','group','what-if')+$arguments+@('--no-pretty-print'))
    $expected="$($entry.resourceId)/providers/Microsoft.Authorization/policyExemptions/$($entry.exemptionName)"
    foreach ($change in $whatIf.changes) {
        if ($change.changeType -eq 'Ignore') { continue }
        if ($change.resourceId -ine $expected -or $change.changeType -notin @('Create','Modify','NoChange')) {
            throw 'Exemption what-if includes an unexpected target or destructive change.'
        }
    }
    Write-JsonFile $whatIf (Join-Path $script:DemoLocal "$($entry.exemptionName)-$(($entry.resourceId -split '/')[-1])-what-if.json")
}
Write-JsonFile $plan (Join-Path $script:DemoLocal 'network-waiver-validation.json')
if ($Stage -eq 'Validate') { Write-Host 'Validated six resource-scoped waivers; no service configuration changes.'; return }
foreach ($entry in $plan) {
    $result=Invoke-AzJson -Arguments @('deployment','group','create','--name',
        "$($entry.exemptionName)-$(($entry.resourceId -split '/')[-1])",'--resource-group',$entry.group,
        '--template-file',(Join-Path $PSScriptRoot $entry.template),'--parameters',"@$($entry.parameters)")
    if ($result.properties.provisioningState -ne 'Succeeded') { throw 'Exemption deployment did not succeed.' }
    $waiver=Invoke-DemoArm GET (
        "$($entry.resourceId)/providers/Microsoft.Authorization/policyExemptions/$($entry.exemptionName)" +
        '?api-version=2022-07-01-preview'
    )
    if ($entry.exemptionName -eq 'giandoria-public-network') {
        Assert-DemoNetworkExemption $waiver $entry.resourceId $entry.assignmentId $entry.references
    } else {
        Assert-DemoStorageExemption ([pscustomobject]@{id=$entry.resourceId}) $entry.assignmentId | Out-Null
    }
    if ($waiver.properties.description.Length -lt 100 -or
        (Get-Value $waiver 'properties.metadata.rationaleDocument') -ne 'docs/19-policy-exemption-experiment.md') {
        throw 'Deployed exemption is missing its reviewer rationale.'
    }
    Write-Host "$(($entry.resourceId -split '/')[-1]): $($entry.exemptionName) verified."
    $prior=@($prior | Where-Object {
        $_.resourceId -ine $entry.resourceId -or $_.exemptionName -ne $entry.exemptionName
    })+@($entry)
    Write-JsonFile $prior $priorFile
}
Write-Host 'Exact-member network waivers deployed. Authentication, service configuration and Defender remain unchanged.'
