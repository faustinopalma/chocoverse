#Requires -Version 7.4
[CmdletBinding()]
param([ValidateSet('Validate', 'Run')][string]$Mode = 'Validate')

. "$PSScriptRoot\common.ps1"
Initialize-DemoContext
$python = Join-Path $script:RepoRoot '.venv\Scripts\python.exe'
$workspace = Get-Content -LiteralPath (Join-Path $script:DemoLocal 'demo-workspace.json') -Raw |
    ConvertFrom-Json -DateKind String
if ($workspace.displayName -ne 'ws-giandoria-demo') { throw 'Unexpected recorded Fabric workspace.' }
$capacities = @(Invoke-AzJson -Arguments @('resource', 'list', '--resource-group', 'rg-giandoria-fabric-demo',
    '--resource-type', 'Microsoft.Fabric/capacities'))
if ($capacities.Count -ne 1) { throw 'Expected one existing demo capacity.' }
Assert-DemoOwnership $capacities[0]
$capacityId = $capacities[0].id
$capacity = Invoke-DemoArm -Method GET -Path "${capacityId}?api-version=2023-11-01"
if ($capacity.sku.name -ne 'F4' -or
    $capacity.location.ToLowerInvariant().Replace(' ', '') -ne 'swedencentral' -or
    $capacity.properties.state -ne 'Paused') {
    throw 'Experiment requires the existing Sweden Central F4 to start Paused.'
}
$fabricToken = Invoke-AzJson -Arguments @('account', 'get-access-token', '--resource', 'https://api.fabric.microsoft.com')
$fabricHeaders = @{ Authorization = "Bearer $($fabricToken.accessToken)" }
$workspaceUri = "https://api.fabric.microsoft.com/v1/workspaces/$($workspace.id)"
$liveWorkspace = (Invoke-RecordedWebRequest -Uri $workspaceUri -Headers $fabricHeaders).Content |
    ConvertFrom-Json -DateKind String
$capacityList = (Invoke-RecordedWebRequest -Uri 'https://api.fabric.microsoft.com/v1/capacities' `
    -Headers $fabricHeaders).Content | ConvertFrom-Json -DateKind String
if (Get-Value $capacityList 'continuationToken') { throw 'Paginated capacity discovery needs explicit handling.' }
$matching = @($capacityList.value | Where-Object { $_.displayName -eq $capacity.name -and $_.sku -eq 'F4' })
if ($matching.Count -ne 1 -or $liveWorkspace.capacityId -ne $matching[0].id -or
    $liveWorkspace.displayName -ne 'ws-giandoria-demo') {
    throw 'Recorded workspace is not assigned to the expected F4.'
}

$eventFile = Join-Path $script:DemoLocal 'foundation-events.jsonl'
$lines = @(Get-Content -LiteralPath $eventFile | Where-Object { $_.Trim() })
if ($lines.Count -lt 1 -or $lines.Count -gt 64) { throw 'Experiment requires 1-64 retained synthetic events.' }
$events = @($lines | ForEach-Object { $_ | ConvertFrom-Json -DateKind String })
$runIds = @($events.runid | Sort-Object -Unique)
if ($runIds.Count -ne 1 -or $runIds[0] -notmatch '^[a-zA-Z0-9_-]{1,64}$') { throw 'Invalid experiment run identity.' }
foreach ($event in $events) {
    $null = [guid]::Parse($event.id)
    if ($event.type -notmatch '^lab\.[a-z.]+$' -or $event.seq -lt 1) { throw 'Only lab events are allowed.' }
    $null = [DateTimeOffset]::Parse($event.time)
    $null = [DateTimeOffset]::Parse($event.walltime)
}
if (@($events.id | Sort-Object -Unique).Count -ne $events.Count) { throw 'Input event IDs are not unique.' }
Invoke-RecordedNative -FilePath $python -Arguments @('-c',
    'import importlib.metadata; assert importlib.metadata.version("fabric-cicd") == "1.4.0"') -TimeoutSeconds 30
Write-Host "Validated: existing F4/workspace, pinned publisher and $($events.Count) synthetic events."
if ($Mode -eq 'Validate') { return }

$started = [DateTimeOffset]::UtcNow
$deadline = $started.AddMinutes(15)
$report = [ordered]@{
    StartedAt = $started.ToString('o'); InputEvents = $events.Count; RunId = $runIds[0]
    MaxWallMinutes = 15; CapacityState = 'Unknown'; Status = 'Running'
    Path = 'fabric-cicd definitions + direct Kusto ingest/query; not Eventstream latency validation'
}

function Assert-ExperimentDeadline {
    if ([DateTimeOffset]::UtcNow -ge $deadline) { throw 'Experiment exceeded its 15-minute deadline.' }
}

function Invoke-ExperimentKusto {
    param([Parameter(Mandatory)][string]$Query, [switch]$Management)
    Assert-ExperimentDeadline
    $route = if ($Management) { 'mgmt' } else { 'query' }
    $body = @{ db = $script:ExperimentDatabase; csl = $Query } | ConvertTo-Json -Compress
    $response = Invoke-RecordedWebRequest -Method POST -Uri "$script:ExperimentKusto/v1/rest/$route" `
        -Headers $script:ExperimentKustoHeaders -Body $body -ContentType 'application/json' -TimeoutSec 60
    $result = $response.Content | ConvertFrom-Json -DateKind String
    if ((Get-Value $result 'error') -or (Get-Value $result 'Exceptions') -or
        -not (Get-Value $result 'Tables')) {
        throw 'Kusto returned an error, exceptions or no table result.'
    }
    foreach ($table in $result.Tables) {
        if ($table.TableName -ne 'QueryStatus') { continue }
        $severityColumn = [array]::IndexOf(@($table.Columns.ColumnName), 'Severity')
        if ($severityColumn -lt 0) { throw 'QueryStatus has no Severity column.' }
        foreach ($row in $table.Rows) {
            if ([int]$row[$severityColumn] -le 2) { throw 'Kusto reported partial query failure.' }
        }
    }
    return $result.Tables[0]
}

