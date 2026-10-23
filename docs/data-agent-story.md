# Investigating Giandoria's supply recovery with a Fabric Data Agent

## Giandoria in the Chocoverse

Giandoria is an established Italian chocolate maker, supplying its own shops, supermarkets and export channels.
**Chocoverse** is its connected business world: suppliers, planners, factory teams, logistics partners and customers.

Customer orders, shared forecasts and sales information feed back into demand planning.
Finance follows costs and cash across the chain; Microsoft Fabric brings its business records together.

## This recovery review

In September 2047, Giandoria expands its supermarket and export channels. In late October, an unexpected equipment
malfunction requires unplanned maintenance on the moulding line, which shapes the chocolate, reducing its capacity.
Giandoria adds shifts in late December.

By the end of February, Operations asks: **is Giandoria supplying its customers again?**
How did sales fare during the disruption? Have shipments recovered? Are orders still waiting to be shipped?

Let's ask a Fabric Data Agent, starting with sales. We compare September, before maintenance,
November, during the reduced-capacity period, and February, after the additional shifts.

## 1. Measure the commercial change

Operations first needs to identify which product sales fell during the supply disruption and how far they recovered.
We compare *sell-out*, the chocolate actually sold to customers, across the three months.
These are realized sales, not a measure of underlying demand: availability can limit what customers can buy.
The comparison identifies the products to follow through the factory next.
Calendar-day averages make the month lengths comparable.

**Recorded input — product sales:**

> How did daily sales change across September 2047, November 2047 and February 2048? Use our semantic-model
> sell-out measures. Give one table with each product's average kg per calendar day in the three months,
> rounded to one decimal. Identify the products behind the change.

![Fabric response: product sell-out per calendar day across the three review months.][recovery-sales]

Dark chocolate moves from **211.5 to 147.6 to 227.2 kg/day**; milk chocolate from
**190.4 to 106.9 to 169.9 kg/day**. Seasonal gianduja follows a different path, peaking in November.
The next investigation therefore follows dark and milk chocolate, which share the moulding line.

## 2. Follow the pattern through the factory

Operations now needs to check whether the factory is supplying the products behind the sales change.
*Throughput* is the volume moving through production over time. We compare starts, releases and shipments.
The Lakehouse contains these product-level production records.

**Recorded input — production flow:**

> Does the sales pattern also appear in supply? Use Lakehouse SQL to compare September 2047, November 2047
> and February 2048. Combine dark70 and milk and return one row per month with started, released and shipped
> kg per calendar day, rounded to one decimal. Keep production flows distinct from sell-out.

![Fabric response: combined dark and milk production starts, releases and shipments per calendar day.][recovery-flow]

Combined shipments move from **397.2 to 253.1 to 404.9 kg/day**. Starts and releases show the same
November dip and February recovery. This pattern is consistent with the lower moulding capacity during maintenance
and the subsequent increase. The monthly comparison alone cannot separate the effects of capacity and demand.

Throughput has recovered to September's pace. The next question is how that recovery reaches outstanding orders.

## 3. Check the backlog behind the recovery

The factory's recovered pace raises another question: what has happened to orders still waiting to be shipped?
This outstanding volume is the company's *backlog*. Operations needs its daily trend and month-end position
to see whether the recovery is reaching those orders.

**Recorded input — backlog recovery:**

> Has the company also reduced its backlog? Use the Lakehouse's observed company balances from 2047-11-01
> through 2048-02-29. Plot daily backlog and finished stock as a native line chart. For November and February,
> report average observed backlog, last observed backlog and the number of observed dates.
> Use every available observation.

![Fabric response: November and February company backlog, with observed-date counts.][recovery-backlog]

The chart belongs to the **same input above**, using all **121 observed dates** per series.

![Native Fabric chart: backlog in blue and finished stock in magenta,
with 121 observed dates per line.][recovery-history]

Average observed backlog falls from **983.0 kg in November to 533.3 kg in February**.
The final February observation is **0 kg**, compared with **1,119 kg** at November's close.
The average also reveals the workload carried during February.
The comparison uses 30 November observations and 29 February observations.

## 4. What the investigation tells us

Giandoria's recovery appears across all three answers. Dark chocolate sales rise above September's pace,
while milk chocolate sales recover only part of their decline. Combined dark and milk shipments reach
**404.9 kg/day**, slightly above September's **397.2 kg/day**.

That recovered flow also reaches outstanding orders: average backlog falls from **983.0 kg in November
to 533.3 kg in February**, and February closes at **zero**. The closing balance marks the clearance of the
backlog; the monthly average shows that Giandoria was still working through it during February.

The investigation starts with the commercial symptoms, checks factory shipments, then follows orders awaiting delivery.
Using natural-language questions, the analyst follows that thread across semantic-model measures, Lakehouse SQL
and a daily chart. Together, the answers show a recovery in supply and order fulfilment, with an uneven recovery
in product sales.

---

## Sources

The review uses September and November 2047 and February 2048 data, available through **3 March 2048**.
The [complete responses and checked figures][evidence] support the results shown above.
The [technical guide][companion] explains how to reproduce the analysis and records its verification limits.

## Closing note — follow Giandoria through the Chocoverse

This investigation is one episode inside **Chocoverse**, Giandoria's evolving business universe.
The next review can follow how Giandoria turns this recovery into reliable supply across its channels.

Fabric provides complementary lenses: Eventhouse and Real-Time Dashboards follow operational events;
Lakehouse, the semantic model and Power BI organize analytical snapshots and business measures.
Ontology connects entities, the Data Agent answers questions over configured sources, and the Decision Room
supports governed investigations.

The [project tour](../README.md) introduces the wider Chocoverse.
The [original repository](https://github.com/faustinopalma/chocoverse) and [technical guide][companion]
provide the implementation and reproduction instructions.

[recovery-sales]: ./images/data-agent-story/recovery-sales.png
[recovery-flow]: ./images/data-agent-story/recovery-flow.png
[recovery-backlog]: ./images/data-agent-story/recovery-backlog.png
[recovery-history]: ./images/data-agent-story/recovery-history.svg
[evidence]: ./data-agent-recovery-evidence.json
[companion]: ./29-data-agent-companion.md
