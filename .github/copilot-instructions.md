# Giandoria — instructions for every session

Giandoria is an Italian chocolate maker whose suppliers, factory, planning, channels, territory, customers and
LLM agents are modelled on an accelerated, stoppable simulation clock. Events stream to Microsoft Fabric.

## Where the knowledge lives

The design in [docs/](../docs/README.md) is the source of truth. Read it; do not restate it here or in code comments.

* Start with [docs/README.md](../docs/README.md), then chapter 01 (mental model, glossary §1.14, reading guide §1.15).
* [Chapter 12](../docs/12-elements-to-create.md): every element to create, with IDs (GR-05, CI-01…) and the 29 open
  checks (§12.16).
* [Chapter 14](../docs/14-implementation-plan.md): the phases, their exit criteria and costs.
* [Chapter 15](../docs/15-open-decisions.md): decisions D1–D20 and the decision log (§15.2, rules in §15.10).
* [Chapter 17](../docs/17-reverse-time-simulation.md): reverse-time simulation, my independently developed method
  for finite-capacity backward planning. Write that chapter in my first-person voice; preserve the origin and
  prior-art caveats without describing me as "the owner".
* [Chapter 18](../docs/18-tenant-governance.md): what the reference tenant's policies deny, change and add, the
  roles and Privileged Identity Management, model quota, and the shared Foundry resource built by
  [infra/shared-foundry](../infra/shared-foundry/README.md).
* [decisions/phase-0-decisions.md](../decisions/phase-0-decisions.md): adopted assumptions and remaining tenant facts.

If the code and the design disagree, stop and ask; then update the design in the same change.

## Language and naming

* The owner chats in Italian. Every file, code, comment, commit message and document is in **English**.
* In narrative prose, describe Giandoria as an established Italian chocolate maker. Explain simulation and
  generated-data boundaries only where they help readers understand scope or provenance. Never name real chocolate
  makers, brands or products. Name products by category and use the campaign partners in chapter 02.

## Everything as code

* Azure resources, including the Fabric capacity: Bicep with Azure Verified Modules. Fabric workspace, roles and
  settings: idempotent `fab`/REST scripts. Item definitions: `fabric-cicd`, with targeted REST for supported gaps.
  No Terraform dependency or state. One managing tool per object; explicit, project-scoped deletion. (D7)
* One demo only: prefix `giandoria`, environment `demo`, F4, Sweden Central for all new resources. Local
  development and isolated spike resources do not create extra cloud environments. No automatic SKU/region fallback.
* D18 allows viewing and participation, visual authoring in the stopped demo followed by export to Git and
  redeployment, and a recorded administrator check of overage if no API exists. Other creation/change is code-only.
* The Azure and Fabric MCP servers are for reading, documentation, schemas, pricing, quota, validation and
  diagnostics. Do not use them to create durable resources; throw-away spike resources are created by scripts.
* Prefer repeatable Azure CLI/PowerShell scripts, including REST calls where needed, over portal mutations.
  If CLI authentication or consent is missing, ask the owner to complete it rather than switching to browser writes.
  Declare supported resource descriptions in Bicep too; share their source with operational publication to avoid drift.

## Cost safety — always

* Deployment and bounded experiments in the existing demo context are authorized without repeated confirmations.
  State expected cost, enforce short execution limits and suspend F4 in cleanup. New regions, larger SKUs,
  destructive actions or broader privileges require a separate decision.
* A script that resumes Fabric must suspend it in failure cleanup. Successful lab Start may hand off to a verified
  cloud shutdown schedule with retained session/deadline state; other experiment scripts suspend before exit.
* Pay-as-you-go only: F4, no reservations, overage off. Region Sweden Central (D4, D17); West Europe is denied.
* Preserve datasets and restart state when hibernating. Our targets are approximately EUR 200 for the
  initial useful dataset, a few tens of euros per active demo day and low idle costs. Exact D16 operational limits
  still need pricing and implementation; do not confuse adopted guardrail principles with enforced money limits.
* The whole subscription has a EUR 500 monthly ceiling, not a spending target or a Giandoria-only allowance.
  Include shared resources/other projects, handle USD billing versus EUR explicitly and minimize on-demand spend.
  Required private endpoints/small fixed costs are acceptable after pricing; a budget alert is not an automatic stop.
* Prefer public Entra-authenticated endpoints. We use non-expiring, resource-scoped network waivers on
  Storage, ACR and shared experimental Foundry for only the members in
  [the exemption register](../docs/19-policy-exemption-experiment.md). Do not broaden or automatically recreate
  exemptions, modify policy assignments, use exclusion tags, or exempt authentication/vulnerability controls.
  If governance revokes the waiver, report it and revisit perimeter/private access instead of evading the change.
