# Should Giandoria expand its partner campaigns?

Giandoria is considering a larger role for partner campaigns. The commercial team needs to understand their
sales contribution, then assess the stock and funding an expansion would require.

Follow a Fabric Data Agent investigation from the first question to a proposal for a controlled pilot.
The captured answers show what the records establish and which evidence the team should gather next.

## 1. A business decision before a query

Giandoria buys ingredients, makes chocolate and sells through its own shops and other channels.
Fabric brings these records together. A *Data Agent* turns business questions into queries over configured
sources, using their definitions to retrieve answers that can be inspected.

Here, it uses SQL for sales records and DAX for Finance's published measures. The team can concentrate on
the decision: **would a larger campaign generate profitable demand that Giandoria can serve and fund?**
We start with its existing sales contribution.

## 2. Start with a fair comparison

For seventy-percent dark chocolate in the central territory, compare campaign sales with sales across
all channels in the same month.

**Recorded input — commercial comparison:**

> For August 2034, how much seventy-percent dark chocolate did fictional partner campaigns sell in the central
> territory, and what share of that category's central-territory sell-out did campaigns represent? Apply our
> Commercial sell-out topic and show the numerator, denominator and percentage.

![Campaigns account for 82 kg of 1,994 kg sold: a 4.11% share.][commercial-answer]

**Campaigns contributed 4.11% of recorded sales** for this product, territory and month.
Keeping those filters aligned makes the comparison meaningful.

The execution trace below belongs to the same commercial input above. The *ontology*, a map of business
entities and relationships, resolves the product, channel and territory before SQL calculates the totals.

![Business labels are resolved before the SQL query runs.][ontology-grounding]

This establishes contribution. Measuring *additional* demand requires a comparable baseline or control;
assessing profitability also requires campaign costs and margins. Next, we look at the company's financial context.

## 3. Read cash as a balance

Finance's closing-cash measure returns the last observed balance in the month. Its definition lives in
the *semantic model*, where reusable business metrics are maintained.

**Recorded input — cash close:**

> For the company-wide August 2034 close, what was our closing cash in EUR? Show observation days and calendar days,
> explain why cash balances must not be added across days, and use the semantic model measures.

![August closing cash is EUR 3,435,099.60, with observations for all 31 days.][cash-answer]

The agent calls those measures through [DAX](./images/data-agent-story/cash-dax.png).
**EUR 3,435,099.60 is the company's closing balance.** Finance would assess scheduled payments and existing
commitments to determine how much could fund a campaign.

## 4. Recommend a measured next step

Before combining the findings, we ask which measures can describe the campaign itself.

**Recorded input — supported detail:**

> For August 2034, report Sold kg, Released kg and closing cash in EUR for dark70 sold through campaigns in centre.
> If the model cannot support a metric at that product/channel/territory grain, say unavailable rather than
> allocating or inventing it.

![Sales returns 82 kg; production and cash are unavailable at the requested campaign detail.][boundaries-answer]

Sales identifies product, channel and territory. Production identifies date and product; cash identifies
company and date. These different levels of detail explain why the briefing keeps campaign sales and company
cash separate.

**Prepare a bounded pilot proposal. Launch it once Commercial, Operations and Finance establish its value,
feasibility and spending limits.**

The 82 kg establishes an existing campaign contribution. The next step is to test whether a larger campaign
would create additional profitable sales. Three checks turn that proposal into an executable plan:

| Decision gate | Evidence required before launch |
|---|---|
| Commercial value | A comparable baseline or control, incremental sales and margin after campaign costs. |
| Supply feasibility | Usable stock, existing commitments and replenishment lead times for the proposed campaign. |
| Cash exposure | Scheduled payments, a spending cap and a stop condition agreed with Finance. |

The proposal should set the budget, duration and success criteria from these checks. Broad expansion remains
conditional on the pilot's results. This is the team's recommendation; the Data Agent supplies inspectable evidence.

The investigation ends here. The following demonstrations explore stock-policy rules and daily patterns;
they complement the review rather than provide the missing launch evidence.

## 5. Further analysis: stock policy

A stock target depends on a policy assumption. This example shows how the semantic model handles two
cover-day values selected together.

**Recorded input — stock policy:**

> At snapshot end 2034-09-03, suppose the Cover policy slicer has both 2 and 4 selected simultaneously, not two
> separate scenarios. Which cover-days value and stock target in kg does the semantic model return? Use the
> published one-decimal kg precision. Does this change production?

![Selecting two and four cover days together returns the three-day default and a 1,252.7 kg target.][policy-answer]

The measure uses its **3-day default**, producing a **company-wide target of 1,252.7 kg**.
Comparing two policies would require evaluating each separately.

