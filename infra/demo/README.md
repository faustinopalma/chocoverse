# Giandoria demo infrastructure

Single synthetic-data PoC in Sweden Central, deployed with Bicep/AVM and PowerShell 7.4+.
This is the operational runbook. See [chapter 19](../../docs/19-policy-exemption-experiment.md) for the network
waiver register and [chapter 20](../../docs/20-fabric-walking-skeleton.md) for verified Fabric behavior and limits.

## Scope

Three project resource groups, two LRS Storage accounts, runtime/control identities, ACR Basic,
Consumption-only Container Apps environment, capped project Log Analytics and keyless Application Insights.
The Fabric stage creates one F4 and a workspace; the experiment publishes the Eventhouse/KQL definitions.
Azure Automation provides cloud Start/Stop with a scheduled deadline. The causal business runtime and its
deployment assets are verified end-to-end through a two-calendar-year collection with real model decisions.
The shared Foundry service and model configuration are not modified; its registered network Waiver is separate.

Infrastructure uses incremental ARM deployments: no automatic deletion, stack teardown or data reset.
This is not the full target bootstrap or production lifecycle.
Resources retain data, and ACR/Storage/Defender can incur idle charges.

## Prerequisites

- Azure CLI and Bicep; the configured `.env` context must match the active CLI account.
- The signed-in operator can read their Entra profile, deploy resources and grant scoped data roles.
- Exemptions require `policyExemptions/write` at resource scope and `policyAssignments/exempt/action` on the
  inherited assignment [F97]; Owner only on a child subscription does not necessarily suffice.
- Required Azure resource providers registered, Sweden Central service availability and quota checked.
- Fabric permissions are separate from Azure Owner; lack of Fabric authorization must be reported.

## Explicit stages

Run from the repository root after preparation/validation and authorized Azure spending:

```powershell
$record = '.\ops\Invoke-RecordedCommand.ps1'
$deploy = '-NoProfile', '-File', '.\infra\demo\Deploy-Demo.ps1'
& $record -FilePath pwsh -Arguments ($deploy + @('-Stage','Validate'))
& $record -FilePath pwsh -Arguments ($deploy + @('-Stage','Foundation'))
& $record -FilePath pwsh -Arguments ($deploy + @('-Stage','Exemptions'))
& $record -FilePath pwsh -Arguments ($deploy + @('-Stage','Public'))
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Test-DemoPublicAccess.ps1','-WriteProbe')
& $record -FilePath pwsh -Arguments ($deploy + @('-Stage','Fabric'))
```

`Foundation` creates Storage network-disabled. It refuses to disable an already-public account on rerun;
use `Public` for subsequent foundation updates. Existing resources require exact project/environment tags.
`Exemptions` is an explicit administrative step, not normal reconciliation. It creates a missing waiver only
while the account is network-disabled; it does not widen, renew or overwrite an existing exception.
The waiver has no expiry and affects one networking member on each account only.
`Public` fails if the required waiver is missing or differs. It does not recreate it.
All stages stop on errors; inspect/report partially provisioned resources rather than silently skipping them.

The additional network-audit Waivers and rationale updates are a separate administrative operation:

```powershell
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Deploy-NetworkExemptions.ps1',
    '-Stage','Validate')
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Deploy-NetworkExemptions.ps1',
    '-Stage','Deploy')
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Test-DemoPublicAccess.ps1')
```

This operation includes the approved shared experimental Foundry scope; review its consumers before execution.
Only the exact network members in chapter 19 are exempted. A previously recorded waiver is not recreated.
Policy reevaluation is asynchronous: reduce all states to the newest per resource/assignment/member before
filtering noncompliance. Exemption readback alone is not a completed compliance evaluation.

The Fabric stage and experiment activate paid compute and suspend F4 in `finally`, verifying `Paused` even on failure.
This is not an independent watchdog against operator-machine failure. Neither is a general runtime resume command.
Workspace/item identities are recorded locally; unrecorded same-name resources are never silently adopted.

## Lab Start/Stop

The Automation Account uses the `GiandoriaPowerShell` runtime environment: PowerShell 7.4, Az 12.3.0.
`runbookType=PowerShell` is the language/type field, not a declaration of PowerShell 5.1.
Publication verifies the runtime binding, published source and each schedule's persisted arguments;
job output records the actual runtime version.
Runbook metadata, including descriptions, is also declared in Bicep. Both IaC and the publisher derive the text
from the scripts' help synopsis; content bundling/publication remains the publisher's responsibility.
Azure limits this description to 512 characters; the publisher and tests enforce it. Full parameter help and
examples remain in the source and `Get-Help`, not the native portal input tooltip.

```powershell
.\infra\demo\Deploy-Automation.ps1 -Stage Validate
.\infra\demo\Deploy-Automation.ps1 -Stage Deploy
.\ops\Invoke-LabControl.ps1 -Action Start -MaxWallMinutes 240 -Speed 8760
.\ops\Invoke-LabControl.ps1 -Action Status
.\ops\Invoke-LabControl.ps1 -Action Extend -SessionId '<recorded-session-guid>' -ExtensionMinutes 240
.\ops\Invoke-LabControl.ps1 -Action Stop -SessionId '<recorded-session-guid>'
```

