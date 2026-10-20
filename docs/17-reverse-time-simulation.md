# 17 — Reverse-time simulation: my planning method

> **The idea:** start from delivery dates and simulate towards the past to find when production and purchasing
> must happen, accounting for finite capacity rather than subtracting fixed lead times.
>
> I developed this approach independently in 2015 for seasonal chocolate gift packs, using unmodified SimPy.
> My earliest dated record is a July 2015 presentation. The literature calls the core idea *backward simulation*
> and predates my work; I claim no priority.

**See the original project:** [faustinopalma/sim_factory_original](https://github.com/faustinopalma/sim_factory_original)
contains the Excel-driven SimPy model, a restyled presentation and illustrated English documentation.
Its [technical note](https://github.com/faustinopalma/sim_factory_original/blob/main/docs/reverse-time-simulation.md)
explains the time mapping and distinguishes it from the worked examples' input and reporting conventions.
It is a separate repository, not an already integrated Chocoverse planning engine.

## 17.1 The planning question

A Christmas assortment needs several chocolates, shared wrapping machines and printed packaging.
Making everything early wastes shelf life, stock space and cash. Ordering too late misses the delivery.

**What is the latest feasible time for each operation and purchase?**

Fixed-offset MRP ignores competing resource demands. Forward simulation tests what can happen from today.
A backward simulation builds a candidate plan from the deadlines; a forward check then tests whether today's
materials, open orders and resource states can support it.

## 17.2 The mirror

SimPy's clock still increases. Only its interpretation changes:

```text
T = reference date at the end of the planning horizon
s = increasing simulation clock
t = T - s = corresponding factory-calendar time

A reservation [s_a, s_b] becomes [T - s_b, T - s_a].
```

Durations and overlaps are preserved, so a single-capacity machine remains single-capacity.
The simulation's start becomes the calendar finish. Precedence and calendar rules must be reversed explicitly.

This reverse clock is internal to a planning call. It must not replace the company's continuous virtual time
or introduce wall time into business analysis.

## 17.3 What must be reversed

* **Due dates:** release each finished-product request at `s = T - due_date`.
* **Dependencies:** assembly asks for its components when it completes in reverse time.
* **Calendars:** reflect shifts and closures; calculate elapsed time in UTC, retaining Europe/Rome shift rules.
* **Changeovers:** transpose directional setup times, not just the product sequence.
* **Lags:** retain minimum waits; explicitly validate maximum holds and repair or reject violations.
* **Inputs:** net stock in calendar order; validate current stock, ETAs and line states in the forward pass.

Use deterministic priorities and planned durations. Breakdowns and other uncertainty belong in forward scenarios.

## 17.4 Production boxes

A **production box** is a request carrying an item, quantity, need date, consuming operation and customer order.
It queues for machines and crews, reserves work, then requests its own components recursively.
Purchased items lead to latest order dates. The links preserve **pegging**: which customer needs each material.

Requests can share a campaign, but consolidation may move later demand earlier. Shelf life and consolidation
windows still constrain that choice.

## 17.5 Two passes and slack

| Pass | Starting point | Result |
|---|---|---|
| Backward | Delivery deadlines | Candidate latest starts/finishes and purchase dates |
| Forward | Today's available resources, stock and ETAs | Earliest starts/finishes and delivery feasibility |

`Slack = latest start - earliest start`, measured per operation in elapsed hours.
Negative slack flags a conflict between these candidate schedules, not proof that every alternative is infeasible.
Weekends and shifts make slack non-additive: do not sum it along a route.

Both passes are heuristic. Compare their schedules and check all constraints before publishing a plan as feasible.

## 17.6 A small example

Assume one uninterrupted shift, available materials, no setup time and a Friday 18:00 delivery.
The order needs three hours of wrapping, then two hours of packing:

| Step | Backward reservation | Forward check |
|---|---|---|
| Wrapping | Friday 13:00–16:00 | Can start only at 14:00; finishes at 17:00 |
| Packing | Friday 16:00–18:00 | Starts at 17:00; finishes at 19:00 |

Each operation has **−1 hour of start slack**; the order is **one hour late**, not two.
The planner must change an input: release materials earlier, add suitable capacity or renegotiate delivery.
A real seasonal plan adds competing orders, closed shifts, quality holds and supplier lead times to this same logic.

## 17.7 Intended role in Giandoria

The target architecture uses this method for seasonal capacity checks, MPS feasibility, capacity-aware MRP dates,
capable-to-promise and agent briefings. Detailed short-horizon optimization can complement it with CP-SAT.

**Implementation boundary:** these are design intentions. Chocoverse's deployed reduced-detail business runtime
does not implement the full two-pass engine described here. The Decision Room's stock-cover selector is arithmetic
sensitivity, not this scheduler. See the [current implementation map](./README.md) for shipped scope.

## 17.8 Execution contract

The proposed engine builds one fresh environment per call, uses only enterprise-visible inputs and converts every
result back to virtual-calendar timestamps. Outputs retain resource, pegged order, earliest/latest dates and slack.
Versioned inputs and stable tie rules make results reproducible.
Conflicts produce explicit exceptions for a planner, agent or bounded fallback; they must not be hidden as success.

## 17.9 Acceptance checks

Before integrating the engine, verify hand-computed schedules, mirrored precedence and resource capacity,
closed shifts and daylight-saving transitions, shared crews, netting, maximum lags and deterministic replay.
Reproduce the small example above and forward-check any plan labelled feasible.
These are acceptance requirements, not claims of an existing passing scheduler test suite.

## 17.10 Origin and prior art

My contribution is an independently developed application to seasonal confectionery: unmodified SimPy, recursive
production boxes, shared resources and shift calendars. It is not the invention of backward simulation itself,
nor a claim to the first SimPy implementation.

The literature includes backward scheduling from 1989 [P39], forward/backward improvement [P48], task float [P44]
and time symmetry [P49]. A 2024 review [P47] provides the broader history.
Full citations **P39–P49** and the limits of that research remain in
[chapter 16](./16-references.md#163-production-supply-and-planning-methods-p).

## 17.11 Limits

The result depends on priorities and modelling assumptions; it is not guaranteed globally optimal.
Maximum lags, rework and path-dependent machine states need explicit handling, not faith in the time mirror.
Random disruptions require forward testing. A plausible chart is not a feasibility proof.
