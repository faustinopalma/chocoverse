# 22 - Dashboard engineering

The business dashboard is created from code, not manually assembled in the browser. One Python publisher
generates a Fabric Real-Time Dashboard and a companion KQL Queryset from the same fifteen query files.
All authored page names, titles and column aliases are English. Business analysis uses virtual time;
real time is confined to technical diagnostics. No semantic model, DAX, PBIX or traditional Power BI
report is created by this Real-Time Dashboard publisher. A separate, shared Power BI semantic model
and two thin reports are described in [chapter 23](./23-semantic-model-showcase.md).

This chapter owns implementation and validation methodology. The [business lab](./21-business-lab.md#watching-the-company)
explains the analytical time contract and limitations; the [operating runbook](../infra/demo/README.md#watching-live-and-historical-data)
owns activation and publication commands. The wider clock design is in [chapter 07](./07-time-model.md).

## 22.1 Source map

| Source | Responsibility |
|---|---|
| [lab_views.py](../src/giandoria/lab_views.py) | Panel catalogue, stable identities, both JSON definitions, authenticated publication and definition readback |
| [fabric/queries](../fabric/queries) | Authoritative KQL text; identical in dashboard tiles and queryset tabs |
| [fabric_deploy.py](../src/giandoria/fabric_deploy.py) | Shared `RecordedRequests` transport: workspace scope, ownership preflight, audit, accepted item registry and asynchronous REST operations |
| [events.py](../src/giandoria/events.py) | Event identities, simulation UTC timestamps, local virtual dates and separate real timestamps |
| [business.py](../src/giandoria/business.py) | Business facts and module observations; authoritative meaning of quantities, postings and balances |
| [runtime.py](../src/giandoria/runtime.py) | Checkpointed event publication and `world.business.observed` snapshots |
| [test_lab_views.py](../tests/test_lab_views.py) | Offline definition, language, ownership-boundary and temporal-contract regression tests |
| [business_verify.py](../src/giandoria/business_verify.py) | Reusable authenticated Kusto `query` helper, including partial-query-failure detection |
| [cloud_io.py](../src/giandoria/cloud_io.py) | Recorded, host-restricted HTTP used by live query verification |
| [common.ps1](../infra/demo/common.ps1) and [Invoke-RecordedCommand.ps1](../ops/Invoke-RecordedCommand.ps1) | Guarded operator context and command journaling |

The publisher reads ignored local records produced by the deployment:

- `.local\demo-workspace.json`: recorded workspace name and ID.
- `.local\business-fabric.json`: enterprise query endpoint, database ID and matching workspace ID.
- `.local\demo-fabric-items.json`: accepted item identities, shared with other Fabric publishers.
- `.local\demo-fabric-pending.json`: pending creations and receipts used by the transport.

These are deployment state, not portable source configuration. Do not invent replacements or adopt
same-name items to bypass a mismatch. Tenant/subscription/object IDs and credentials do not belong in this guide.

## 22.2 Definition generation

`PANELS` is an ordered tuple of `(query_name, title, page, visual_type)`. The query name selects
`fabric\queries\<query_name>.kql`. Page order follows first occurrence in this catalogue.

`identity(name)` uses UUIDv5 with the namespace string `giandoria:lab-views:<name>`:

- `source` identifies the shared enterprise data source.
- The query name identifies both its dashboard query and queryset tab.
- `tile:<query_name>` identifies its tile.
- The page name identifies its page.

Generation is deterministic: the same source and endpoint produce the same definitions. Reordering panels
changes layout, not query/tile identities; renaming a page changes its page identity and can invalidate
bookmarked page selectors. Item identities remain in the deployment registry.

`definitions(root, endpoint, database)` validates the existing HTTPS Fabric Kusto endpoint and returns
documents keyed by `rt_giandoria` and `qs_giandoria`:

- Dashboard schema version `52`, one `manual-kusto` data source, inline query references, five pages.
- Queryset version `1.0.0`, one `AzureDataExplorer` source, one tab per panel.
- A simple vertical layout: `x=0`, width `12`, height `5`, advancing `y` by `5` within each page.
- Table, line or bar visuals; `visualOptions` is empty, allowing Fabric to infer columns and series.
- Dashboard auto-refresh defaults to ten real seconds. Refresh cadence controls when to ask for data,
  **not** the business time axis or the simulation speed.
- No global real-time range parameter is injected into business queries.

The Python generator is the source for these definitions; ignored `*-definition.json` files are readback
evidence, not files to edit. There is no import-time or Start-time dashboard deployment.

## 22.3 Query and metric catalogue

Every query reads `bronze_business` and explicitly selects the current implemented run,
`business-demo-001`. Another universe must not be mixed into its aggregates.
The prototype has a source-owned fixed 90-day window, not an interactive date-range selector.

| Page | Query | Output and interpretation |
|---|---|---|
| Overview | [company-now](../fabric/queries/company-now.kql) | Highest-sequence enterprise observation: UTC virtual instant, Rome virtual date, tick, finished stock/backlog/WIP in kg, cash/lifetime revenue/receivables/payables in EUR, planning strategy |
| Overview | [business-history](../fabric/queries/business-history.kql) | Full history of complete virtual days: sold, quality-released and dispatched kg |
| Overview | [manager-decisions](../fabric/queries/manager-decisions.kql) | Latest twenty deduplicated strategic decisions: virtual UTC timestamp, model/fallback mode, option, explanation and token usage |
| Sales | [sales-trend](../fabric/queries/sales-trend.kql) | Daily sold kg split into channel series over ninety complete virtual days |
| Sales | [channels](../fabric/queries/channels.kql) | Sold kg by channel over the same virtual window |
| Sales | [products](../fabric/queries/products.kql) | Sold kg by SKU over the same virtual window |
| Sales | [territories](../fabric/queries/territories.kql) | Sold kg by territory over the same virtual window |
| Operations | [operations-trend](../fabric/queries/operations-trend.kql) | Last available daily observation of finished stock, backlog, WIP, own-retail stock and trade stock in kg |
| Operations | [recent-business](../fabric/queries/recent-business.kql) | Sold, quality-released and dispatched kg over ninety complete virtual days |
| Finance | [finance-balances](../fabric/queries/finance-balances.kql) | Last available daily observation of cash, receivables and payables in EUR |
| Finance | [finance-flows](../fabric/queries/finance-flows.kql) | Daily revenue, purchases and conversion postings in EUR over ninety complete virtual days |
| Finance | [monthly-finance](../fabric/queries/monthly-finance.kql) | The same posting categories over all complete virtual months |
| Diagnostics | [lab-health](../fabric/queries/lab-health.kql) | Latest observed virtual instant, real update timestamp/age, configured speed and tick; not a worker-health probe |
| Diagnostics | [live-flow](../fabric/queries/live-flow.kql) | Deduplicated event counts in ten-second real UTC bins over the last fifteen real minutes |
| Diagnostics | [latest-events](../fabric/queries/latest-events.kql) | Latest twenty-five deduplicated enterprise events by sequence, showing virtual UTC time, Rome date, type and payload; no real-time cutoff |

### Flows, snapshots and units

Sold kg comes from `retail.sellout.recorded` and `trade.sellout.recorded`, not invoices.
Released kg comes from `factory.quality.released`, not production starts.
Shipped kg comes from `logistics.shipment.dispatched`, not delivery confirmation.
Thus sales, releases and shipments are related flows, not three equivalent revenue measures.

Finance charts read `finance.ledger.posted` and classify `event.data.posting_type`:

| Metric | Included posting types |
|---|---|
| Revenue | `retail.cash.received`, `finance.sales.invoice` |
| Purchases | `finance.purchase.invoice` |
| Conversion | `finance.conversion.paid` |

Amounts are integer cents in the source, divided by `100.0` for EUR. These charts do not sum cash settlement
events into revenue again. Cash and receivables/payables come from observations, not by summing periodic balances.
Revenue in the company-state table is lifetime cumulative revenue; finance flow charts show period postings.
There is no inventory valuation, statutory P&L, COGS, margin or inferred lost-sales/service-level measure.

## 22.4 Virtual-time query recipe

Business windows first obtain `end_day` from the maximum emitted local date of `world.business.observed`
for the selected run. They filter `end_day - 90d <= sim_day < end_day`. Full daily history omits the lower bound.
Monthly history uses `startofmonth` of the same observation anchor and excludes that month.

This is the **last observed virtual date**, not the latest sales date: a quiet sales period must not move the
window backwards. It is also not a verified ingestion watermark. Delayed facts can still revise earlier totals.
While the lab is stopped, the anchor remains frozen and the same query keeps its business window.
Tiles execute independently: during fast simulation, two refreshes can observe different virtual dates.
This dashboard is not a coordinated as-of report with a shared cross-tile cutoff. For exact reconciliation,
run the relevant source queries against the same explicit virtual cutoff in a separate analytical query.

Use emitted `simlocaldate`, rather than UTC `bin(sim_ts, 1d)`, for Rome calendar days. A day remains a business
date across daylight-saving changes; its UTC duration can be twenty-three or twenty-five hours. Intraday `sim_ts`
remains UTC. `virtual_date_rome` is explicitly formatted as `yyyy-MM-dd`: Kusto may infer ISO-looking JSON
strings as datetime values, so an unformatted `tostring` can otherwise expose an unwanted midnight timestamp.

Deduplicate flow facts with `summarize take_any(*) by event_id` **before** sums. Replayed identities are assumed
to have the same payload; the separate business ingestion verifier checks exact payload integrity.
For daily balances use `summarize arg_max(sequence, *) by sim_day`, which selects the latest observed state
and also collapses identical deliveries. Do not sum snapshots or claim these samples are exact closing balances.
Do not fabricate missing observations as zero or use `now()`, `ago()`, `wall_ts`, speed or activation-session IDs
to select business periods. Technical arrival queries are the explicit exception, on the Diagnostics page.

## 22.5 Publication and ownership

Use the publication command in the [operating runbook](../infra/demo/README.md#watching-live-and-historical-data).
It initializes the guarded Azure CLI context and executes `python -m giandoria.lab_views` through the recorded wrapper.
Dependencies are the existing project environment and runtime Azure Identity/HTTP libraries; no separate
dashboard authoring package or browser automation is required for publication.

`main()` performs these steps:

1. Check the recorded workspace display name and agreement between workspace records.
2. Build both documents using the recorded enterprise endpoint/database.
3. Obtain an Entra token for the Fabric API using `AzureCliCredential`; no secret is written into definitions.
4. Run `RecordedRequests.preflight`: list items with pagination and reject conflicting type, description marker
   or unrecorded identity. The marker is the `MARKER` constant in the publisher.
5. For each item, encode the document as an `InlineBase64` definition part:
   `RealTimeDashboard.json` or `RealTimeQueryset.json`.
6. POST `/v1/workspaces/{workspace}/items` for a new managed item, or
   `/v1/workspaces/{workspace}/items/{item}/updateDefinition` for an accepted existing one.
7. Follow accepted asynchronous operations within the shared five-minute publication deadline; accept completed
   HTTP 200/201 responses and fail explicitly on unsupported/failed operation responses.
8. Require an accepted item identity, POST `getDefinition`, decode its part and compare parsed JSON exactly
   with the requested document. Only then write the local readback copy.
9. Close the credential even on failure.

The shared transport restricts HTTPS hosts, workspace paths, methods and planned mutations; it records request
body hashes, sizes, HTTP outcomes and accepted creation receipts in `.local\command-journal`.
It does not allow arbitrary PATCH/DELETE, resource adoption or secret-bearing HTTP traces.
Publishing does not change source business data, restart the simulation or manage the capacity.
The two-item update is sequential, **not transactional**: on a partial failure inspect both items and safely
republish the complete source. A same-source rerun updates the registered items rather than creating duplicates.

### UI edits and metadata drift

The source owns the full definition. A subsequent publication replaces browser-authored changes;
export and reconcile intentional changes into source before republishing.

Saving a queryset in the UI can normalize the database ID to its display name and replace its description.
If preflight reports an ownership conflict, do not weaken ownership checks or automatically adopt the item.
Compare the registered item ID/type, source identity and all query contents with the prior readback.
Only after confirming there is no unincorporated user change may an operator restore the exact managed description
with a separately audited, scoped metadata update and rerun publication. Keep that evidence in ignored records.
Unexplained differences require review, not a blanket reset.

## 22.6 Validation methodology

Validation has four independent layers. Passing one does not imply the next.

### Offline regression tests

Run from the project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_lab_views.py -v
```

The tests verify deterministic generation; expected English title/page/tile labels and date aliases;
queryset/dashboard query equality; unique query identities; valid tile references; refresh settings;
enterprise-only sources; rejection of foreign endpoints; complete virtual-window selection; separation of
wall time; snapshot selection rather than summation; and acceptance of HTTP 201 publication completion.
They inspect generated documents and KQL contracts, **not** Kusto execution or browser rendering.

### Live KQL execution

With F4 active under a bounded lab session, execute every source query through the authenticated
`business_verify.query` helper and host-restricted `RecordedHttp`. Inspect result columns, units, row shapes
and partial-query status, not HTTP success alone. Nonempty results are expected for the retained populated
reference universe, but an empty result is not intrinsically an error for a newly created universe.
Keep query output and audit records in ignored storage, not in this guide.

### Controlled KQL fixtures

To verify semantics independently of the live scenario, prefix each source query with a Kusto
`let bronze_business = datatable(...) [...]` fixture defining the same query-facing columns:
`event_id`, `run_id`, `event_type`, `sim_ts`, `wall_ts`, `sequence` and dynamic `event`.
This shadows the source name within the query; it does not ingest or mutate a table.

Use known facts and exact expected results:

- Two sales of 10 and 5 kg, one 20 kg quality release and one 17 kg shipment.
- Revenue postings of EUR 100 and EUR 5, purchases EUR 10 and conversion EUR 5.
- Two observations on one completed local day with cash EUR 100 then EUR 120; the result must be EUR 120,
  not EUR 220. Add an observation on the next virtual date to anchor the window.
- Duplicate every row to model replay; all totals and balances must remain unchanged.
- Add a sale outside the 90-day window, a current-day sale and current-month posting, and a higher-sequence
  observation belonging to another run. Each must be excluded from the appropriate aggregate/anchor.
- Make a local date differ from the UTC calendar date to prove grouping uses `simlocaldate`.
- Run each business query twice with unchanged virtual facts: shift real timestamps by twenty-four hours
  and change recorded speed from 8,760 to 1. Compare complete result arrays for equality.

These controlled queries have verified all twelve business panels. The fixture is an integration technique,
not an automatic offline test or proof of a cloud controller restart; actual restart continuity is a separate
runtime concern. The three diagnostic panels intentionally do not satisfy wall-time invariance.

### Definition readback and browser checks

The publisher's exact parsed-JSON readback proves persistence. Separately open the item from the Fabric
workspace in an authenticated browser; CLI tokens do not sign in the integrated browser.
Select every page, wait for tables/charts to load and check:

- Expected tiles and English labels, usable layout, units, series and populated table columns.
- Business chart axes show virtual dates, not the real emission date.
- Channel trend splits into seven series; channel/product/territory bars show their respective categories.
- Only Diagnostics uses a real UTC arrival-time axis.
- No query-error tile. Browser console warnings alone do not establish a failed business query.

Scroll each page through its last tile: Fabric can defer rendering off-screen charts, so counting only
initially visible charts is not a complete rendering check.
All five pages have been opened successfully with rendered charts after integrated-browser authentication.
Authentication/loading problems do not justify recreating the item, changing business clocks, weakening
ownership guards or reporting unverified rendering as success.

## 22.7 Extending the dashboard

For a new metric, establish the enterprise event/observation and its unit first; choose flow aggregation or
snapshot selection; then select a virtual period and explicit incomplete-period policy.
Add the KQL source, one catalogue entry and the corresponding tests. Keep title, page, table aliases and units
in English. Validate offline, execute against Fabric, publish/read back, then inspect the browser.
Do not add a second managing tool or duplicate a query inside hand-maintained JSON.
Changes to metric meaning or time selection must also update this catalogue and the business time contract.