For ordinary portal use, open `aa-giandoria-demo`, select Runbooks, then `Start-GiandoriaLab` and Start.
Leave the technical IDs empty. Defaults are `Mode=Continuous`, `Speed=8760` and `MaxWallMinutes=240` (four hours).
To stop, start `Stop-GiandoriaLab`; empty `SessionId` resolves the current recorded session.
To add time, start `Extend-GiandoriaLab` and change only `ExtensionMinutes` (240 adds four hours).
Scripts retain an explicit session ID so a stale Stop or Extend cannot inadvertently select a newer session.
No runtime installation or manual ingestion step is required at each activation.

### Parameter guide: real duration versus simulated speed

The Azure Automation form uses free-text fields. It does **not** turn PowerShell `ValidateSet` choices into
dropdowns or display comment-based parameter help. Enter the values below without quotes; do not type the
displayed expression `[guid]::Empty`. Leave technical IDs empty. Optional means a default exists, not that every
field applies to every operation. In the runbook menu, **Runbook settings > Description** contains a compact reminder.
For full source help locally: `Get-Help .\ops\automation\Start-GiandoriaLab.ps1 -Full`.

For the usual actions, change only these fields:

| Goal | Runbook | Values to set |
|---|---|---|
| Watch the company for four real hours | `Start-GiandoriaLab` | Defaults: `Mode=Continuous`, `MaxWallMinutes=240`, `Speed=8760` |
| Slower three-hour demonstration | `Start-GiandoriaLab` | `MaxWallMinutes=180`, `Speed=730` |
| Add four real hours | `Extend-GiandoriaLab` | `ExtensionMinutes=240`; leave both technical IDs empty |
| Query history without generating data | `Start-GiandoriaLab` | `Mode=Analysis`, `MaxWallMinutes=240` |
| Stop now, preserving history | `Stop-GiandoriaLab` | Leave all fields at their defaults |

Starting a runbook creates an Automation **job**. A Completed Start/Extend job means the control operation
completed, not that the laboratory has stopped. Use the job's **Output** for settings and UTC shutdown time;
All logs also includes verbose technical HTTP records. Queueing, capacity activation and worker startup take time.
Cancelling an Automation job is not the lab Stop procedure; use `Stop-GiandoriaLab`.
Submitting Start while the lab is active fails without changing it; it does not extend.
During an existing Start/Extend/Stop, wait for its output rather than submitting competing jobs.

#### Start-GiandoriaLab

| Parameter | Values / default | Meaning and when to use |
|---|---|---|
| `MaxWallMinutes` | Integer 10-1440; default 240 | Start only: REAL minutes until automatic shutdown, including startup. 180 = 3 hours, 240 = 4 hours |
| `Mode` | `Continuous` (default), `Analysis`, `Batch` | Start only: live company, queries only, or advanced finite collection |
| `Speed` | Integer 1-8760; default 8760 | Start/Continuous: simulated seconds per REAL second; see examples below. Not the session length |
| `SessionId` | GUID; leave empty in portal | Technical: Start generates an ID; Extend selects the current session. Scripts should specify the recorded ID |
| `ControlJobId` | GUID; leave empty in portal | Internal controller-ownership tracking; Automation supplies its own job ID |
| `Operation` | `Start` (default), `Extend` | Legacy compatibility only; leave Start. For ordinary extensions choose `Extend-GiandoriaLab` |
| `ExtensionMinutes` | Integer 10-1440; default 240 | Legacy compatibility only; ignored by Start. Leave its default |

#### Extend-GiandoriaLab

| Parameter | Values / default | Meaning and when to use |
|---|---|---|
| `ExtensionMinutes` | Integer 10-1440; default 240 | REAL minutes to ADD to the previous shutdown deadline, not to now; 60 = +1 hour, 240 = +4 hours |
| `SessionId` | GUID; leave empty in portal | Selects the current running session; scripts should specify its recorded ID to reject stale commands |
| `ControlJobId` | GUID; leave empty in portal | Internal controller-ownership tracking |

Extend keeps the current mode, speed, session and company history; at most 24 real hours may remain afterwards.
It accepts running Continuous/Analysis sessions only, not stopped/expired sessions or finite Batch collection.
Fabric remains active while the Continuous worker checkpoints and restarts briefly.
The local CLI routes `-Action Extend` to this dedicated runbook. Old callers of Start with `Operation=Extend`
remain supported through the same shared extension function; their irrelevant Start settings are ignored with a warning.
For example, Start at 15:00 for 180 minutes expires at 18:00. Extend at 15:05 by 240 minutes expires at 22:00:
seven hours from the original start, with six hours and 55 minutes remaining at extension time.

#### Stop-GiandoriaLab

| Parameter | Values / default | Meaning and when to use |
|---|---|---|
| `Force` | `False` (default), `True` | Leave False for normal checkpoint/graceful shutdown. True skips graceful waiting for recovery; still verifies shutdown |
| `SessionId` | GUID; leave empty in portal | Selects the current session; scripts should pass the recorded ID to avoid stopping a newer one |
| `ControlJobId` | GUID; leave empty in portal | Internal controller tracking |
| `IfExpired` | `False` (default), `True` | Internal scheduled-stop guard. True deliberately leaves a not-yet-expired session running |
| `Reconcile` | `False` (default), `True` | Internal hourly safety check. True does not stop a healthy session within its deadline |

