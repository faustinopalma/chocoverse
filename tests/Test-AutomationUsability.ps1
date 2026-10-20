#Requires -Version 7.4
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=Split-Path $PSScriptRoot
$source=Join-Path $root 'ops\automation'
foreach ($name in @('Start-GiandoriaLab','Extend-GiandoriaLab','Stop-GiandoriaLab')) {
    $errors=$null
    $ast=[System.Management.Automation.Language.Parser]::ParseFile(
        (Join-Path $source "$name.ps1"),[ref]$null,[ref]$errors)
    if ($errors) { throw "$name does not parse." }
    $help=$ast.GetHelpContent()
    if (-not $help -or -not $help.Synopsis -or -not $help.Examples.Count) { throw "$name requires synopsis and examples." }
    $text=Get-Content -Raw (Join-Path $source "$name.ps1")
    $iacDescription=($text.Split('.SYNOPSIS')[1].Split('.DESCRIPTION')[0].Replace("`r",'').Replace("`n",' ')).Trim()
    if ($iacDescription -cne ($help.Synopsis -replace '\s+',' ').Trim()) {
        throw "$name synopsis formatting differs between Bicep and the publisher."
    }
    if ($iacDescription.Length -gt 512) { throw "$name description exceeds Azure's 512-character limit." }
    foreach ($parameter in $ast.ParamBlock.Parameters) {
        if (-not $help.Parameters.ContainsKey($parameter.Name.VariablePath.UserPath.ToUpperInvariant())) {
            throw "$name lacks help for $($parameter.Name)."
        }
    }
    $names=@($ast.ParamBlock.Parameters.Name.VariablePath.UserPath)
    $expected=if ($name -eq 'Start-GiandoriaLab') {
        @('MaxWallMinutes','Mode','Speed','SessionId','ControlJobId','Operation','ExtensionMinutes')
    } elseif ($name -eq 'Extend-GiandoriaLab') { @('ExtensionMinutes','SessionId','ControlJobId') }
    else { @('Force','SessionId','ControlJobId','IfExpired','Reconcile') }
    if (($names -join ',') -ne ($expected -join ',')) { throw "$name operator parameter order differs." }
}
$script:RepoRoot=$root
$script:DemoSubscriptionScope='/subscriptions/offline-test'
$script:DemoAccount=@{id='offline-test';tenantId='offline-test'}
$script:DemoLocal=Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
[IO.Directory]::CreateDirectory($script:DemoLocal)|Out-Null
$script:Mutations=[Collections.Generic.List[string]]::new()
$script:Books=@{}
$script:Contents=@{}
$script:DraftContents=@{}
$script:Bindings=@{}
$script:DeletedBindings=[Collections.Generic.HashSet[string]]::new()
$script:CorruptOnPublish=$false
$script:IgnoreNewArguments=$false
$script:BindingReads=0
$script:ExtendDiscoveryStatus=0
function Reset-TestBindings {
    param([switch]$Unsafe)
    $script:Bindings=@{
        hourly=@{
            id="$script:DemoSubscriptionScope/jobSchedules/hourly"
            properties=@{runbook=@{name='Stop-GiandoriaLab'};schedule=@{name='ReconcileHourly'}
                parameters=$(if ($Unsafe) {@{}} else {@{Reconcile='True'}});runOn=$null}
        }
        deadline=@{
            id="$script:DemoSubscriptionScope/jobSchedules/deadline"
            properties=@{runbook=@{name='Stop-GiandoriaLab'};schedule=@{name='stop-session'}
                parameters=@{SessionId='recorded-session';IfExpired='True'};runOn='test-worker'}
        }
    }
}
Reset-TestBindings
function Initialize-DemoContext {}
function Get-Value {
    param($Value,$Name)
    foreach ($part in $Name.Split('.')) {
        if ($null -eq $Value) { return $null }
        $property=$Value.PSObject.Properties[$part]
        if (-not $property) { return $null }
        $Value=$property.Value
    }
    return $Value
}
function Write-JsonFile { param($Value,$Path) }
function Get-DemoDeploymentOutputs { return @{stateAccountName=@{value='stgiandoriatest'}} }
function Assert-DemoOwnership {
    param($Resource)
    $record=$Resource | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    if ($record.tags.project -ne 'giandoria' -or $record.tags.env -ne 'demo') {
        throw 'Refusing to adopt an unowned resource.'
    }
}
function Invoke-AzJson {
    param($Arguments)
    if ($Arguments[0] -eq 'account') { return @{accessToken='offline-token'} }
    $rg=$Arguments[[array]::IndexOf($Arguments,'--resource-group')+1]
    if ($rg -eq 'rg-giandoria-fabric-demo') { return @{id='/capacity';name='fcgiandoriatest';tags=@{project='giandoria';env='demo'}} }
    return @{name='aa-giandoria-demo';tags=@{project='giandoria';env='demo'}}
}
function Invoke-DemoArm {
    param($Method,$Path)
    if ($Method -ne 'GET') { throw 'Publisher read helper attempted a mutation.' }
    if ($Path -match '/jobSchedules/([^/?]+)\?') {
        $script:BindingReads++
        return $script:Bindings[$Matches[1]] | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    }
    if ($Path -like '*/jobSchedules?*') {
        $items=@($script:Bindings.Values | Sort-Object id)
        $page=if ($Path -like '*page=2*') { @($items | Select-Object -Skip 1) } else { @($items | Select-Object -First 1) }
        $result=@{value=@($page | ForEach-Object {@{id=$_.id;properties=@{parameters=$null}}})}
        if ($Path -notlike '*page=2*' -and $items.Count -gt 1) {
            $result.nextLink="https://management.azure.com$script:DemoSubscriptionScope/resourceGroups/rg-giandoria-ops-demo/providers/Microsoft.Automation/automationAccounts/aa-giandoria-demo/jobSchedules?api-version=2024-10-23&page=2"
        }
        return $result | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    }
    if ($Path -like '*/variables/*') { return @{properties=@{isEncrypted=$true}} }
    if ($Path -like '*/runtimeEnvironments/*') { return @{properties=@{runtime=@{language='PowerShell';version='7.4'}}} }
    if ($Path -match '/runbooks/([^/?]+)\?') {
        $name=$Matches[1]
        if ($script:Books.ContainsKey($name)) { return $script:Books[$name] }
        return @{tags=@{project='giandoria';env='demo'};properties=@{state='Published';runtimeEnvironment='GiandoriaPowerShell'}}
    }
    return @{tags=@{project='giandoria';env='demo'}}
}
function Invoke-RecordedWebRequest {
    param($Method,$Uri,$Headers,$Body,$ContentType,[switch]$SkipHttpErrorCheck)
    if (-not $Uri.StartsWith('https://management.azure.com/')) { throw 'Unexpected publisher host.' }
    $Path=([uri]$Uri).PathAndQuery
    if ($Method -ne 'GET') {
        $script:Mutations.Add("$Method $Path")
        if ($Path -notmatch '/runbooks/|/jobSchedules/') { throw "RunbooksOnly changed an out-of-scope resource: $Path" }
    }
    if ($Path -match '/jobSchedules/([^/?]+)\?') {
        $id=$Matches[1]
        if ($Method -eq 'DELETE') {
            $script:Bindings.Remove($id)
            $script:DeletedBindings.Add($id)|Out-Null
        }
        elseif ($Method -eq 'PUT') {
            if ($script:DeletedBindings.Contains($id)) { throw 'Deleted binding IDs cannot be reused.' }
            if (-not $script:Bindings.ContainsKey($id)) {
                $record=$Body|ConvertFrom-Json -AsHashtable
                if ($script:IgnoreNewArguments) { $record.properties.parameters=@{} }
                $record.id=$Path.Split('?')[0]
                $script:Bindings[$id]=$record
            }
            # Existing-ID PUT succeeds but ignores new arguments, matching the observed service behavior.
        }
        else { throw "Unexpected binding mutation: $Method" }
        return @{}
    }
    if ($Path -match '/runbooks/([^/?]+)(.*)') {
        $name=$Matches[1];$tail=$Matches[2]
        if ($Method -eq 'GET' -and $tail -like '?api-version=*') {
            if ($script:ExtendDiscoveryStatus) { return @{StatusCode=$script:ExtendDiscoveryStatus;Content='Discovery denied'} }
            if ($script:Books.ContainsKey($name)) {
                return @{StatusCode=200;Content=($script:Books[$name]|ConvertTo-Json -Depth 8)}
            }
            return @{StatusCode=404;Content='Runbook not found'}
        }
        if ($tail -like '/draft/content?*' -and $Method -eq 'GET') {
            $text=if ($script:DraftContents.ContainsKey($name)) { $script:DraftContents[$name] } else { $script:Contents[$name] }
            return @{Content=$text}
        }
        elseif ($tail -like '/draft/content?*') { $script:Contents[$name]=$Body }
        elseif ($tail -like '/content?*') { return @{Content=$script:Contents[$name]} }
        elseif ($tail -like '/publish?*') {
            $script:Books[$name].properties.state='Published'
            if ($script:CorruptOnPublish -and $name -eq 'Stop-GiandoriaLab') {
                ($script:Bindings.Values | Where-Object {$_.properties.schedule.name -eq 'stop-session'}).properties.parameters=@{}
                $script:CorruptOnPublish=$false
            }
            if ($name -eq 'Stop-GiandoriaLab') {
                $rotated=@{}
                foreach ($binding in $script:Bindings.Values) {
                    $newId=[guid]::NewGuid().ToString()
                    $binding.id="$script:DemoSubscriptionScope/jobSchedules/$newId"
                    $rotated[$newId]=$binding
                }
                $script:Bindings=$rotated
            }
        }
        else { $script:Books[$name]=$Body|ConvertFrom-Json -AsHashtable }
        return @{}
    }
    throw "Unexpected publisher request: $Path"
}
try {
    $publisher=Get-Content -Raw (Join-Path $root 'infra\demo\Deploy-Automation.ps1')
    $publisher=$publisher.Replace('. "$PSScriptRoot\common.ps1"','')
    $publisher=$publisher.Replace("Join-Path `$PSScriptRoot 'automation.bicep'", "Join-Path '$root\infra\demo' 'automation.bicep'")
    $block=[scriptblock]::Create($publisher)
    & $block -Stage Publish -RunbooksOnly
    if ($script:Mutations.Count -ne 9) { throw 'Expected exactly source/metadata/publish changes for Start/Extend/Stop.' }
    foreach ($name in @('Start-GiandoriaLab','Extend-GiandoriaLab','Stop-GiandoriaLab')) {
        if (-not $script:Books[$name].properties.description -or
            $script:Contents[$name] -notmatch 'function Write-ControlSessionSummary') {
            throw 'Published runbook lacks its description or bundled shared controller.'
        }
        $errors=$null
        [Management.Automation.Language.Parser]::ParseInput($script:Contents[$name],[ref]$null,[ref]$errors)|Out-Null
        if ($errors) { throw "Bundled $name does not parse." }
    }
    if ($script:Books['Start-GiandoriaLab'].properties.description -notmatch '8760 ~ year/hour' -or
        $script:Books['Extend-GiandoriaLab'].properties.description -notmatch '240 = \+4h') {
        throw 'Published Start description lacks a concrete speed example.'
    }
    if ($script:BindingReads -lt 6) { throw 'Publication did not individually verify all paginated bindings.' }
    $beforeCount=$script:Mutations.Count
    $script:Books['Extend-GiandoriaLab'].properties.state='Edit'
    & $block -Stage Publish -RunbooksOnly
    if ($script:Mutations.Count - $beforeCount -ne 9 -or $script:DeletedBindings.Count) {
        throw 'Repeated publication unnecessarily replaced healthy bindings.'
    }
    Reset-TestBindings -Unsafe
    $beforeCount=$script:Mutations.Count
    & $block -Stage Publish -RunbooksOnly
    $hourly=@($script:Bindings.Values | Where-Object {$_.properties.schedule.name -eq 'ReconcileHourly'})
    $deadline=@($script:Bindings.Values | Where-Object {$_.properties.schedule.name -eq 'stop-session'})
    if ($script:Mutations.Count - $beforeCount -ne 11 -or $script:Bindings.ContainsKey('hourly') -or
        $hourly.Count -ne 1 -or $hourly[0].properties.parameters.Reconcile -ne 'True' -or
        $deadline[0].properties.parameters.IfExpired -ne 'True') {
        throw 'Unsafe hourly binding was not replaced and verified without changing a deadline.'
    }
    Reset-TestBindings
    $script:CorruptOnPublish=$true
    & $block -Stage Publish -RunbooksOnly
    $deadline=@($script:Bindings.Values | Where-Object {$_.properties.schedule.name -eq 'stop-session'})
    if ($deadline.Count -ne 1 -or $deadline[0].properties.parameters.SessionId -ne 'recorded-session' -or
        $deadline[0].properties.parameters.IfExpired -ne 'True' -or $deadline[0].properties.runOn -ne 'test-worker') {
        throw 'Publication did not restore all persisted deadline/worker inputs.'
    }
    Reset-TestBindings -Unsafe
    $script:IgnoreNewArguments=$true
    $caught=$false
    try { & $block -Stage Publish -RunbooksOnly } catch {
        if ($_.Exception.Message -notmatch 'did not retain its requested arguments') { throw }
        $caught=$true
    }
    $script:IgnoreNewArguments=$false
    if (-not $caught) { throw 'Publisher reported success after a binding lost its arguments.' }
    Reset-TestBindings
    foreach ($guard in @('discovery','ownership','runtime','state','edited')) {
        $saved=$script:Books['Extend-GiandoriaLab']|ConvertTo-Json -Depth 12
        switch ($guard) {
            'discovery' { $script:ExtendDiscoveryStatus=403 }
            'ownership' { $script:Books['Extend-GiandoriaLab'].tags.project='other' }
            'runtime' { $script:Books['Extend-GiandoriaLab'].properties.runtimeEnvironment='other' }
            'state' { $script:Books['Extend-GiandoriaLab'].properties.state='Draft' }
            'edited' {
                $script:Books['Extend-GiandoriaLab'].properties.state='Edit'
                $script:DraftContents['Extend-GiandoriaLab']=$script:Contents['Extend-GiandoriaLab']+"`n# Pending operator change"
            }
        }
        $offset=$script:Mutations.Count
        $caught=$false
        try { & $block -Stage Publish -RunbooksOnly } catch {
            if ($_.Exception.Message -notmatch 'HTTP 403|unowned resource|existing Published Extend-GiandoriaLab|unpublished draft') { throw }
            $caught=$true
        }
        finally {
            $script:ExtendDiscoveryStatus=0
            $script:Books['Extend-GiandoriaLab']=$saved|ConvertFrom-Json -AsHashtable
            $script:DraftContents.Remove('Extend-GiandoriaLab')
        }
        $extendWrites=@($script:Mutations | Select-Object -Skip $offset | Where-Object {$_ -like '*/runbooks/Extend-GiandoriaLab*'})
        if (-not $caught -or $extendWrites.Count) { throw "Extend $guard guard permitted publication/adoption." }
    }
    $count=$script:Mutations.Count
    $caught=$false
    try { & $block -Stage Deploy -RunbooksOnly } catch { $caught=$true }
    if (-not $caught -or $script:Mutations.Count -ne $count) { throw 'RunbooksOnly permitted infrastructure deployment.' }

    $cliPath=Join-Path $root 'ops\Invoke-LabControl.ps1'
    $ast=[Management.Automation.Language.Parser]::ParseFile($cliPath,[ref]$null,[ref]$null)
    $help=$ast.GetHelpContent()
    foreach ($parameter in $ast.ParamBlock.Parameters) {
        if (-not $help.Parameters.ContainsKey($parameter.Name.VariablePath.UserPath.ToUpperInvariant())) {
            throw "Local control help is missing $($parameter.Name)."
        }
    }
    $script:StatusJson=@{
        id='offline-session';state='Running';desired='Running';mode='Continuous';speed=730
        expiresAt=[datetimeoffset]::UtcNow.AddHours(3).ToString('o')
    }|ConvertTo-Json -Compress
    function Invoke-RecordedWebRequest {
        param($Uri,$Headers,[switch]$SkipHttpErrorCheck)
        if ($Uri -ne 'https://stgiandoriatest.blob.core.windows.net/lab-state/active-session.json') {
            throw 'Status attempted a request outside its read-only control record.'
        }
        return @{StatusCode=200;Content=$script:StatusJson}
    }
    $cli=(Get-Content -Raw $cliPath).Replace('. "$PSScriptRoot\..\infra\demo\common.ps1"','')
    $cliBlock=[scriptblock]::Create($cli)
    & {
        function Start-Sleep { param($Seconds) }
        function Invoke-DemoArm {
            param($Method,$Path)
            if ($Path -like '*/streams?*') { return @{value=@()} }
            if ($Path -like '*/jobs/*') { return @{properties=@{status='Completed'}} }
            return @{tags=@{project='giandoria';env='demo'}}
        }
        function Invoke-RecordedWebRequest {
            param($Method,$Uri,$Headers,$Body,$ContentType)
            if ($Method -ne 'PUT' -or $Uri -notlike 'https://management.azure.com/*/jobs/*') {
                throw 'Extend CLI submitted an unexpected request.'
            }
            $request=$Body|ConvertFrom-Json
            $names=@($request.properties.parameters.PSObject.Properties.Name | Sort-Object)
            if ($request.properties.runbook.name -ne 'Extend-GiandoriaLab' -or
                $request.properties.parameters.ExtensionMinutes -ne '60' -or
                ($names -join ',') -ne 'ControlJobId,ExtensionMinutes,SessionId') {
                throw 'Extend CLI did not route only applicable parameters to the dedicated runbook.'
            }
            $script:CLIExtendSubmitted=$true
            return @{}
        }
        $script:CLIExtendSubmitted=$false
        & $cliBlock -Action Extend -SessionId ([guid]::NewGuid()) -ExtensionMinutes 60 6>$null | Out-Null
        if (-not $script:CLIExtendSubmitted) { throw 'Extend CLI did not submit its dedicated runbook.' }
    }
    $output=@(& $cliBlock -Action Status 6>&1)
    if ($output[-1] -cne $script:StatusJson -or
        ($output -join "`n") -notmatch 'Speed=730 simulated seconds per REAL second' -or
        ($output -join "`n") -notmatch 'Automatic shutdown UTC:') {
        throw 'Status did not preserve raw JSON and explain speed/deadline on its host stream.'
    }
    $caught=$false
    try { & $cliBlock -Action Start -Force } catch {
        $caught=$true
        if ($_.Exception.Message -notmatch 'Force applies only to Stop/Reconcile') { throw }
    }
    if (-not $caught -or $script:Mutations.Count -ne $count) { throw 'Inapplicable Force was not rejected without mutations.' }
}
finally { [IO.Directory]::Delete($script:DemoLocal) }
Write-Host 'Parameter help/order, Status, publication isolation and paginated binding preservation/repair passed.'
