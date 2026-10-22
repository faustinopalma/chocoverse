# What should Giandoria check before promising more volume?

Giandoria buys ingredients, makes chocolate and sells through its own shops and other channels.
Each part of the value chain contributes records to Fabric. Before confirming additional volume,
Operations needs to understand stock and outstanding demand.

Follow three questions to a Fabric Data Agent: establish the inventory position, check whether the signal
recurs, then find the detail needed to act. Each answer determines the next step.

## 1. Establish the current position

Operations first needs the latest recorded finished stock and backlog. These balances show the starting
position for a supply review; production releases and sales describe flows over a period.
The semantic model gives those concepts explicit measures.

**Recorded input — inventory position:**

> Before we promise additional volume, what does our latest company inventory observation show? Use the semantic
> model measures. Report the observation date, finished stock and backlog in kg. Keep balances at company level
> and distinguish observed facts from delivery commitments.

![The observed company position on 3 September: 0 kg finished stock and 37 kg backlog.][inventory-position]

The answer retrieves the published balances. **Zero recorded finished stock alongside backlog**
gives Operations a concrete reason to investigate supply. Its significance depends on whether this is an
isolated observation or a recurring condition.

## 2. Check whether the condition recurs

A single closing observation can reflect timing. We therefore examine the preceding 30 days.
If stock recovers consistently, the latest observation deserves a different interpretation from repeated
zero-stock observations with outstanding demand.

**Recorded input — persistence:**

> To decide whether this calls for an operational review rather than reacting to one day, show company finished
> stock and backlog for each observed date from 2034-08-05 through 2034-09-03. Use the Lakehouse SQL source.
> Return every observed date, then create a native line chart with both series. Report the observation count
> and how many observations have zero finished stock and positive backlog. Treat missing dates as unknown,
> not zero. These are balances: do not sum them across days or infer lost sales.

![The agent returns 30 observed dates and identifies seven zero-stock observations with positive backlog.][inventory-persistence]

The following native chart belongs to the **same input above**. SQL retrieves the daily company observations;
the visualization shows how stock and backlog change together.

![Native Fabric chart: finished stock and backlog, with all 30 observations in each series.][inventory-history]

The condition recurs on **7 of 30 observed dates**, including three consecutive dates on 24–26 August.
This supports a review of replenishment and allocation timing. Quantifying missed sales, service failures
or production constraints would require their own records.

## 3. Find the detail needed to act

Operations now needs to identify which products require attention. Company totals establish the signal;
a replenishment priority list requires product-level stock and outstanding orders.
We ask whether the available model supports that next step.

**Recorded input — product priorities:**

> Which products should Operations replenish first? Break down the latest observed finished stock and backlog
> by product using the semantic model. If those balances are only recorded at company level, state that limit
> and the additional records needed for a product priority list. Keep sales and production flows distinct
> from inventory balances.

![The agent identifies the company-level boundary and the records needed for product priorities.][inventory-detail]

The semantic model keeps these balances at company level. Product-level inventory and open orders,
with reservations and due dates, would let Operations rank replenishment needs.
Sell-out records completed purchases; production records starts, releases and shipments.
Both remain distinct from available stock and total demand.

## 4. Turn the evidence into a next action

**Review the recurring stock-and-backlog condition before promising additional volume.**
The investigation identifies a recurring signal and the detail required to make a product-level decision.

| What the evidence supports | Next operational step |
|---|---|
| Seven observed zero-stock dates with backlog in a 30-day window. | Check replenishment and allocation timing. |
| Stock and backlog are recorded at company level. | Obtain product-level usable stock, reservations and open orders. |
| Delivery commitments require quantities and dates. | Match those records to replenishment lead times before confirming volume. |

The Data Agent connects everyday questions to governed measures, SQL results and a visual trend.
Operations retains the decision: use the signal to focus the review, then use the right detail to act.

---

## Evidence and further reading

These executions use a fixed enterprise snapshot through **3 September 2034**.
Inputs are quoted verbatim. Results and all 60 chart points were checked against the source snapshot.
The reply images are **rendered exports of the actual response text**, labelled accordingly; the chart is an
unmodified native Fabric SVG export. The [input/output record](./data-agent-inventory-evidence.json) retains
the response prose.

The [companion guide](./29-data-agent-companion.md) owns reproduction, access requirements and separate
[capability tests](./29-data-agent-companion.md#295-recorded-capability-tests) for cash, stock-policy defaults,
row completeness and Python. Topics retrieval remains unverified; M365 feedback remains blocked by the
current sharing setting. These statuses are independent of the inventory findings.

Microsoft documentation: [Data Agent overview][agent-overview], [query runtime][agent-runtime],
[native charts][agent-visuals] and [Code Interpreter][agent-python].

## Closing note — experiment with the Chocoverse

This investigation is one episode inside **Chocoverse**, Giandoria's evolving business universe.
The [original repository](https://github.com/faustinopalma/chocoverse) contains its code, scenarios and laboratory.
Purchases, production, deliveries, sales and financial movements form a continuing story in **virtual time**.
Pause it, resume it or change a scenario to explore a different course.

Fabric provides complementary lenses: Eventhouse and Real-Time Dashboards follow operational events;
Lakehouse, the semantic model and Power BI organize analytical snapshots and business measures.
Ontology connects entities, the Data Agent answers questions over configured sources, and the Decision Room
supports governed investigations.

Live views follow incoming events; snapshot-based views advance through explicit extraction and publication.
This article retains a fixed snapshot. The [project tour](../README.md) and [implemented scope](./README.md)
explain the current reduced-detail runtime and wider design.
Use the [laboratory runbook](../infra/demo/README.md) to experiment; Azure/Fabric runs incur charges and require
its start, shutdown and cost controls.

[inventory-position]: ./images/data-agent-story/inventory-position.png
[inventory-persistence]: ./images/data-agent-story/inventory-persistence.png
[inventory-history]: ./images/data-agent-story/inventory-history.svg
[inventory-detail]: ./images/data-agent-story/inventory-detail.png
[agent-overview]: https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent
[agent-runtime]: https://learn.microsoft.com/en-us/fabric/data-science/data-agent-runtime
[agent-visuals]: https://learn.microsoft.com/en-us/fabric/data-science/data-agent-visuals
[agent-python]: https://learn.microsoft.com/en-us/fabric/data-science/data-agent-code-interpreter