Do not set `IfExpired=True` or `Reconcile=True` when you want an ordinary manual Stop.
Force is not deletion or a data reset. Check the final Output for confirmed Paused F4; a settling controller
may require the existing reconciliation to finish shutdown.

### Choosing Speed

`Continuous` resumes the saved company and appends new events beyond the original two-year reference.
Speed is a time multiplier: `Speed=730` means one real second represents 730 simulated seconds.
It is independent of the real session duration: `MaxWallMinutes=180` always requests three real hours.
Set speed at Start, not by editing scenario files or submitting Extend.

| Speed | Target simulated time per REAL hour | Target time between hourly simulation ticks |
|---|---|---|
| 8760 | 365 days (one year); one simulated day about every 9.9 real seconds | 0.41 real seconds |
| 730 | About 30.4 days (one month); one simulated day about every two real minutes | 4.93 real seconds |
| 60 | 2.5 days | One real minute |
| 24 | One day | 2.5 real minutes |
| 1 | One hour (unaccelerated) | One real hour |

The clock advances in **hourly simulated ticks**, not second by second. Between ticks it still emits observations
approximately every five real seconds, so slow speed need not look disconnected.
IO, model calls and checkpointing can reduce achieved speed; these are targets, not throughput guarantees.
Paused time is not replayed at the next Start. Analysis generates no company events and ignores Speed; Batch is
not paced by Speed. Neither stopping nor changing presentation speed deletes previous history.

Use `Mode=Analysis` to activate Fabric without generating business events, or `Mode=Batch` for the finite collector.
Stop preserves checkpoints, event history and all strategic decisions. A new Start continues the same company;
it is not a new scenario or a reset. Start accepts 10-1,440 real minutes, with a four-hour default.

To prolong a running session in the portal, start `Extend-GiandoriaLab` with
`ExtensionMinutes=240` (or another value from 10 to 1,440). Leave `SessionId` empty to select the current session.
The extra minutes are added to its existing deadline, not measured from the time the request is submitted.
Prorogations are repeatable, provided the resulting remaining duration does not exceed 24 hours.
Stop remains immediate on demand; a stopped or expired session cannot be revived by Extend.

The new shutdown schedule is armed before the changed deadline is committed. Earlier scheduled stops recheck
the current deadline atomically, so they cannot stop a successfully extended session.
In Continuous mode, Extend asks the worker to checkpoint and exit, waits for terminal execution, then starts
a replacement. Fabric stays active and company time, event history, speed, session ID and decision budgets are
preserved. A brief generation pause is expected during worker startup; a fresh budget is not granted by extension.
Analysis mode extends without creating a worker. Batch collection does not support extension.
If renewal fails after committing the deadline, the controller shuts down safely instead of reporting success.
Sessions started by older runbook versions must be stopped and started once before extension is available.

Run operational commands through the recorded wrapper shown above. Start returns when activation is complete,
not when the experiment is finished. It deliberately leaves the lab running under its verified one-time shutdown
schedule. Stop is session-scoped and preserves data. `-Force` skips graceful waiting, not state verification.
Hourly reconciliation reuses Stop; the three operator runbooks are Start, Extend and Stop.
Scheduling is not an exact-second guarantee.
Automation queue/worker startup and graceful shutdown are not instantaneous. The requested deadline is independent
of an operator terminal. Automation stores schedule times at whole-minute precision: the one-time trigger is rounded
up to the first UTC minute at or after expiry and read back before activation. This avoids an early, expiry-guarded
invocation doing nothing and deferring shutdown until hourly reconciliation.
The runtime also checks session ownership/deadline and has a separate hard Job timeout.

For an isolated cloud-only deadline test, run `tests\Test-AutomationDeadline.ps1`. It activates paid F4 for a
bounded ten-minute session, schedules an early reconciliation probe and verifies that it leaves the unexpired
session running. The test rejects early shutdown, then verifies automatic shutdown without an operator Stop request.
Its temporary probe schedule/binding are removed afterwards. Do not run it casually or against an operator-owned session.

The [business fidelity summary](../../docs/21-business-lab.md) explains module boundaries, strategic decisions,
retained checkpoints and limits. It does not replace the full target architecture.

## Watching live and historical data

Open the existing `ws-giandoria-demo` workspace while the lab is active:

- `rt_giandoria`: Overview, Sales, Operations, Finance and Diagnostics pages, refreshed every ten seconds.
- `qs_giandoria`: the same fifteen editable queries for company trends and separate technical diagnostics.
- `kqldb_giandoria`: query `bronze_business` directly for deeper analysis.

For a live observation session, start with `rt_giandoria`, then inspect Diagnostics for recent real arrivals
and a changing virtual tick. Capacity Active or a saved session marked Running is not sufficient evidence
that the worker is producing data. Check the actual job execution and compare two company observations.
The Power BI thin reports and `da_giandoria` use the fixed snapshot described below: their numbers should
agree with each other at the published cutoff, not with the current live company totals.
Ask the agent for its cutoff and whether the data is live before comparing results.

Use the dashboard's Pages control to switch between views. In the query set, select a tab and choose Run.
Open both items from the workspace list rather than constructing a URL from their REST item type names.

