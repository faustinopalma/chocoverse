#Requires -Version 7.4
[CmdletBinding()]
param(
    [ValidateSet('Validate','Deploy','Publish')][string]$Stage='Validate',
    [switch]$RunbooksOnly
)
if ($RunbooksOnly -and $Stage -ne 'Publish') { throw 'RunbooksOnly requires Stage=Publish; no infrastructure or schedule timing updates are allowed.' }
. "$PSScriptRoot\common.ps1"
Initialize-DemoContext
$outputs = Get-DemoDeploymentOutputs
$capacities = @(Invoke-AzJson -Arguments @('resource','list','--resource-group','rg-giandoria-fabric-demo','--resource-type','Microsoft.Fabric/capacities'))
if ($capacities.Count -ne 1) { throw 'Expected exactly one demo capacity.' }
Assert-DemoOwnership $capacities[0]
$accountId = "$script:DemoSubscriptionScope/resourceGroups/rg-giandoria-ops-demo/providers/Microsoft.Automation/automationAccounts/aa-giandoria-demo"
$existingAccounts = @(Invoke-AzJson -Arguments @('resource','list','--resource-group','rg-giandoria-ops-demo','--resource-type','Microsoft.Automation/automationAccounts'))
foreach ($existingAccount in $existingAccounts | Where-Object { $_.name -eq 'aa-giandoria-demo' }) {
    Assert-DemoOwnership $existingAccount
}
$parameters = @("stateAccountName=$($outputs.stateAccountName.value)", "capacityName=$($capacities[0].name)")
$template = Join-Path $PSScriptRoot 'automation.bicep'

