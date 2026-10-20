# 20 - Fabric walking skeleton

## Summary

The demo can publish Eventhouse/KQL definitions with `fabric-cicd`, replay retained synthetic CloudEvents and
verify them after a capacity suspend/resume cycle. The bounded test passed with **53 unique events**.
This validates a small direct-Kusto path, not the Eventstream pipeline or production throughput.
Use the [infra guide](../infra/demo/README.md) for prerequisites, commands and local diagnostic records.

## What is deployed

We use one existing demo workspace on the Sweden Central F4, with no additional Azure resources or environments.
The pinned `fabric-cicd==1.4.0` publisher manages these source-controlled items [F44][F98][F99]:

| Item | Type | Scope |
|---|---|---|
| `eh_giandoria` | Eventhouse | Minimum consumption units unset/zero |
| `kqldb_giandoria` | ReadWrite KQL database | Explicitly created under the recorded Eventhouse |
| `bronze_lab` | Experimental table | Synthetic clock events, not the four target business/truth bronze tables |

Definitions live in [fabric](../fabric). The
[publisher](../src/giandoria/fabric_deploy.py) only permits the recorded workspace, expected item types and planned
mutations. It does not delete items or silently adopt same-name items.
Deployment currently uses the signed-in operator's existing workspace Admin and capacity-control permissions.
The secretless CI deployment identity and its minimum permissions remain to be implemented.

## Verified behavior

Verified on **2026-10-18**, with `fabric-cicd==1.4.0`:

| Check | Result |
|---|---|
| Definitions | Items created and updated in place; KQL database explicitly created under the Eventhouse |
| Schema | `.create-merge table` and additive column changes work through `DatabaseSchema.kql` |
| Replay | Two copies of 53 events appended; exact expected raw-row growth and 53 unique identities |
| Fidelity | Sequence, type, sim timestamp, selected decoded fields and exact original JSON text checked |
| Persistence | Previously ingested events remained available after suspend/resume |
| Cleanup | F4 independently confirmed `Paused` after successful and failed executions |

Raw bronze is intentionally **at-least-once**. Grouping by event identity provides a unique-event view, not
physical exactly-once ingestion or concurrency-safe production deduplication. Each run appends two replay batches;
it does not delete existing data. Legacy rows without raw text are excluded from exact-envelope verification.

Kusto `dynamic` can normalize strongly typed timestamp values and does not preserve the original JSON text [F101].
We therefore retain the original JSONL line in `raw_event:string` and also expose `payload:dynamic` for analytics.
The replay check compares retrieved raw text with the input line exactly, excluding only the line terminator.

## Operational constraints

The [experiment script](../infra/demo/Invoke-FabricExperiment.ps1) accepts at most 64 retained lab events.
It enforces a 15-minute working deadline, a 330-second publisher timeout and a separate suspension confirmation
window of up to five minutes. Its `finally` cleanup is not an independent cloud watchdog.

Fabric operations can be asynchronous [F100]. If publication is interrupted, keep the local item registry,
pending-create receipts and command journal: recovery requires a recorded accepted request and matching remote
metadata/definition. It never adopts an arbitrary same-name item. Definition recovery needs active capacity.
The scripted deployment and replay require no portal interaction.

Costs and subscription-wide limits belong in [chapter 13](./13-cost-control-and-operations.md);
network waivers and their revocation behavior belong in [chapter 19](./19-policy-exemption-experiment.md).

## Scope of this initial check

This clock-only skeleton does not validate the Eventstream/outbox ingestion path, batching latency, Profile M
or target-speed throughput, update policies, mirroring or Delta plan writes.
The subsequent [business lab](./21-business-lab.md) implements and verifies the causal simulators,
Eventstream ingestion, truth exclusion, real model decisions, token guards and independent cloud shutdown.
Use that chapter and the operating guide for current functionality rather than treating this initial test
as a project-wide feature inventory.

Secretless CI deployment, the full planning hierarchy, subscription budget enforcement and production-scale
throughput validation remain separate work.
Overage-off and surge settings still require check 27. The authoritative platform checks are in
[chapter 12](./12-elements-to-create.md#open-checks); passing this bounded test does not close them all.