Business pages use only simulation time (`sim_ts`, Europe/Rome `simlocaldate`).
Recent windows cover the 90 complete virtual days before the latest observed virtual date; the current incomplete
day/month is excluded from flow charts. Full daily and monthly history stays continuous across stops and speed changes.
Stock and finance balances are the last available observation per day, not exact closing balances or sums of snapshots.
Revenue, purchases and conversion are shown separately, not presented as a complete P&L.
The Diagnostics page alone includes real arrival time (`wall_ts`) and last-update age:
retained values when stopped are not current liveness.
Manager decisions show rule fallback explicitly if the model is unavailable or a request/token guard is reached.
Ingestion and query latency add to the approximately five-second observation cadence; this is near-real-time,
not a contractual latency guarantee. All dashboard/query-set definitions and fifteen queries are source-owned.

For historical inspection without advancing the company:

```powershell
.\ops\Invoke-LabControl.ps1 -Action Start -Mode Analysis -MaxWallMinutes 240
# Inspect Fabric, then Stop using the SessionId returned by Start.
```

Example near-real-time arrivals:

```kusto
bronze_business
| where run_id == "business-demo-001" and wall_ts > ago(15m)
| summarize take_any(*) by event_id
| summarize events=count() by bin(wall_ts, 10s)
| order by wall_ts asc
```

Deduplicate by `event_id` before sums. Do not use `ago()` on future simulation timestamps.
The full-history examples are in [fabric/queries](../../fabric/queries); add `sequence <= 285349` to reproduce
only the original two-year enterprise reference.

Data survives Stop:

| Location | Retained content |
|---|---|
| Eventhouse `bronze_business` | Queryable enterprise events and exact raw JSON; interactive queries require active F4 |
| State Storage `outbox/business-demo-001/<first>-<last>.json` | Archived exact event batches, including separate truth |
| State Storage `snapshots/business-demo-001/current.json` | Current restart checkpoint |
| State Storage `decisions/business-demo-001/ledger.json` | Lifetime strategic decisions and durable session budgets |
| State Storage `lab-state/business-summary.json` | Latest company summary |
| State Storage `snapshots`/`decisions`, `business-demo-001/reference-two-years.json` | Retained reference checkpoint/ledger |

Storage access uses Entra authentication; inspect or download blobs with the portal or authenticated Storage tools.
Do not edit current checkpoints, ledgers or archives to replay a demonstration.
Public network reachability does not mean anonymous data access.

View publication is an explicit deployment action, not part of every Start:

```powershell
& $record -FilePath .\.venv\Scripts\python.exe -Arguments @('-m','giandoria.lab_views')
```

It uses the recorded workspace/item registry and current guarded CLI context.
Definition readback and live queries are verified separately from browser rendering; an authenticated Fabric
browser session is required to view the UI. The integrated test browser does not inherit CLI authentication.

The [dashboard engineering guide](../../docs/22-dashboard-engineering.md) describes source ownership,
all metrics, definition generation, safe publication, browser checks and regression-test methodology.

### Power BI semantic showcase

With F4 already active and the guarded context initialized as above, publish/update the shared model
and two thin reports:

```powershell
& $record -FilePath .\.venv\Scripts\python.exe -Arguments @('-m','giandoria.showcase')
```

This extracts a new common virtual-date/sequence snapshot, publishes `sm_giandoria_showcase`,
processes its embedded import partitions, reconciles DAX against extracted rows, then publishes
`rp_giandoria_commercial` and `rp_giandoria_operations`. It does not start/stop the lab, resume capacity,
change its SKU or create Azure infrastructure. Use analysis-only Start if capacity needs activation.
Model processing/querying uses the existing F4 and is not cost-free; no new fixed-cost service is added.

To iterate on measures or visuals without moving the cutoff:

```powershell
& $record -FilePath .\.venv\Scripts\python.exe -Arguments @('-m','giandoria.showcase','--reuse-snapshot')
```

The latter requires the saved `.local\showcase-snapshot.json`. Generated model, persisted-definition
readbacks and verification evidence are saved under ignored `.local`; do not edit them as source.
The accepted item registry and ownership marker guard every update.
An ordinary Power BI refresh reprocesses the **same embedded snapshot**; only a new extraction/publication
advances the business cutoff. No scheduled refresh is installed. Open the reports from the recorded
workspace and authenticate separately in the browser. All authored labels are English.

The [semantic showcase guide](../../docs/23-semantic-model-showcase.md) owns model grains, relationships,
DAX construction, visual lessons, validation and the intentional non-production snapshot tradeoff.

### Dynamic Smart narrative and KPI definitions

The two thin reports include native custom Smart narrative summaries above the charts and optional
English KPI definitions below all charts. Republish only the reports without extracting a newer snapshot:

```powershell
& $record -FilePath .\.venv\Scripts\python.exe -Arguments @('-m','giandoria.report_narratives','publish')
```

Prerequisites: the saved and reconciled showcase model/snapshot, operator Fabric access and active F4.
Publication invokes no external language model and requires no commentary receipt or inference role.

`publish` updates and reads back **only the two existing reports**, checking that the persisted semantic model
still matches the saved snapshot. It does not refresh the model, modify the Data Agent or stop the simulation.
Reload an open report after publication. Verify that year selection changes the native trend sentence and
KPI values; on the stock-policy page, also verify the cover-day selector. The KPI guide stays unchanged
at the bottom. This is native custom Smart narrative, not Copilot mode.

