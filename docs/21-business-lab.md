# 21 — The first causal business lab

The first business fidelity connects consumer demand to channel stock, replenishment, shipments, production,
material purchasing and cash. It is a modular monolith, not a collection of unrelated event generators.
The cloud path has collected and verified two calendar years with real weekly LLM decisions.
The [cloud runbook](../infra/demo/README.md) is the authoritative home for deployment and operating commands.

## Scope and boundaries

The [scenario](../config/business.json) defines all seven channel categories, three aggregate territories,
three one-kilogram product recipes and two daily line-capacity budgets. Channels retain their own stock;
the warehouse cannot ship unavailable finished goods, and the factory cannot consume missing ingredients or
packaging. Production takes six simulated hours, followed by the configured quality hold. Suppliers deliver
against purchase orders after material-specific lead times; distribution also takes simulated time.

This level does not implement the target 180-SKU assortment, individual stores or 107 provinces, machine-level
shifts/failures, complete seasonal negotiations, cold-chain constraints, reverse-time planning or inventory
valuation. Financial postings cover sales, purchases, conversion, receivables, payables and cash, not statutory
accounts or a complete profit-and-loss statement. Scenario quantities and prices are illustrative assumptions.

## Modules and causal flow

| Module | Owns | Exchanges |
|---|---|---|
| World and market | Calendar and seeded seasonal purchase intents | Intents to channels; hidden market events |
| Retail and trade | Channel stock, sell-out and replenishment pipeline | Sales observations and sales orders |
| Logistics | Central finished goods and outstanding orders | Delayed deliveries and wholesale invoices |
| Factory | Raw/packaging stock, daily capacity, WIP and quality release | Production schedules, receipts and released goods |
| Supply | Confirmed purchase orders and supplier lead times | Confirmations, delayed materials and invoices |
| Planning | Observed forecasts, replenishment targets, production and MRP policies | Production schedules and purchase orders |
| Finance | Cash, invoices and settlement schedules | Balanced postings and delayed collections/payments |

The [engine](../src/giandoria/business.py) routes every message no earlier than the next hourly tick.
Modules expose step, snapshot/restore, health and appropriately restricted observations. Each owns its state;
co-location in one container does not authorize direct cross-module mutations.
Conservation checks cover recipes, raw materials, WIP, factory/warehouse transfers, channel replenishment and cash.

## Rare strategic decisions

An S&OP chair reviews enterprise observations at the configured weekly interval. Routine forecasting, allocation,
production and purchase calculations remain rules. The manager selects a bounded planning option, not arbitrary
code, tools or transactions: forecast uplift is at most 15%, with two to four days of stock cover.
The selected option becomes a message and is applied on the next tick.

The [manager ledger](../src/giandoria/managers.py) persists a request reservation before inference, then records
the validated option, explanation, input digest, deployment/version and token usage. Replays reuse that record.
Interrupted reservations are not reissued; invalid responses, unavailable models and exhausted limits produce
an explicitly recorded rule fallback. The completed two-year collection used a run-wide guard of 110 calls
and 1,500,000 reserved tokens. Continuous operation allows at most 128 requests and 2,000,000 reserved tokens
per activation session, with at most 4,096 completion tokens per request. Restarting the same session cannot
reset its durable budget. These are request/token guards, not enforcement of the subscription's EUR budget.
Lifetime totals and every recorded decision remain in the same ledger; earlier decisions are never reissued.

`ReportProvider` is the live-runtime Fabric Data Agent integration seam. The current implementation exposes only
planning, logistics, factory and finance observations for the S&OP role. No manager receives latent market
intents or unrestricted module snapshots. A future report provider must preserve that boundary and cut-off.
The separate [Data Agent showcase](./24-data-agent-showcase.md) publishes an enterprise semantic-model-backed
agent for observers and an isolated S&OP experiment. It does not replace this provider or apply its decisions
to the running company.

## Persistence and operation

Azure Automation exposes three operator runbooks, Start/Extend/Stop, and owns the cloud shutdown deadline.
A separate manual Consumption Container Apps
Job owns simulation execution; Automation does not host the long-running business loop.
Start arms shutdown before activation. Stop requests quiescence, stops remaining executions, verifies capacity
state and does not expose a new session until concurrent controllers have settled.

The [runtime](../src/giandoria/runtime.py) checkpoints completed tick batches with their outbox before delivery,
archives their envelopes, publishes enterprise events, then acknowledges the outbox. A crash after delivery can
replay events with the same identities: downstream analysis must deduplicate by event ID. Checkpoint fingerprints
reject incompatible scenarios rather than silently resetting data. A renewable Blob lease excludes duplicate
workers; execution/session deadlines and the Job timeout bound compute separately.
The monitored two-year collector (`Batch`) advances no further than tick 17,544, preserving the leap day and
all restart state. Individual batch executions cover at most 744 hours; success without progress is an error.

