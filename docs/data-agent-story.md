# How far has Giandoria's supply recovered?

Giandoria buys ingredients, makes chocolate and sells through its own shops and other channels.
A channel expansion, a temporary moulding restriction and a capacity increase create a supply-recovery
review: **what has recovered, and what should Operations check before the next expansion?**

Follow three questions to a Fabric Data Agent. Compare product sales, trace the pattern through the factory,
then assess outstanding backlog. Each answer gives the next question a purpose.

## 1. Measure the commercial change

Product comparisons show which part of the business drives the change.
We compare September, November and February to locate the commercial signal across the episode.
The semantic model supplies the sell-out definition; calendar-day averages make the month lengths comparable.

**Recorded input — product sales:**

> How did daily sales change across September 2047, November 2047 and February 2048? Use our semantic-model
> sell-out measures. Give one table with each product's average kg per calendar day in the three months,
> rounded to one decimal. Identify the products behind the change.

![Fabric response: product sell-out per calendar day across the three review months.][recovery-sales]

Dark chocolate moves from **211.5 to 147.6 to 227.2 kg/day**; milk chocolate from
**190.4 to 106.9 to 169.9 kg/day**. Seasonal gianduja follows a different path, peaking in November.
The next investigation therefore follows dark and milk chocolate, which share the moulding line.

## 2. Follow the pattern through the factory

Operations needs to establish whether factory throughput follows the sales pattern.
Starts, releases and shipments locate the change along the supply flow.
The Lakehouse contains these product-level production records.

**Recorded input — production flow:**

> Does the sales pattern also appear in supply? Use Lakehouse SQL to compare September 2047, November 2047
> and February 2048. Combine dark70 and milk and return one row per month with started, released and shipped
> kg per calendar day, rounded to one decimal. Keep production flows distinct from sell-out.

![Fabric response: combined dark and milk production starts, releases and shipments per calendar day.][recovery-flow]

Combined shipments move from **397.2 to 253.1 to 404.9 kg/day**. Starts and releases show the same
November dip and February recovery. This is consistent with the episode's moulding restriction and capacity
response. The comparison describes the observed run; isolating each intervention's effect calls for controlled runs.

Throughput has recovered to September's pace. The next question is how that recovery reaches outstanding orders.

## 3. Check the backlog behind the recovery

Throughput describes pace; backlog describes outstanding company volume.
Operations needs its daily path as well as the closing position to assess how far the recovery has progressed.

**Recorded input — backlog recovery:**

> Has the company also reduced its backlog? Use the Lakehouse's observed company balances from 2047-11-01
> through 2048-02-29. Plot daily backlog and finished stock as a native line chart. For November and February,
> report average observed backlog, last observed backlog and the number of observed dates.
> Use every available observation.

![Fabric response: November and February company backlog, with observed-date counts.][recovery-backlog]

The native chart belongs to the **same input above**, using all **121 observed dates** in each series.

![Native Fabric chart: daily company backlog and finished stock from November through February.][recovery-history]

Average observed backlog falls from **983.0 kg in November to 533.3 kg in February**.
The final February observation is **0 kg**, compared with **1,119 kg** at November's close.
Together, the average and closing balance show a substantial recovery and the workload carried during February.
The comparison uses 30 November observations and 29 February observations.

## 4. Set the next operational checkpoint

**Make sustained backlog clearance the next checkpoint for expansion.**
Factory throughput has recovered; product sales and daily backlog give Operations a more complete view of readiness.

| Observed signal | Next operational check |
|---|---|
| Dark chocolate sales exceed September's pace; milk chocolate is at 169.9 versus 190.4 kg/day. | Review product and channel replenishment needs. |
| Combined dark and milk shipments recover to 404.9 kg/day. | Track whether the recovered flow is sustained. |
| February closes with zero backlog after averaging 533.3 kg. | Confirm sustained clearance and match product-level stock and open orders to new commitments. |

The Data Agent connects business questions to governed measures, SQL records and a visual trend.
Operations retains the decision, using each answer to focus the next check.

---

## Evidence and further reading

These executions use a fixed enterprise snapshot through **3 March 2048**; the review covers three complete
months ending in February. Dates are simulated business dates. The [scenario plan][scenario] retains the demand
and capacity assumptions; enterprise records supply the outcomes.
The retained run includes a January update aligning planning and execution capacity.
The [input/output record][evidence] owns provenance, exact responses and independently calculated reference values.

Inputs are quoted verbatim. Reply images are real Fabric browser screenshots; the chart is a native SVG export.
Captures cover published sales and authoring-mode supply and backlog.
Sales and production use calendar-day averages. Company balances use observed dates and retain company grain.
The companion guide owns [reproduction][companion] and separate [capability tests][capabilities].
Topics retrieval remains unverified; M365 feedback awaits an administrator-authorized sharing change.

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

[recovery-sales]: ./images/data-agent-story/recovery-sales.png
[recovery-flow]: ./images/data-agent-story/recovery-flow.png
[recovery-backlog]: ./images/data-agent-story/recovery-backlog.png
[recovery-history]: ./images/data-agent-story/recovery-history.svg
[scenario]: ../config/scenarios/channel-expansion-maintenance.json
[evidence]: ./data-agent-recovery-evidence.json
[companion]: ./29-data-agent-companion.md
[capabilities]: ./29-data-agent-companion.md#295-recorded-capability-tests
[agent-overview]: https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent
[agent-runtime]: https://learn.microsoft.com/en-us/fabric/data-science/data-agent-runtime
[agent-visuals]: https://learn.microsoft.com/en-us/fabric/data-science/data-agent-visuals
[agent-python]: https://learn.microsoft.com/en-us/fabric/data-science/data-agent-code-interpreter