A normal showcase republication generates the same native dynamic definitions; no fixed AI prose is reused.
The earlier `generate` / `generate --new-attempt` commands are a separate archived snapshot-commentary
experiment, not a report dependency. Dynamic summary updates do not advance the model's fixed virtual cutoff.
Existing Data Agent snapshot contracts must be reconciled separately when the source snapshot advances.

### Fabric IQ ontology preview

The [ontology guide](../../docs/26-fabric-ontology.md) defines the entity grains, relationships and preview
limits. The tenant setting **Users can create Ontology (preview) items** must be enabled for the publishing
identity; otherwise the API returns `403 FeatureNotAvailable`.
An administrator must approve and enable this feature for the intended author group before publication.
Do not broaden tenant access or change SKU/region as a workaround.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[ontology]'
& $record -FilePath .\.venv\Scripts\python.exe -Arguments @('-m','giandoria.ontology','prepare')
# Only after the tenant prerequisite is enabled and F4 is active:
& $record -FilePath .\.venv\Scripts\python.exe -Arguments @('-m','giandoria.ontology','publish')
```

`prepare` validates the existing enterprise snapshot and entity/relationship keys without cloud writes.
`publish` checks ontology creation before copying data, then creates only the registered `ont_giandoria`
and `lh_giandoria_context` items in the original workspace. It uploads immutable Delta files through
regional OneLake APIs, verifies exact byte readback and table registration, and publishes entity definitions
and data bindings. Exact definition readback is required before writing the verification receipt.
Ownership conflicts, changed source files, orphan keys, missing table registration or service errors abort.
No Spark session, graph materialization, new Azure resource, permission grant or manager integration is added.

### Native Decision Room app

The [Decision Room guide](../../docs/27-decision-room.md) explains the interface, identity boundaries,
virtual-time contract and code-first **app authoring** workflow. It uses the original approved workspace,
existing F4 and published enterprise model/agent/ontology, not the advancing live company or hidden truth.

Run from the repository root after the source publications have verification receipts and F4 is active:

```powershell
.\ops\Invoke-DecisionRoom.ps1 -Action Prepare
.\ops\Invoke-DecisionRoom.ps1 -Action Login
.\ops\Invoke-DecisionRoom.ps1 -Action Query
.\ops\Invoke-DecisionRoom.ps1 -Action Sources
.\ops\Invoke-DecisionRoom.ps1 -Action Preview
# After confirming the existing registered app/workspace:
.\ops\Invoke-DecisionRoom.ps1 -Action Deploy
.\ops\Invoke-DecisionRoom.ps1 -Action Status
```

`Prepare` validates the local publications and generates ignored source coordinates; it does not advance
their cutoff. `Query` uses native Rayfin authentication for the semantic-model resource. `Sources` compares
the real model/agent definitions with their prepared contracts. Management actions obtain a short-lived,
in-memory Fabric token through the guarded Azure CLI context. Tokens are not persisted in project files.
The wrapper records commands, pins the supported Node 22 CLI runtime and uses the approved Edge profile
without changing browser defaults. Preserve the ignored deployment registry to target the same app.

Frontend build, lint, typecheck and tests run from
`apps\giandoria-decision-room`; see its [README](../../apps/giandoria-decision-room/README.md).
`-Action Dev` is the Fabric-backed authoring entry point, not a deployment or a guarantee that the local
Functions host has started. Verify Functions readiness independently before relying on local investigations.
After deployment, perform the hosted checklist in chapter 27, including a real investigation and review
create/reload/update/delete. A successful publish or skipped non-GraphQL generation is not runtime validation.

The wrapper neither starts the lab nor changes its deadline. Use the existing Start/Extend controls when
needed. F4 suspension preserves the app; managed SQL and retained services may still incur idle charges.
Do not broaden permissions, create a trial, or provision another capacity to recover a failed operation.

### Fabric Data Agent showcase

Prerequisites: the reconciled semantic showcase above, its saved snapshot, F4 already active, operator
Fabric/source access and tenant AI prerequisites. This does not activate capacity or change tenant settings,
permissions, the worker identity or the live runtime. Initialize the guarded CLI context in each new shell:

```powershell
. .\infra\demo\common.ps1
Initialize-DemoContext
$record = '.\ops\Invoke-RecordedCommand.ps1'
& $record -FilePath .\.venv\Scripts\python.exe -Arguments @('-m','giandoria.data_agent','deploy')
& $record -FilePath .\.venv\Scripts\python.exe -Arguments @('-m','giandoria.data_agent','ask',
    'What are total Sold kg and Revenue EUR? State the virtual cutoff and whether this is live.')
& $record -FilePath .\.venv\Scripts\python.exe -Arguments @('-m','giandoria.data_agent','evaluate')
```

Publication creates/updates `da_giandoria` from source with matching draft/published definitions and
exactly one enterprise semantic-model source. Open that item from the recorded workspace for the
observer interface; browser sign-in is independent of CLI sign-in. CLI questions use the published MCP
endpoint. These calls use existing paid capacity and AI services; they are not cost-free.
Use `ws-giandoria-demo` for the observer showcase; the same-named agent in `ws-giandoria-agent-demo`
belongs to the isolated application-authentication experiment. Both expose fixed snapshots, not current
Eventhouse data. A semantic-model refresh alone cannot advance embedded source rows.
If the browser editor remains on Loading while CLI questions succeed, do not recreate the item or
change permissions blindly. Open the workspace in a fresh browser tab and follow its Data Agent link;
this recovers a stale integrated-browser workload session without changing the item. If it persists,
check Fabric workload/extension loading and authentication separately. A successful published MCP answer
verifies the query path, not the browser chat interface.

To run one isolated manager decision, choose a safe unique experiment name. The example chooses the
first virtual date after the whole snapshot, not the operator's real date:

```powershell
$agent = Get-Content .\.local\data-agent.json -Raw | ConvertFrom-Json
$cutoff = ([datetime]::ParseExact($agent.contract.throughDate, 'yyyy-MM-dd',
    [cultureinfo]::InvariantCulture)).AddDays(1).ToString('yyyy-MM-dd')
