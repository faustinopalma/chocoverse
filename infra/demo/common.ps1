#Requires -Version 7.4
. "$PSScriptRoot\..\shared-foundry\scripts\common.ps1"
. "$PSScriptRoot\..\..\ops\CommandJournal.ps1"
$script:DemoAzJson = (Get-Command Invoke-AzJson).ScriptBlock
$script:DemoAz = (Get-Command Invoke-Az).ScriptBlock

function Invoke-AzJson {
    param([Parameter(Mandatory)][string[]]$Arguments, [switch]$AllowFailure)
    $id = [guid]::NewGuid().ToString()
    Write-CommandRecord -Operation 'az' -Status Started -InvocationId $id -Details @{
        arguments = @(Get-RecordedArguments ($Arguments + @('--only-show-errors', '--output', 'json')))
    }
    try {
        $result = & $script:DemoAzJson -Arguments $Arguments -AllowFailure:$AllowFailure
        Write-CommandRecord -Operation 'az' -Status $(if ($AllowFailure -and $null -eq $result) {
            'Failed'
        } else { 'Succeeded' }) -InvocationId $id -Details @{ outputRecorded = $false }
        return $result
    }
    catch {
        Write-CommandRecord -Operation 'az' -Status Failed -InvocationId $id -Details @{
            exitCode = $LASTEXITCODE; errorType = $_.Exception.GetType().FullName
        }
        throw
    }
}

function Invoke-Az {
    param([Parameter(Mandatory)][string[]]$Arguments)
    Invoke-RecordedNative -FilePath 'az' -Arguments $Arguments
}

function Initialize-DemoContext {
    Import-DotEnv
    Initialize-Tooling
    if (-not $env:AZURE_SUBSCRIPTION_ID -or -not $env:AZURE_TENANT_ID) {
        throw 'Configure the subscription and tenant in .env first.'
    }
    $account = Invoke-AzJson -Arguments @('account', 'show')
    if ($account.id -ne $env:AZURE_SUBSCRIPTION_ID -or $account.tenantId -ne $env:AZURE_TENANT_ID) {
        throw 'Active Azure context does not match .env. No automatic context switch is allowed.'
    }
    $script:DemoSubscriptionScope = "/subscriptions/$($account.id)"
    $script:DemoAccount = $account
    $script:DemoLocal = Join-Path $script:RepoRoot '.local'
    [IO.Directory]::CreateDirectory($script:DemoLocal) | Out-Null
}

function Invoke-DemoArm {
    param(
        [Parameter(Mandatory)][ValidateSet('GET', 'POST')][string]$Method,
        [Parameter(Mandatory)][string]$Path
    )
    if (-not $Path.StartsWith('/')) { throw 'ARM paths must be relative to management.azure.com.' }
    $token = Invoke-AzJson -Arguments @('account', 'get-access-token', '--resource', 'https://management.azure.com/')
    $response = Invoke-RecordedWebRequest -Method $Method -Uri ("https://management.azure.com$Path") -Headers @{
        Authorization = "Bearer $($token.accessToken)"
    } -SkipHttpErrorCheck
    if ([int]$response.StatusCode -notin @(200, 201, 202, 204)) {
        throw "ARM $Method failed ($([int]$response.StatusCode)): $($response.Content)"
    }
    if ($response.Content) { return $response.Content | ConvertFrom-Json -DateKind String }
}

function Assert-DemoOwnership {
    param([Parameter(Mandatory)]$Resource)
    if ((Get-Value $Resource 'tags.project') -ne 'giandoria' -or
        (Get-Value $Resource 'tags.env') -ne 'demo') {
        throw 'Refusing to adopt or modify a resource without the exact Giandoria demo ownership tags.'
    }
}

function Get-DemoDeploymentOutputs {
    $deployment = Invoke-AzJson -Arguments @('deployment', 'sub', 'show', '--name', 'giandoria-demo-foundation')
    if ($deployment.properties.provisioningState -ne 'Succeeded') {
        throw 'The foundation deployment has not succeeded.'
    }
    return $deployment.properties.outputs
}

function Get-DemoStorageTargets {
    $outputs = Get-DemoDeploymentOutputs
    return @(
        [pscustomobject]@{ Group = 'rg-giandoria-core-demo'; Name = $outputs.stateAccountName.value }
        [pscustomobject]@{ Group = 'rg-giandoria-ops-demo'; Name = $outputs.opsAccountName.value }
    )
}