This is a planning target. Campaign availability requires the inventory checks above; changing production
requires a separate authorized action.

## 6. Further analysis: daily sales

A daily view reveals variation hidden by the monthly total. We retrieve the complete month before charting it.

**Recorded input — complete daily table:**

> Show the complete daily company sell-out table for August 2034: every date from August 1 through August 31,
> ordered by date, with Sold kg. Return all 31 rows, not just a preview of 25, and state the snapshot cutoff.

The [daily result](./images/data-agent-story/daily-rows.png) contains all **31 dates**, checked against the source.

**Recorded input — native chart:**

> For August 2034, show daily company Sold kg as an interactive native Fabric line chart, not a Python image.
> Label virtual date and kg and state the snapshot cutoff.

![Native Fabric chart of daily company sales across all 31 August dates.][native-chart]

This is a static export of the native chart. In Fabric, hovering reveals each date and value.
It shows company-wide sales; assessing a campaign's daily effect would require a campaign-specific comparison.

## 7. Further analysis: production timing

We can also explore how daily sales and production releases move together. Each flow is totalled by date
before the two series are paired, preserving the quantities.

**Recorded input — Python calculation:**

> Use Code Interpreter to calculate the Pearson correlation between daily company Sold kg and Released kg for
> August 2034. Aggregate each flow by date before combining it, include all days, and report the paired-day count
> and correlation to four decimals. Show the Python execution, distinguish association from causation, and
> explicitly say if the tool is unavailable.

![Code Interpreter executes Python over the retrieved daily data.][python-execution]

The [answer](./images/data-agent-story/python-answer.png) reports **31 paired days** and a Pearson correlation
of **-0.3069**, matching an independent calculation.

This modest negative same-day association describes one month of company-wide activity. Understanding its
cause would require examining production schedules and inventory timing. Its role here is to demonstrate
a reproducible calculation, rather than to set campaign or production policy.

---

## Evidence and further reading

These recorded executions use a snapshot through **3 September 2034**; August is the last complete month.
Inputs are quoted verbatim, and numerical results were independently checked.

The commercial trace demonstrates ontology resolution and SQL; [Topics retrieval remains unverified][topics-status].
[M365 consumer feedback is blocked][feedback-status] by the current sharing setting.
Reproduction steps, access requirements and feature limits belong to the
[companion guide](./29-data-agent-companion.md). The ontology has a
[migration requirement](./26-fabric-ontology.md) before its announced retirement on **31 January 2027**.

Microsoft documentation: [Data Agent overview][agent-overview], [query runtime][agent-runtime],
[native charts][agent-visuals] and [Code Interpreter][agent-python].

## Closing note — experiment with the Chocoverse

This review is one investigation inside **Chocoverse**, Giandoria's evolving business universe.
The [original repository](https://github.com/faustinopalma/chocoverse) contains its code, scenarios and laboratory.
Purchases, production, deliveries, sales and financial movements form a continuing story in **virtual time**.
Pause it, resume it or change a scenario to explore a different course.

Fabric provides complementary views: Eventhouse and Real-Time Dashboards follow operational events;
Lakehouse, the semantic model and Power BI organize analytical snapshots and business measures.
Ontology connects entities, the Data Agent answers questions over configured sources, and the Decision Room
supports governed investigations.

Live views follow incoming events; snapshot-based views advance through explicit extraction and publication.
This article retains a fixed snapshot. The [project tour](../README.md) and [implemented scope](./README.md)
explain the current reduced-detail runtime and wider design.
Use the [laboratory runbook](../infra/demo/README.md) to experiment; Azure/Fabric runs incur charges and require
its start, shutdown and cost controls.

[commercial-answer]: ./images/data-agent-story/commercial-answer.png
[ontology-grounding]: ./images/data-agent-story/ontology-grounding.png
[cash-answer]: ./images/data-agent-story/cash-answer.png
[policy-answer]: ./images/data-agent-story/policy-answer.png
[native-chart]: ./images/data-agent-story/native-chart.svg
[python-execution]: ./images/data-agent-story/python-execution.png
[boundaries-answer]: ./images/data-agent-story/boundaries-answer.png
[topics-status]: ./29-data-agent-companion.md#c-schema-descriptions-and-topics-teach-context-at-the-correct-scope
[feedback-status]: ./29-data-agent-companion.md#h-consumer-feedback-close-the-loop-without-claiming-automatic-learning
[agent-overview]: https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent
[agent-runtime]: https://learn.microsoft.com/en-us/fabric/data-science/data-agent-runtime
[agent-visuals]: https://learn.microsoft.com/en-us/fabric/data-science/data-agent-visuals
[agent-python]: https://learn.microsoft.com/en-us/fabric/data-science/data-agent-code-interpreter