& $record -FilePath .\.venv\Scripts\python.exe -Arguments @('-m','giandoria.data_agent','manager',
    '--experiment','sop-example-01','--cutoff',$cutoff)
```

Every result states `appliedToLab: false`. Evidence, ledger and result live only under
`.local\data-agent-experiments\<name>`. Repeat the exact command to verify replay: no new MCP `tools/call`
or Foundry inference should occur, although source metadata is rechecked. A changed snapshot requires
new publication/provenance and a new experiment name. An interrupted reservation is intentionally not
retried; inspect it before authorizing another billable attempt. Never delete its history to force replay.
For a failed golden question, inspect `.local\data-agent-evaluations`, then explicitly rerun only the
relevant `evaluate --case totals|calendar|scenario|boundaries` case after addressing the cause.
Golden evaluation commands always create a new evaluation; unlike named manager replay, they invoke the agent.

The [Data Agent guide](../../docs/24-data-agent-showcase.md) owns construction, time/source checks,
evaluation, failure handling, local-lock recovery and snapshot limits. These commands do not provision
application access; use the section below for that path. Use normal Stop/deadline handling; this command never suspends
an active user's laboratory.

### Data Agent delegation comparison

This read-only experiment compares an overview-only generalist, the same generalist with a real Data Agent tool,
and a control supplied with the retrieved evidence. See [chapter 28](../../docs/28-data-agent-delegation-experiment.md)
for the frozen questions, observed results and limitations.

Prerequisites: a stopped lab, the existing runtime model deployment, reconciled semantic snapshot and published
Data Agent, and the operator's configured Azure CLI identity. Run from the repository root:

```powershell
.\ops\Invoke-AgentComparison.ps1 -Experiment 'delegation-example-01'
```

For the stronger same-data query comparison, use a new name and select the query protocol:

```powershell
.\ops\Invoke-AgentComparison.ps1 -Experiment 'query-knowledge-example-01' -Protocol query
```

This gives the generalist every table/column, relationship and measure expression/description, plus read-only
access to the full enterprise model. Its generated DAX is executed, not merely displayed.
The same generalist also runs with the exact Data Agent instructions as a knowledge-transfer control;
the real Data Agent answers each question independently.
The four frozen cases cover balances, unsupported dimensional grains, policy multiselection and missing observations.
Query errors and wrong shapes are retained as failures, without automatic repairs.
Only the configured semantic model is queried; no truth workspace or additional permissions enter the experiment.

To isolate access to the curated semantic catalogue, use the ablation protocol:

```powershell
.\ops\Invoke-AgentComparison.ps1 -Experiment 'query-ablation-example-01' -Protocol query-ablation
```

It adds a raw-schema arm with the same tables, columns, relationships and query access but no measure catalogue
in its prompt. The other three arms are unchanged. Four cases produce at most twelve direct DAX executions
and four Data Agent calls; the ordinary query protocol executes eight direct queries and four specialist calls.
These counts do not describe the specialist's undisclosed internal query activity.

The wrapper verifies the existing model version, starts **Analysis** mode with a 45-real-minute shutdown deadline,
runs the comparison and invokes session-scoped Stop in `finally`.
Cleanup independently checks Paused F4 and terminal worker executions; it must not be used to take over another
user's active session. Company data is preserved and no business time advances.

The suite reserves at most sixteen generalist completions with 2,048 output tokens each, four specialist calls,
a 32 KB input envelope per completion and a 30-minute logical run deadline.
The child process is bounded to 1,900 seconds; startup and cleanup have separate limits.
The published snapshot is rechecked before and after the suite. No inference retries are automatic.
Local checkpoint commits retry only transient Windows replacement locks, with a short bounded delay and audit;
this never repeats a model or Data Agent call. Persistent write failures still fail the run.
These are request/time limits, not a monetary ceiling; F4, both inference paths and supporting services cost money.
Retained services, including subscription Defender plans, can cost money after shutdown.

The unique name reserves `.local\agent-comparisons\<name>\result.json` before inference.
It contains the frozen plan/oracle, actual questions and answers, scores, usage and failures.
Reusing a name fails: inspect an incomplete run, then deliberately choose a new name for another billable trial.
Never delete records to hide failed trials, and never publish raw prompts, tenant identities or operational journals.
Offline comparison checks need no cloud session:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_agent_comparison.py -v
```

### Secretless Data Agent application identity

The [authentication guide](../../docs/25-data-agent-authentication.md) owns the token-exchange flow,
authorization boundary and revocation. Prerequisites: the saved/reconciled showcase snapshot, existing active F4,
the runtime user-assigned managed identity, operator permissions to create an application and provision
Fabric access, and existing tenant service-principal eligibility. No script enables a tenant setting.