function Get-DemoStorage {
    param([Parameter(Mandatory)]$Target)
    if ($Target.Name -notmatch '^stgiandoria[a-z0-9]+$') { throw 'Unexpected Storage account name.' }
    $path = "$script:DemoSubscriptionScope/resourceGroups/$($Target.Group)" +
        "/providers/Microsoft.Storage/storageAccounts/$($Target.Name)"
    $account = Invoke-DemoArm -Method GET -Path "${path}?api-version=2025-01-01"
    Assert-DemoOwnership $account
    return $account
}

function Get-DemoStorageNetworkAssignment {
    $assignments = Invoke-DemoArm -Method GET -Path (
        "$script:DemoSubscriptionScope/providers/Microsoft.Authorization/policyAssignments?api-version=2023-04-01"
    )
    $candidates = @(
        foreach ($assignment in $assignments.value) {
            if ($assignment.properties.policyDefinitionId -notlike '*policySetDefinitions*') { continue }
            $definition = Invoke-DemoArm -Method GET -Path (
                "$($assignment.properties.policyDefinitionId)?api-version=2023-04-01"
            )
            $references = @($definition.properties.policyDefinitions | Where-Object {
                $_.policyDefinitionReferenceId -eq 'StorageAccountPublicNetworkModify'
            })
            if ($references.Count -eq 0) { continue }
            if ($references.Count -ne 1) { throw 'Ambiguous Storage network policy reference.' }
            $rule = Invoke-DemoArm -Method GET -Path (
                "$($references[0].policyDefinitionId)?api-version=2023-04-01"
            )
            $operations = @(Get-Value $rule 'properties.policyRule.then.details.operations')
            $networkOperations = @($operations | Where-Object {
                $_.field -eq 'Microsoft.Storage/storageAccounts/publicNetworkAccess' -and $_.value -eq 'Disabled'
            })
            if ($networkOperations.Count -ne 1 -or $operations.Count -ne 1) {
                throw 'Storage network rule changed; review it before creating any exemption.'
            }
            $assignment
        }
    )
    if ($candidates.Count -ne 1) { throw 'Expected exactly one effective Storage public-network Modify assignment.' }
    return $candidates[0]
}

function Assert-DemoStorageExemption {
    param([Parameter(Mandatory)]$Account, [Parameter(Mandatory)][string]$AssignmentId)
    $path = "$($Account.id)/providers/Microsoft.Authorization/policyExemptions/" +
        'giandoria-public-storage-poc?api-version=2022-07-01-preview'
    $waiver = Invoke-DemoArm -Method GET -Path $path
    $p = $waiver.properties
    $refs = @($p.policyDefinitionReferenceIds)
    if ($p.policyAssignmentId -ne $AssignmentId -or $p.exemptionCategory -ne 'Waiver' -or
        $refs.Count -ne 1 -or $refs[0] -ne 'StorageAccountPublicNetworkModify' -or
        (Get-Value $p 'expiresOn') -or (Get-Value $p 'metadata.project') -ne 'giandoria') {
        throw 'Storage exemption differs from the owner-approved, non-expiring, single-rule waiver.'
    }
    return $waiver
}

function Test-DemoAnonymousBlobDenial {
    param([int]$StatusCode, [string]$Content)
    return $StatusCode -in @(401, 403) -or (
        $StatusCode -eq 409 -and $Content -cmatch '<Code>PublicAccessNotPermitted</Code>'
    )
}

function Assert-DemoNetworkExemption {
    param(
        [Parameter(Mandatory)]$Waiver,
        [Parameter(Mandatory)][string]$ResourceId,
        [Parameter(Mandatory)][string]$AssignmentId,
        [Parameter(Mandatory)][string[]]$ReferenceIds
    )
    $expectedId="$ResourceId/providers/Microsoft.Authorization/policyExemptions/giandoria-public-network"
    $p=$Waiver.properties
    $actual=@($p.policyDefinitionReferenceIds | Sort-Object -Unique)
    if ($Waiver.id -ine $expectedId -or $p.policyAssignmentId -ine $AssignmentId -or
        $p.exemptionCategory -ne 'Waiver' -or (Get-Value $p 'expiresOn') -or
        @($p.policyDefinitionReferenceIds).Count -ne $ReferenceIds.Count -or
        @(Compare-Object $actual @($ReferenceIds | Sort-Object -Unique)).Count -ne 0 -or
        (Get-Value $p 'metadata.project') -ne 'giandoria' -or
        (Get-Value $p 'metadata.environment') -ne 'demo') {
        throw 'Network exemption differs from the reviewed resource, assignment, exact members or validity.'
    }
}
