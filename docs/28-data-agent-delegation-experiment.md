# 28 - Testing the Data Agent

We test whether Fabric Data Agent helps answer specific questions about Giandoria's sales, cash and inventory.
We compare a generalist with and without the Data Agent, then repeat the comparison with full data access
to check whether company-specific rules make a difference.

## 28.1 Method

The tests ran on **21 October 2026**, using a **fixed snapshot through virtual 2034-09-03**.
The generalist was `gpt-5.6-terra`, version `2026-07-09`. No Copilot runtime was involved.

Questions and expected answers were fixed before inference. Expected values came from saved enterprise rows,
not from either agent. Source rows, formulas, relationships and the Data Agent's source configuration were
checked before and after each complete run. The dataset did not evolve between questions.

Direct query attempts were executed against Power BI, not just inspected as text.
Each question allowed one attempt, without automatic inference retries.
Wrong values, query errors and wrong output shapes counted as failures.
Numeric tolerance was 0.01; unavailable values had to be `null`.
Hidden simulator truth was excluded from every configuration.

## 28.2 Test with a summary only

The generalist received a company summary without detailed records.
We compared it with the same generalist allowed to ask the Data Agent.
A control received the Data Agent's answer directly.

| Question | Summary only | With Data Agent | Answer supplied directly |
|---|---|---|---|
| Monthly and year-to-date sales | No numerical answer | Correct | Correct |
| Sales for one product/channel/territory | No numerical answer | Correct | Correct |
| Two separate inventory-cover scenarios | No numerical answer | Correct | Correct |
| Unavailable OEE, margin and hidden demand | Correctly declined | Correctly declined, without delegation | Not needed |

The generalist chose to delegate the three answerable questions.
This shows that delegation supplied missing detail. It does not show better reasoning:
the generalist also succeeded when given the retrieved answer.

## 28.3 Test with full data access

The generalist could query all rows in the same semantic model through `executeQueries`.
We varied only the information provided about that model:

- **Schema:** tables, columns and relationships.
- **Catalogue:** schema plus measure names, DAX formulas, descriptions and formats.
- **Catalogue + instructions:** the same information plus the Data Agent's exact instructions.

The Data Agent answered independently through MCP. Its internal query and model were not exposed.
The first run used the catalogue configurations; a second added the schema-only configuration.
The four questions and data were unchanged.

| Question and expected answer | Catalogue, both runs | Catalogue + instructions, both runs | Data Agent, first run | Data Agent, second run | Schema, second run |
|---|---|---|---|---|---|
| August cash: EUR 3,435,099.60; 31 observed days; 31 calendar days | Correct | Correct | Correct | Correct | Correct |
| August `dark70` / `campaigns` / `centre`: 82 kg; production and cash unavailable at that grain | Correct | Correct | **86 kg: wrong** | Correct | Correct |
| Cover values 2 and 4 selected together: 3 days; target 1,252.7 kg | Correct | Correct | Correct | Correct | **Both `null`: wrong** |
| June 2030: 8,129 kg; cash `null`; 0 observed days; 30 calendar days | Correct | Correct | Correct | **Observed days `null`: wrong** | Correct |

The 82 kg reference is the sum of 31 matching Sales rows: eleven at 2 kg and twenty at 3 kg.
Executed model queries agreed. The source checks found no changes.
The Data Agent's earlier 86 kg answer was therefore wrong for this snapshot, but its cause is unknown.

## 28.4 The knowledge that made a difference

When cover values 2 and 4 were selected together, the schema-only generalist used:

```dax
SELECTEDVALUE('Cover policy'[Days])
```

That returns blank for multiple selected values. Its executed query returned `null` for both days and target.
Giandoria's published measure instead uses:

```dax
SELECTEDVALUE('Cover policy'[Days], 3)
```

The company rule defaults to **three days** and calculates the target from trailing 30-calendar-day sales.
The Data Agent and both catalogue configurations returned **3 days and 1,252.7 kg**.
The rows alone do not specify that default.

Other rules in [the instructions](../fabric/data-agent/instructions.txt) and
[the measures](../src/giandoria/showcase.py) define:

- virtual business dates rather than real dates;
- valid filters for sales, production and finance;
- balances as the last observation within a period, not sums of daily values;
- missing balances versus zero observation counts;
- financial meanings and measurements that are unavailable.

**The useful contribution is access to these rules, not exclusive expertise.**
Providing the catalogue directly also solved the policy question.
The Data Agent made errors elsewhere, so its answers still need checking.

## 28.5 Reproduce and limitations

The [runbook](../infra/demo/README.md#data-agent-delegation-comparison) contains the bounded commands.
They start analysis mode and stop the lab in cleanup, without advancing company time.
The [runner](../src/giandoria/agent_comparison.py) contains the questions, calculations and query execution;
[tests](../tests/test_agent_comparison.py) cover scoring, controls and failures.

All responses, queries and failures remain in ignored local records, including an interrupted attempt
not counted as a complete run. The comparisons do not change company state or Data Agent instructions.

These few cases are not an accuracy benchmark. They demonstrate retrieval and one business-rule failure,
not general superiority, live-data completeness or production readiness.
The Data Agent adds cost and latency; another governed query interface could provide the same rules.