Run in the guarded CLI context above:

```powershell
& $record -FilePath pwsh -Arguments @('-NoProfile','-File',
    '.\infra\demo\Deploy-DataAgentIdentity.ps1','-Stage','Validate')
& $record -FilePath pwsh -Arguments @('-NoProfile','-File',
    '.\infra\demo\Deploy-DataAgentIdentity.ps1','-Stage','Deploy')
& $record -FilePath .\.venv\Scripts\python.exe -Arguments @('-m','giandoria.data_agent_service')
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Build-Runtime.ps1')
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Test-RuntimeImage.ps1')
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Test-DataAgentIdentity.ps1')
```

The dedicated service principal has no password, certificate, Graph application permissions or Azure role.
Its only federated trust names the existing runtime managed identity. Contributor is granted only in
`ws-giandoria-agent-demo`, on the same F4, with exactly a generated enterprise semantic model and its
Data Agent. Contributor includes write access there; the runtime client's read-only behavior does not
make this a read-only permission. The original truth-containing workspace is never granted to the app.

Identity receipts and the service workspace/item registries remain under ignored `.local`; do not remove
them to force adoption. `.local\data-agent-service.json` contains non-secret identifiers, source contract
and independent probe expectations. The probe uploads that configuration to `lab-state/data-agent-service.json`
and uses one pinned-image execution of the existing job. It checks application identity, original-workspace
denial, exact enterprise items, direct DAX totals and one numerically validated MCP answer. Evidence is stored
under `lab-state/data-agent-auth-check/`. A fabricated or stale answer is an error, even after HTTP success.
The test waits at most eight minutes and stops only its exact probe execution on failure/timeout, never the
running company. It consumes paid compute/capacity; do not run it in an automatic retry loop.

To reconcile existing access without refreshing the snapshot or republishing the agent:

```powershell
& $record -FilePath .\.venv\Scripts\python.exe -Arguments @('-m','giandoria.data_agent_service','--access-only')
```

An unexpected existing role causes failure. The explicit `--upgrade-viewer` migration permits only a reviewed
Viewer-to-Contributor change in this isolated workspace; normal reconciliation never escalates silently.
No model-access security group is needed. The identity script's explicit `-RemoveUnusedBuildGroup` switch
can remove only a recorded, exactly owned obsolete single-member Build group and its exact model grant.

Persist a newly validated runtime image for subsequent normal executions using
`Deploy-Runtime.ps1 -Stage Validate`, then `-Stage Deploy`. Updating the job template does not replace a running
execution. The published template includes the authentication client, but ordinary manager decisions still
use simulator briefings: no automatic Data Agent inference or snapshot refresh is enabled. Authentication
readiness is not a live decision data barrier. Normal Stop/deadline handling preserves this configuration;
no additional capacity, Key Vault or always-on service is created.

### Updating help while someone is using the lab

After validating the changed controller source, publish only runbook source/descriptions:

```powershell
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Deploy-Automation.ps1',
    '-Stage','Publish','-RunbooksOnly')
```

Start and Stop must already be Published and bound to `GiandoriaPowerShell`. A missing `Extend-GiandoriaLab`
is created in the same account only on an explicit HTTP 404; any existing Extend requires ownership tags and
the same Published/runtime checks. Other discovery errors abort rather than treating the runbook as absent.
An existing `Edit` state is accepted only if draft and published source are identical (apart from line endings
and surrounding whitespace). A genuinely changed unpublished draft blocks publication to protect operator edits.
It does not rewrite Automation
configuration, change schedule timing, operate on a session, start a worker or resume/pause Fabric.
The publisher snapshots and individually verifies bound arguments, including `Reconcile=True` for the hourly
check and session/expiry guards for existing deadlines. It repairs an incorrect hourly binding or arguments
lost during publication using a fresh binding ID, then verifies the persisted result. Updating an existing
binding ID can succeed without changing its arguments; list responses do not include authoritative parameters.
Publication may rotate binding IDs, so preservation is checked by runbook/schedule association, not a saved GUID.
Repair is logged as a warning and a failed readback aborts publication rather than reporting success.
Already-running jobs continue using their submitted version; future jobs use the newly published source.

## Monitored business collection

The runtime Job is deployed separately from the Fabric definitions. Build and validate before updating its
immutable image; publishing Automation configuration wires the recorded Job into Start/Stop.

```powershell
$record = '.\ops\Invoke-RecordedCommand.ps1'
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Build-Runtime.ps1')
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Test-RuntimeImage.ps1')
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Deploy-Runtime.ps1','-Stage','Validate')
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Deploy-Runtime.ps1','-Stage','Deploy')
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Deploy-Automation.ps1','-Stage','Publish')
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\ops\Invoke-BusinessExperiment.ps1',
    '-MinimumTick','17544','-TargetTick','17544')
```

The configured collection horizon is two calendar years from the scenario epoch, including leap day.
Each execution advances at most 744 hourly ticks, stops at the terminal tick and retains daily checkpoints.
The collector starts sequential executions under a two-hour independent shutdown schedule, observes durable
progress, rejects failed/concurrent/no-progress jobs and runs final Storage-to-Fabric verification.
Its `finally` requests Stop and independently checks Paused F4 and terminal executions.
An interrupted collection resumes the same checkpoint and decision ledger; it never silently resets the universe.