function Invoke-AutomationArm {
    param([string]$Method,[string]$Path,$Body,[string]$ContentType='application/json',[switch]$AllowNotFound)
    $token = Invoke-AzJson -Arguments @('account','get-access-token','--resource','https://management.azure.com/')
    $args = @{ Method=$Method; Uri="https://management.azure.com$Path"; Headers=@{Authorization="Bearer $($token.accessToken)"} }
    if ($null -ne $Body) {
        $args.Body = if ($Body -is [string]) { $Body } else { $Body | ConvertTo-Json -Depth 25 }
        $args.ContentType=$ContentType
    }
    if ($AllowNotFound) {
        if ($Method -ne 'GET') { throw 'AllowNotFound applies only to read-only discovery.' }
        $response=Invoke-RecordedWebRequest @args -SkipHttpErrorCheck
        if ([int]$response.StatusCode -eq 404) { return $null }
        if ([int]$response.StatusCode -ne 200) { throw "Automation discovery failed: HTTP $($response.StatusCode)." }
        return $response
    }
    return Invoke-RecordedWebRequest @args
}
function Get-AutomationBindings {
    $page="$accountId/jobSchedules?api-version=2024-10-23"
    while ($page) {
        $list=Invoke-DemoArm GET $page
        foreach ($item in $list.value) {
            # List responses omit bound parameters; only individual GETs are authoritative.
            Invoke-DemoArm GET "$($item.id)?api-version=2024-10-23"
        }
        $next=Get-Value $list 'nextLink'
        $page=if ($next) {
            $uri=[uri]$next
            if ($uri.Scheme -ne 'https' -or $uri.Host -ne 'management.azure.com' -or
                -not $uri.AbsolutePath.StartsWith("$accountId/jobSchedules", [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Unexpected Automation binding pagination URL.'
            }
            $uri.PathAndQuery
        } else { '' }
    }
}
function Get-AutomationBindingSignature {
    param($Properties)
    if ($Properties -is [Collections.IDictionary]) { $Properties=[pscustomobject]$Properties }
    $parameters=Get-Value $Properties 'parameters'
    $sorted=[ordered]@{}
    if ($parameters) {
        $keys=if ($parameters -is [Collections.IDictionary]) { $parameters.Keys } else { $parameters.PSObject.Properties | ForEach-Object Name }
        foreach ($key in @($keys | Sort-Object)) { $sorted[$key]=$parameters.$key }
    }
    return [ordered]@{
        runbook=$Properties.runbook.name; schedule=$Properties.schedule.name
        runOn=Get-Value $Properties 'runOn'; parameters=$sorted
    } | ConvertTo-Json -Depth 10 -Compress
}
function Set-AutomationBinding {
    param($Properties)
    if ($Properties -is [Collections.IDictionary]) { $Properties=[pscustomobject]$Properties }
    $id=[guid]::NewGuid().ToString()
    $body=@{runbook=$Properties.runbook;schedule=$Properties.schedule;parameters=$Properties.parameters}
    if (Get-Value $Properties 'runOn') { $body.runOn=$Properties.runOn }
    Invoke-AutomationArm PUT "$accountId/jobSchedules/${id}?api-version=2024-10-23" @{properties=$body} | Out-Null
    $created=Invoke-DemoArm GET "$accountId/jobSchedules/${id}?api-version=2024-10-23"
    if ((Get-AutomationBindingSignature $created.properties) -cne (Get-AutomationBindingSignature $Properties)) {
        throw "Automation binding $id did not retain its requested arguments."
    }
    return $created
}
function Repair-AutomationBinding {
    param($Existing,$Properties)
    Write-Warning "Replacing Automation binding for $($Properties.runbook.name)/$($Properties.schedule.name); persisted arguments differ."
    # PUT on an existing ID can silently ignore parameters; a deleted ID can also remain reserved.
    Invoke-AutomationArm DELETE "$($Existing.id)?api-version=2024-10-23" | Out-Null
    return Set-AutomationBinding $Properties
}
if ($Stage -eq 'Validate') {
    Invoke-Az -Arguments @('bicep','build','--file',$template,'--outfile',(Join-Path $script:DemoLocal 'automation-template.json'))
    Invoke-AzJson -Arguments (@('deployment','sub','validate','--location','swedencentral','--template-file',$template,'--parameters')+$parameters) | Out-Null
    Invoke-Az -Arguments (@('deployment','sub','what-if','--location','swedencentral','--template-file',$template,'--parameters')+$parameters+@('--no-pretty-print','--only-show-errors'))
    return
}
if ($Stage -eq 'Deploy') {
    Invoke-AzJson -Arguments (@('deployment','sub','create','--name','giandoria-demo-automation','--location','swedencentral','--template-file',$template,'--parameters')+$parameters) |
        ForEach-Object { Write-JsonFile $_ (Join-Path $script:DemoLocal 'automation-deployment.json') }
}
$account = Invoke-DemoArm GET "${accountId}?api-version=2024-10-23"
Assert-DemoOwnership $account
$runtimeJobId = ''
$jobRecord = Join-Path $script:DemoLocal 'runtime-deployment.json'
if (Test-Path -LiteralPath $jobRecord) {
    $runtimeJobId = (Get-Content -Raw -LiteralPath $jobRecord | ConvertFrom-Json).properties.outputs.jobId.value
}
$config = @{
    project='giandoria'; location='swedencentral'; subscriptionId=$script:DemoAccount.id; tenantId=$script:DemoAccount.tenantId
    automationId=$accountId; capacityId=$capacities[0].id; stateAccount=$outputs.stateAccountName.value
    runtimeJobId=$runtimeJobId
}
if (-not $RunbooksOnly) {
    Invoke-AutomationArm PUT "$accountId/variables/GiandoriaConfig?api-version=2024-10-23" @{
        properties=@{ isEncrypted=$true; value=($config | ConvertTo-Json -Compress) }
    } | Out-Null
}
$storedConfig=Invoke-DemoArm GET "$accountId/variables/GiandoriaConfig?api-version=2024-10-23"
if ($storedConfig.properties.isEncrypted -ne $true) { throw 'Automation configuration must remain encrypted.' }
$source = Join-Path $script:RepoRoot 'ops\automation'
$common = Get-Content -Raw -LiteralPath (Join-Path $source 'LabControl.ps1')
$bindings=@(Get-AutomationBindings)
Write-JsonFile $bindings (Join-Path $script:DemoLocal 'automation-bindings-before-publish.json')
$hourly=@($bindings | Where-Object { $_.properties.schedule.name -eq 'ReconcileHourly' })
if ($hourly.Count -gt 1 -or ($hourly.Count -eq 1 -and $hourly[0].properties.runbook.name -ne 'Stop-GiandoriaLab')) {
    throw 'Unexpected reconciliation bindings; inspect before publishing.'
}
$reconcile=@{runbook=@{name='Stop-GiandoriaLab'};schedule=@{name='ReconcileHourly'};parameters=[pscustomobject]@{Reconcile='True'}}
if ($hourly.Count -eq 1 -and
    (Get-AutomationBindingSignature $hourly[0].properties) -cne (Get-AutomationBindingSignature $reconcile)) {
    $replacement=Repair-AutomationBinding $hourly[0] $reconcile
    $bindings=@($bindings | Where-Object { $_.id -ne $hourly[0].id }) + @($replacement)
}
if ($RunbooksOnly -and $hourly.Count -eq 0) { throw 'RunbooksOnly requires an existing ReconcileHourly binding.' }
foreach ($name in @('Start-GiandoriaLab','Extend-GiandoriaLab','Stop-GiandoriaLab')) {
    if ($RunbooksOnly) {
        $current=if ($name -eq 'Extend-GiandoriaLab') {
            $response=Invoke-AutomationArm GET "$accountId/runbooks/${name}?api-version=2024-10-23" -AllowNotFound
            if ($response) { $response.Content | ConvertFrom-Json }
        } else { Invoke-DemoArm GET "$accountId/runbooks/${name}?api-version=2024-10-23" }
        if ($current) {
            Assert-DemoOwnership $current
            if ($current.properties.runtimeEnvironment -ne 'GiandoriaPowerShell' -or
                $current.properties.state -notin @('Published','Edit')) {
                throw "RunbooksOnly requires an existing Published $name bound to GiandoriaPowerShell."
            }
            if ($current.properties.state -eq 'Edit') {
                $texts=@{}
                foreach ($kind in @('content','draft/content')) {
                    $response=Invoke-AutomationArm GET "$accountId/runbooks/$name/${kind}?api-version=2024-10-23"
                    $text=if ($response.Content -is [byte[]]) { [Text.Encoding]::UTF8.GetString($response.Content) }
                        else { [string]$response.Content }
                    $texts[$kind]=$text.Replace("`r`n","`n").Trim()
                }
                if ($texts.content -cne $texts.'draft/content') {
                    throw "Runbook $name has an unpublished draft; refusing to overwrite operator changes."
                }
            }
        } elseif ($name -ne 'Extend-GiandoriaLab') {
            throw "RunbooksOnly cannot create $name."
        }
    }
    $path = Join-Path $source "$name.ps1"
    $parseErrors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$null, [ref]$parseErrors)
    if ($parseErrors) { throw "Runbook $name does not parse." }
    $help = $ast.GetHelpContent()
    if (-not $help -or -not $help.Synopsis) { throw "Runbook $name requires an operator description in its help synopsis." }
    $description = ($help.Synopsis -replace '\s+', ' ').Trim()
    if ($description.Length -gt 512) { throw "Runbook $name description exceeds Azure's 512-character limit." }
    Invoke-AutomationArm PUT "$accountId/runbooks/${name}?api-version=2024-10-23" @{
        location='swedencentral'; tags=@{project='giandoria';env='demo';'managed-by'='bicep'}
        properties=@{
            runbookType='PowerShell';runtimeEnvironment='GiandoriaPowerShell';logProgress=$false;logVerbose=$true
            description=$description
        }
    } | Out-Null
    $content = (Get-Content -Raw -LiteralPath $path).Replace('. "$PSScriptRoot\LabControl.ps1"', $common)
    Invoke-AutomationArm PUT "$accountId/runbooks/$name/draft/content?api-version=2024-10-23" $content 'text/powershell' | Out-Null
    Invoke-AutomationArm POST "$accountId/runbooks/$name/publish?api-version=2024-10-23" | Out-Null
    $until=[datetime]::UtcNow.AddMinutes(2)
    do {
        $published = Invoke-DemoArm GET "$accountId/runbooks/${name}?api-version=2024-10-23"
        if ($published.properties.state -eq 'Published') { break }
        Start-Sleep -Seconds 3
    } while ([datetime]::UtcNow -lt $until)
    if ($published.properties.state -ne 'Published') { throw "Runbook $name did not reach Published." }
    if ($published.properties.runtimeEnvironment -ne 'GiandoriaPowerShell') { throw "Runbook $name has an unexpected runtime binding." }
    if ($published.properties.description -ne $description) { throw "Runbook $name operator description differs from the requested source." }
    $until=[datetime]::UtcNow.AddMinutes(2)
    do {
        $publishedContent=(Invoke-AutomationArm GET "$accountId/runbooks/$name/content?api-version=2024-10-23").Content
        $publishedText=if ($publishedContent -is [byte[]]) { [Text.Encoding]::UTF8.GetString($publishedContent) } else { [string]$publishedContent }
        if ($publishedText.Replace("`r`n","`n").Trim() -eq $content.Replace("`r`n","`n").Trim()) { break }
        Start-Sleep -Seconds 3
    } while ([datetime]::UtcNow -lt $until)
    if ($publishedText.Replace("`r`n","`n").Trim() -ne $content.Replace("`r`n","`n").Trim()) {
        throw "Runbook $name published content differs from the requested source."
    }
}
$verifiedBindings=@(Get-AutomationBindings)
foreach ($before in $bindings) {
    # Publishing can rotate binding IDs while retaining the runbook/schedule association.
    $after=@($verifiedBindings | Where-Object {
        $_.properties.runbook.name -eq $before.properties.runbook.name -and
        $_.properties.schedule.name -eq $before.properties.schedule.name
    })
    if ($after.Count -gt 1) { throw "Publication left duplicate bindings for $($before.properties.schedule.name)." }
    if ($after.Count -eq 0) {
        Write-Warning "Restoring Automation binding removed during publication: $($before.id)."
        Set-AutomationBinding $before.properties | Out-Null
    }
    elseif ((Get-AutomationBindingSignature $after[0].properties) -cne (Get-AutomationBindingSignature $before.properties)) {
        Repair-AutomationBinding $after[0] $before.properties | Out-Null
    }
}
Write-JsonFile @(Get-AutomationBindings) (Join-Path $script:DemoLocal 'automation-bindings-after-publish.json')
$runtime = Invoke-DemoArm GET "$accountId/runtimeEnvironments/GiandoriaPowerShell?api-version=2024-10-23"
if ($runtime.properties.runtime.language -ne 'PowerShell' -or $runtime.properties.runtime.version -ne '7.4') {
    throw 'The deployed runtime is not PowerShell 7.4.'
}
if ($RunbooksOnly) {
    Write-Host 'Start/Extend/Stop source, descriptions and bound schedule arguments verified; configuration, schedule timing and running sessions untouched.'
    return
}
$firstRun=[datetimeoffset]::UtcNow.AddHours(1).ToString('o')
Invoke-AutomationArm PUT "$accountId/schedules/ReconcileHourly?api-version=2024-10-23" @{
    properties=@{startTime=$firstRun;frequency='Hour';interval=1;timeZone='UTC';isEnabled=$true}
} | Out-Null
$hourly=@(Get-AutomationBindings | Where-Object { $_.properties.schedule.name -eq 'ReconcileHourly' })
if ($hourly.Count -eq 0) { Set-AutomationBinding $reconcile | Out-Null }
elseif ($hourly.Count -ne 1 -or
    (Get-AutomationBindingSignature $hourly[0].properties) -cne (Get-AutomationBindingSignature $reconcile)) {
    throw 'Reconciliation arguments changed during publication.'
}
Write-Host 'Automation runbooks published; no capacity resumed.'