try {
    Invoke-DemoArm -Method POST -Path "${capacityId}/resume?api-version=2023-11-01" | Out-Null
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Assert-ExperimentDeadline
        $current = Invoke-DemoArm -Method GET -Path "${capacityId}?api-version=2023-11-01"
        if ($current.properties.state -eq 'Active') { break }
        Start-Sleep -Seconds 10
    }
    if ($current.properties.state -ne 'Active') { throw 'F4 resume was not confirmed within five minutes.' }
    $report.ActiveAt = [DateTimeOffset]::UtcNow.ToString('o')
    $env:GIANDORIA_FABRIC_TOKEN = $fabricToken.accessToken
    $env:GIANDORIA_FABRIC_TOKEN_EXPIRES = [string]$fabricToken.expires_on
    try {
        Invoke-RecordedNative -FilePath $python -Arguments @('-m', 'giandoria.fabric_deploy') -TimeoutSeconds 330
    }
    finally {
        Remove-Item Env:GIANDORIA_FABRIC_TOKEN, Env:GIANDORIA_FABRIC_TOKEN_EXPIRES -ErrorAction SilentlyContinue
    }
    Assert-ExperimentDeadline
    $registry = Get-Content -LiteralPath (Join-Path $script:DemoLocal 'demo-fabric-items.json') -Raw | ConvertFrom-Json
    $database = (Invoke-RecordedWebRequest -Uri "$workspaceUri/kqlDatabases/$($registry.items.kqldb_giandoria)" `
        -Headers $fabricHeaders).Content | ConvertFrom-Json -DateKind String
    $eventhouse = (Invoke-RecordedWebRequest -Uri "$workspaceUri/eventhouses/$($registry.items.eh_giandoria)" `
        -Headers $fabricHeaders).Content | ConvertFrom-Json -DateKind String
    if ($database.properties.parentEventhouseItemId -ne $eventhouse.id -or
        $database.properties.databaseType -ne 'ReadWrite' -or
        (Get-Value $eventhouse 'properties.minimumConsumptionUnits') -gt 0) {
        throw 'Fabric item parent/type or minimum-consumption settings differ from the plan.'
    }
    $script:ExperimentKusto = $database.properties.queryServiceUri.TrimEnd('/')
    $queryUri = [uri]$script:ExperimentKusto
    if ($queryUri.Scheme -ne 'https' -or $queryUri.Host -notmatch '^[a-z0-9.-]+\.kusto\.fabric\.microsoft\.com$') {
        throw 'Unexpected Kusto query endpoint; refusing to send credentials.'
    }
    $script:ExperimentDatabase = $database.id
    $kustoToken = Invoke-AzJson -Arguments @('account', 'get-access-token', '--resource', 'https://api.kusto.windows.net')
    $script:ExperimentKustoHeaders = @{ Authorization = "Bearer $($kustoToken.accessToken)" }
    $runFilter = "bronze_lab | where run_id == '$($runIds[0])' and isnotempty(raw_event)"
    $before = Invoke-ExperimentKusto -Query "$runFilter | count"
    $beforeCount = [long]$before.Rows[0][0]
    $sourceById = @{}
    $rows = @(
        for ($i = 0; $i -lt $events.Count; $i++) {
            $event = $events[$i]
            $json = $lines[$i]
            $sourceById[$event.id] = $json
            $rawLiteral = ConvertTo-Json -InputObject $json -Compress
            "'$($event.id)', '$($event.runid)', $($event.seq), datetime($($event.time)), " +
                "datetime($($event.walltime)), '$($event.type)', dynamic($json), $rawLiteral"
        }
    )
    $ingestion = '.set-or-append bronze_lab <| datatable(event_id:string, run_id:string, seq:long, ' +
        "sim_ts:datetime, wall_ts:datetime, event_type:string, payload:dynamic, raw_event:string) [`n" +
        ($rows -join ",`n") + "`n]"
    [IO.File]::WriteAllText((Join-Path $script:DemoLocal 'fabric-experiment-ingest.kql'), $ingestion,
        [Text.UTF8Encoding]::new($false))
    $ingestStarted = [Diagnostics.Stopwatch]::StartNew()
    Invoke-ExperimentKusto -Query $ingestion -Management | Out-Null
    Invoke-ExperimentKusto -Query $ingestion -Management | Out-Null
    $actual = Invoke-ExperimentKusto -Query (
        "$runFilter | summarize copies=count(), payloads=make_set(raw_event, 2) by event_id, seq, sim_ts, event_type " +
        '| project event_id, seq, sim_ts, event_type, copies, payloads | order by seq asc'
    )
    Write-JsonFile -InputObject $actual -Path (Join-Path $script:DemoLocal 'fabric-experiment-query-result.json')
    if ($actual.Rows.Count -ne $events.Count) { throw 'Unique-event count differs from the retained input.' }
    $rawCount = 0L
    $index = @{}
    foreach ($event in $events) { $index[$event.id] = $event }
    foreach ($row in $actual.Rows) {
        $expected = $index[[string]$row[0]]
        $payloads = if ($row[5] -is [string]) { $row[5] | ConvertFrom-Json -DateKind String } else { $row[5] }
        if (-not $expected -or $row[1] -ne $expected.seq -or
            [DateTimeOffset]::Parse([string]$row[2]) -ne [DateTimeOffset]::Parse($expected.time) -or
            $row[3] -ne $expected.type -or $row[4] -lt 2 -or @($payloads).Count -ne 1) {
            throw 'Event identity, sequence, sim time, type or replay payload differs from the input.'
        }
        $raw = @($payloads)[0]
        if ($raw -cne $sourceById[[string]$row[0]]) { throw 'Raw CloudEvent text differs from the retained JSONL.' }
        $stored = $raw | ConvertFrom-Json -DateKind String
        foreach ($field in @('id', 'runid', 'seq', 'time', 'walltime', 'type', 'source', 'specversion')) {
            if ($stored.$field -cne $expected.$field) { throw "Stored CloudEvent field differs: $field" }
        }
        $rawCount += [long]$row[4]
    }
    if ($rawCount -ne $beforeCount + 2 * $events.Count) { throw 'Raw replay row count differs from exactly two batches.' }
    $report.BeforeRawRows = $beforeCount
    $report.AfterRawRows = $rawCount
    $report.UniqueEvents = $actual.Rows.Count
    $totals = Invoke-ExperimentKusto -Query (
        "bronze_lab | where run_id == '$($runIds[0])' | summarize total=count(), withRaw=countif(isnotempty(raw_event))"
    )
    $report.TotalRetainedRows = [long]$totals.Rows[0][0]
    $report.LegacyRowsWithoutRawText = $report.TotalRetainedRows - [long]$totals.Rows[0][1]
    $report.IngestAndQuerySeconds = [math]::Round($ingestStarted.Elapsed.TotalSeconds, 3)
    $report.Status = 'Succeeded'
    Write-Host "Verified $rawCount raw rows, $($actual.Rows.Count) unique CloudEvents, exact identity/sim time and replay."
}
catch {
    $report.Status = 'Failed'
    $report.Error = Protect-CommandText $_.Exception.Message
    throw
}
finally {
    try {
        $current = Invoke-DemoArm -Method GET -Path "${capacityId}?api-version=2023-11-01"
        if ($current.properties.state -ne 'Paused') {
            Invoke-DemoArm -Method POST -Path "${capacityId}/suspend?api-version=2023-11-01" | Out-Null
        }
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            $current = Invoke-DemoArm -Method GET -Path "${capacityId}?api-version=2023-11-01"
            if ($current.properties.state -eq 'Paused') { break }
            Start-Sleep -Seconds 10
        }
        $report.CapacityState = $current.properties.state
        if ($current.properties.state -ne 'Paused') { throw 'F4 suspension not confirmed. Immediate action required.' }
        Write-Host 'F4: Paused. Retained items/data were not deleted.'
    }
    finally {
        $report.CompletedAt = [DateTimeOffset]::UtcNow.ToString('o')
        Write-JsonFile -InputObject $report -Path (
            Join-Path $script:DemoLocal ("fabric-experiment-$($started.ToString('yyyyMMdd-HHmmss')).json")
        )
    }
}