The runtime extra includes `websocket-client`, required by the synchronous Event Hubs WebSocket transport.
Container Apps diagnostics use resource-specific `ContainerAppConsoleLogs` and `ContainerAppSystemLogs` tables
in the existing project Log Analytics workspace, not the legacy `_CL` names. Runtime operation archives in
Storage retain safe HTTP audit and failure stack locations even when console ingestion is delayed.

### Runtime image maintenance

The base pins Python 3.13 on Debian trixie by digest. Builds refresh installed Debian packages and pinned pip;
a unique refresh argument invalidates the package layer and each build gets a distinct source-prefixed tag.
The deployed Job always uses the resulting immutable digest. Builds and isolated checks do not start the lab.
`Test-RuntimeImage.ps1` checks the exact digest in an isolated ACR task without lab credentials:
non-root UID, package inventory, dependency consistency and runtime imports.
Compare actual versions with Debian/PyPI fix evidence;
these checks are not a vulnerability scanner or proof that no CVEs remain.

Before deployment, retain the previous image record, inspect fresh Defender results for the new digest and
review image-only what-if. A missing assessment means scan pending/unknown, not clean.
Deploying a security refresh must not restart the business run, change checkpoints or activate F4.
Verify live digest, stopped executions and Paused F4 afterwards. Rollback selects a retained known digest and
repeats validation; never silently restore a known-vulnerable image. Historical images are retained rather
than deleted to make a registry-wide recommendation appear compliant.

Full verification compares SHA-256 hashes of exact raw enterprise envelopes in bounded sequence buckets,
checks contiguous archived sequences, conservation invariants and activity in all seven channels.
Identical delivery retries are accepted; altered payloads, extra identities and enterprise truth leakage fail.
Local archive caches and detailed results remain under ignored `.local`; do not publish them as an attempt diary.
Archive reads use at most eight workers and atomic cache files. Transport failures on these read-only requests
are recorded and retried at most three times; authorization errors are not retried or bypassed.
The cache can be reused after interruption without replaying simulation or model calls.
For a subsequent continuity check, pass `-PreviousLedger .local\business-verified-ledger.json` to the collector.
Local verification records are UTF-8, including non-ASCII explanations returned by virtual managers.
`Batch` preserves its terminal horizon. Ordinary Continuous Start instead appends to the retained universe.

## Bounded Fabric publish/replay experiment

Install the explicit publishing extra, then validate and run:

```powershell
$record = '.\ops\Invoke-RecordedCommand.ps1'
$experiment = '-NoProfile', '-File', '.\infra\demo\Invoke-FabricExperiment.ps1'
& $record -FilePath .\.venv\Scripts\python.exe -Arguments @('-m','pip','install','-e','.[fabric]')
& $record -FilePath pwsh -Arguments ($experiment + @('-Mode','Validate'))
& $record -FilePath pwsh -Arguments ($experiment + @('-Mode','Run'))
```

Validation is read-only and never resumes F4. Run requires F4 initially Paused and the retained synthetic fixture
`.local\foundation-events.jsonl`; missing input fails explicitly. To create it, follow the
[local run example](../../docs/README.md#running-the-first-local-increment) and export to that path.
Each Run adds two replay batches without deleting prior data.
The [Fabric summary](../../docs/20-fabric-walking-skeleton.md) explains validation scope, execution limits and
replay semantics.

## Read-only follow-up

```powershell
$record = '.\ops\Invoke-RecordedCommand.ps1'
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Test-DemoPublicAccess.ps1')
& $record -FilePath pwsh -Arguments @('-NoProfile','-File','.\infra\demo\Inspect-Demo.ps1')
```

This verifies current exemptions and security settings plus actual public Entra-authenticated Blob/Table/Queue
access. It checks that the same existing Blob cannot be read anonymously.
The access script never repairs exemptions or writes cloud data without `-WriteProbe`; existing probe blobs must
match expected synthetic content and are never overwritten. It is not a continuous monitor.
The inventory script reads capacity state, recorded item identities, operator role and lagged subscription costs.
It also counts project-tagged apps/jobs/private endpoints. A billing refresh is not a live spending limit.

## Verification

Offline guard regressions require no Azure access:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\tests\Test-CommandJournal.ps1
.\tests\Test-DemoInfrastructure.ps1
```

## Local records

Operational evidence is retained under ignored `.local`, not published as a development diary:

| Record | Purpose |
|---|---|
| `command-journal\*.jsonl` | Command/API start, completion, correlation, safe arguments, exit/status and body hashes |
| `fabric-experiment-*.json` | Per-run outcome, timings, counts and cleanup result |
| `demo-workspace.json`, `demo-fabric-items.json`, `demo-fabric-pending.json` | Ownership and interrupted-create recovery |
| `foundation-events.jsonl`, `fabric-experiment-ingest.kql`, `fabric-experiment-query-result.json` | Replay input and query evidence |
| `demo-public-access-check.json` | Latest waiver/settings/data-access check |
| `demo-cost-preflight.json`, `demo-fabric-retail-eur.json` | Lagged subscription cost and regional retail responses |

Keep journals and identity/recovery records when restarting development. Journaling does not retroactively capture
earlier unrecorded operations. Tokens, authorization headers and response bodies are not journaled; sensitive
arguments and context IDs are redacted. Local records are not public-download prerequisites for understanding the
repository: public summaries retain the conclusions and material limits.