Ordinary Start uses `Continuous`: it resumes the same universe beyond that collection horizon and runs until
Stop or the independent session deadline. `Speed` sets simulated seconds per real second, from 1 to 8,760.
The default 8,760 means approximately one simulated year per real hour; a business day takes about ten seconds.
Hourly ticks are paced rather than generated in an unbounded burst. Storage, ingestion and model latency can
reduce achieved speed; the runtime does not fast-forward to catch up after a slow call or while the lab is off.
Change speed at the next Start, without editing scenario configuration or invalidating its checkpoint.
`Analysis` activates Fabric for historical queries without advancing the business.
The [parameter guide](../infra/demo/README.md#parameter-guide-real-duration-versus-simulated-speed) lists portal
choices, technical fields to leave empty and examples separating real session duration from simulated speed.
Sessions default to four real hours and can be extended repeatedly with at most 24 hours remaining.
Extend keeps Fabric active and retains the same company/session, but replaces the simulation worker after
a checkpointed drain. The brief startup pause does not fast-forward simulation time or reset strategic budgets.
Previous shutdown schedules consult the current deadline before acting; manual Stop still wins over renewal.

Truth stays in retained Storage archives and is excluded from the enterprise publisher. The verified business
path is an Entra-authenticated custom endpoint into one low-throughput Eventstream and the `bronze_business`
table. Raw JSON is retained alongside queryable fields. Source acceptance alone is not proof of destination
completeness; the cloud experiment compares the retained outbox with queried identities and exact raw JSON hashes.

The local clock-only CLI remains independent and retains its original semantics. It does not start Azure
resources or pretend that offline hibernation is cloud shutdown.

## The retained reference dataset

The reference prefix of run `business-demo-001` covers 1 June 2030 through 1 June 2032, end-exclusive,
in `Europe/Rome`: 731 days and 17,544 hourly ticks. The completed cloud collection includes all seven channels,
two Easter seasons, 104 real-model strategic reviews and demand-to-cash, production and supplier activity.
Full sequence coverage, conservation invariants and exact enterprise payload equality have been verified.
Truth remains separate; these results do not imply the larger target assortment or machine-level fidelity.
Sequences 1-285,349 identify that immutable two-year prefix, including 239,296 enterprise events.
Continuous operation appends to the same run. It does not replace the reference prefix or reset the company.

### Prospective scenario interventions

The [scenario controller](../src/giandoria/business_scenario.py) stages an append-only plan for the existing run.
Each intervention has a stable ID, simulation-day boundary tick, reason, demand percentages and/or daily line
capacities. Percentages are absolute relative to baseline demand; capacities are absolute kg/day. Unspecified
settings retain their previous values. These are explicit scenario assumptions, not measured customer demand.
Day boundaries are multiples of 24 hourly ticks from the epoch; local dates follow the configured Rome timezone.
Capacity settings apply consistently to production planning and factory execution. Demand percentages change
market intent; forecasts continue learning from observed sell-out and retain the existing replenishment rules.

The baseline configuration and checkpoint fingerprint remain unchanged. The checkpoint retains the plan, and
restart reconstructs its effective settings before continuing. Past interventions cannot be rewritten, removed
or inserted retroactively. Each applied intervention emits an enterprise-visible `world.scenario.changed`
event; latent purchase intent remains truth-only. Company balances, pending messages and ledger history persist.

Offline rehearsal holds the S&OP policy at `balanced` *(assumption)* for comparable experiments; cloud managers
continue using their recorded model-driven decisions. A rehearsal is a scenario-selection aid, not cloud evidence.
Stage changes only after verified Stop and under the runtime lease. Start reads the staged plan and checkpoints
it before advancing. Commands and the control-file schema belong to the
[operating runbook](../infra/demo/README.md#prospective-scenario-interventions).
The [channel-expansion and maintenance plan](../config/scenarios/channel-expansion-maintenance.json)
records the retained run's prospective demand increase, temporary moulding restriction and capacity response.

With the capacity active under a bounded lab session, inspect the business KQL database using:

```kusto
bronze_business
| where run_id == "business-demo-001"
| summarize take_any(*) by event_id
| summarize event_count=count(), first_sim=min(sim_ts), last_sim=max(sim_ts) by event_type
| order by event_type asc
```

Deduplicate before aggregating because delivery is at-least-once. Add `where sequence <= 285349` to reproduce
the original two-year reference independently of subsequent live operation.

## Watching the company

The `rt_giandoria` real-time dashboard has five pages and fifteen tiles with a 10-second refresh.
The companion `qs_giandoria` query set exposes the same editable, source-owned
[queries](../fabric/queries). Publication is explicit through the [view publisher](../src/giandoria/lab_views.py);
no truth table or hidden market observations are exposed.

| Page | Business view |
|---|---|
| Overview | Latest company state, full daily volume history and strategic decisions |
| Sales | Daily channel trends and channel/product/territory mix over 90 complete virtual days |
| Operations | Finished goods, backlog, WIP, channel stocks and recent daily volumes |
| Finance | Cash/receivables/payables, daily revenue/purchases/conversion and complete monthly history |
| Diagnostics | Explicitly separate real-clock update age and event arrivals; recent activity ordered by sequence |

All business windows follow the latest `world.business.observed` virtual date, never `now()`, `ago()`,
wall time, ingestion time, session ID or speed. Daily grouping uses the emitted `simlocaldate` in Europe/Rome,
including daylight-saving changes; displayed intraday timestamps are UTC and are labelled accordingly.
The current virtual day/month is excluded from flow charts so partial periods are not compared with complete ones.
The company pulse still includes the current partial day's latest state. Pauses create no real-time holes in the
business axis; a restart or speed change appends to the same `run_id` and cannot shift the analytical window.
The last observed virtual date is an observation anchor, not a guarantee of ingestion completeness.
Totals deduplicate events by ID. Stock and balance charts select the highest-sequence observation per virtual day,
not sums of snapshots; these are sampled observations, not exact accounting closing balances. Missing observations
are not fabricated as zero. Purchase and conversion flows are not COGS or a statutory profit/loss measure;
no margin or service-level KPI is inferred from unavailable inventory valuation or hidden demand.

Only the diagnostic page uses real generation time and last-update age. When stopped, retained company values
are not proof of worker liveness. Observations are refreshed approximately every five seconds plus delivery/query
latency, even at slow simulation speeds. There is no manual pause/resume control inside the dashboard;
use the Automation runbooks.

The Eventhouse retains enterprise history for interactive KQL analysis while F4 is active.
Storage retains exact event archives (including separate truth), restart snapshots, the strategic ledger and
operation audits. Stop preserves both. The
[operating guide](../infra/demo/README.md#watching-live-and-historical-data) lists the paths, query examples
and analysis-only Start.

For the code map, metric definitions, API publication contract and validation methodology, see
[dashboard engineering](./22-dashboard-engineering.md).

For deeper Power BI modeling, the [semantic showcase](./23-semantic-model-showcase.md) adds one
shared import model and two thin reports: Commercial and Operations. They demonstrate virtual calendar
comparisons, filter context, semi-additive observed balances and a disconnected stock-policy parameter.
They use a common fixed enterprise snapshot, not live refresh; their cutoff card distinguishes them
from the Real-Time Dashboard. Neither the reports nor their what-if slicer controls the laboratory.

## Highest-value next Fabric showcases

More report pages alone add less value than completing the path from a changing observation to an explained,
governed action. The following are **proposed increments, not deployed capabilities**:

| Priority | Increment | Educational value and acceptance boundary |
|---|---|---|
| 1 | Current analytical evidence with a published virtual cutoff | Connect changing enterprise observations to a governed analytical source, expose its latest complete virtual date and reconcile identical-cutoff answers with KQL. An observer Data Agent over curated KQL can demonstrate live questions; application access has separate source-specific limitations. Keep the isolated application workspace and never grant the original truth-containing workspace merely to make this work. |
| 2 | Activator business exceptions | Demonstrate event-to-action behavior for backlog growth, material constraints or falling cash, with an alert ledger and deduplication rather than a notification per hourly tick. Keep actions observational initially: no automatic changes to the company. |
| 3 | OneLake Delta serving and Direct Lake | Materialize validated, deduplicated enterprise facts through a bounded pipeline, expose the same grains through a Direct Lake semantic model, and compare freshness and reconciliation with the existing import model. This teaches OneLake reuse, orchestration and semantic serving instead of just adding another visual. |

The first increment must distinguish an **observation anchor** from a certified completeness watermark.
Live dashboards can show the latest available observation, but manager decisions require all required sources
to be complete through the same exclusive virtual cutoff. Refreshing the existing embedded import partitions
does not extract new Eventhouse rows: the source publisher must extract, validate and republish a new snapshot.
Do not silently advance a snapshot while an observer is comparing report and agent answers.

Activator's processing/arrival clock must not define business duration. For a condition such as "backlog above
threshold for three virtual days", calculate that virtual-duration state upstream from deduplicated, ordered
business events and emit a transition for Activator to act on. A laboratory pause is neither three business days
nor evidence that backlog resolved; operational worker-staleness alerts intentionally use real time instead.
Rate-limit external notifications and define reset/re-arm behavior before enabling actions.

Direct Lake requires actual Delta tables and an explicit publication/framing contract; it is not an automatic
conversion of the existing embedded import snapshot into a live source. Keep this increment bounded on the
existing F4 and measure competing ingestion, query and processing load before scheduling it during a demo.

An operational prerequisite is explicit worker/ingestion freshness and visible failure recovery: active capacity
alone does not mean the simulator is alive. Automatic restarts would need bounded retries, checkpoint/lease
checks, preserved model budgets and an absolute prohibition on extending the shutdown deadline.
Machine OEE remains a separate simulation-fidelity increment requiring real availability, speed and good/reject
measurements; the existing daily capacity budget and quality-release flow are not substitutes.

Product references: [Data Agent sources](https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent),
[Activator](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/data-activator/activator-introduction),
[Direct Lake](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-overview).