* The tenant bills Defender plans per subscription, also while the lab is hibernated. Include them in cost
  statements (chapter 18 §18.6).
* Never change or delete resources the project did not create, such as the tenant's governance workspace.
* End every session by reporting: capacity state, running apps or jobs, cost so far against the budget (D16).

## Rules of the universe

* Two clocks. Business logic never reads the wall clock: it uses sim time from Chronos (`sim_ts`). `wall_ts` is
  only for operations. When the lab is stopped, sim time does not advance (chapter 07).
* The reverse clock of the planning engine stays inside one engine call; every date it outputs is sim time
  (chapter 17 §17.2, §17.8).
* Runs are deterministic for a given scenario and seed. Use the seeded random streams, never global randomness.
* Truth (`kqldb_truth`, `lh_evaluation`) is for evaluation only. No agent and no data agent can reach it; agents see
  only what their role may observe (chapter 07 §7.9, chapter 09, chapter 10 §10.11).

## Security

* No secrets in files or commits. Use Microsoft Entra ID tokens and managed identities.
* Tenant, subscription and object IDs go in an untracked `.env`, never in the docs.

## Writing documentation

* Optimize public documentation for reader value per unit of reading effort, not completeness of our work diary.
  Keep a detail only if it helps understand the design, make a decision, reproduce a task or resolve a known issue.
* Start with a short summary of current behavior, outcome and limits. Link to focused detail for readers who need it;
  each detail must pass the same usefulness test. Do not hide an execution diary in an appendix or collapsible block.
* Keep one authoritative home for each topic: overview, design/decisions, or operational runbook. Link instead of
  repeating inventories, commands, results or caveats. Update the current explanation rather than appending updates.
* Development retries, setting corrections, per-attempt timestamps, raw outputs, transient row counts, test totals
  and personal billing snapshots stay in ignored `.local` records or session files, not public Markdown.
  Preserve command journals and deployment evidence; do not duplicate them into a second narrative log.
* Promote only reusable conclusions from experiments: what was verified, relevant version/date, scope and limits.
  Publish troubleshooting as a symptom/condition and action only when useful to future operators, not as our story.
  Keep material unresolved risks visible; brevity must not erase safety, cost, ownership or reproducibility constraints.
* Write decisions as current collaborative choices ("we decided", "we use"), without conversational history,
  approval attribution or dates of requests. Keep dates only for relevant evidence freshness, citations or real history.
* Chapter 17 uses first person ("I", "my") for the origin and explanation of my planning method.
* Record all operational commands and API calls through the command journal, including failures and exit/status
  codes, locally and separately from public documentation. Never record secrets, tokens, authorization headers
  or raw authentication responses.
* The recommended D2-D16 choices are adopted assumptions, not pending approval; open platform checks stay open.
  Prefer the shared Foundry first; model/alias selection follows measured cost, quality and available quota.
* Prose lines at most 118 characters; CRLF line endings; no BOM.
* Values without a source carry a marker: *(estimate)*, *(assumption)* or *(verify)*.
* Cite sources as [M#], [P#], [F#]; add new ones to [chapter 16](../docs/16-references.md).
* Diagrams in Mermaid; keep labels quoted when they contain punctuation.
* When a check or decision is answered, update its authoritative status and affected explanations; link to evidence
  without copying the execution history. Before delivery, remove duplication, stale snapshots and incidental detail.

## Build and test

Python 3.13 is the agreed runtime (D20); specialist dependencies are added only when needed. Local foundation:

* Install in a project virtual environment: `python -m venv .venv`, then `.venv\Scripts\python -m pip install -e .`.
* Tests: `.venv\Scripts\python -m unittest discover -s tests -v`.
* Local commands and limitations are documented in [docs/README.md](../docs/README.md).
* Local hibernation persists state only; it never claims to suspend cloud resources.

The shared Foundry resource has its own commands (details in
[infra/shared-foundry](../infra/shared-foundry/README.md)):

* Configuration: copy `.env.example` to `.env` at the repository root (untracked) and fill it in; the scripts load it.
* Check without changing anything: `infra/shared-foundry/scripts/Deploy-SharedFoundry.ps1 -WhatIfOnly`.
* Deploy (billable per use; confirm first): the same script without `-WhatIfOnly`.
* Remove: `infra/shared-foundry/scripts/Remove-SharedFoundry.ps1`, which also purges the soft-deleted account.
