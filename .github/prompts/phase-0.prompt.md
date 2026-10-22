---
name: phase-0
description: "Run phase 0 of Giandoria (throw-away sandbox spikes for the 29 open checks, first cost measurements, decisions D1, D4-D10, D16-D20). Use when starting phase 0, running a spike (ingestion, lake, identity, experiences, cost, tooling) or closing phase 0."
argument-hint: "kickoff | ingestion | lake | identity | experiences | cost | tooling | close-out"
agent: agent
---

# Phase 0 — sandbox spikes

You are running **phase 0** of Giandoria, as defined in
[chapter 14 §14.4](../../docs/14-implementation-plan.md). The step to run is given in the argument: `kickoff`, one
spike name, or `close-out`. With no argument, read the results log and propose the next step.

Phase 0 starts locally, then uses isolated throw-away items inside the single `demo`, one F4 in Sweden Central.
There is no separate sandbox environment or capacity. Never delete the retained demo dataset on spike cleanup.
Useful scripts become the seed of the phase-1 bootstrap. D7 uses Bicep/AVM + `fab`/REST + `fabric-cicd`, not Terraform.

## Always read first

1. [docs/README.md](../../docs/README.md) and chapter 01 §1.13–§1.15.
2. [Chapter 14 §14.4](../../docs/14-implementation-plan.md): the spikes, exit criteria, cost and risks.
3. [Chapter 12 §12.16](../../docs/12-elements-to-create.md): the 29 open checks.
4. [Chapter 15](../../docs/15-open-decisions.md): D1, D4–D10, D16–D20 and the recording rules of §15.10.
5. [Chapter 13 §13.12](../../docs/13-cost-control-and-operations.md): the cost measurements CM-01 to CM-10.
6. [decisions/phase-0-decisions.md](../../decisions/phase-0-decisions.md): the owner's answers.
7. [Chapter 18 §18.10–§18.13](../../docs/18-tenant-governance.md): what the tenant's policies deny or change, their
   consequences, the audit commands and the open points.
8. `.local\spikes\results.jsonl`, if it exists: private evidence for already answered checks.

Only read the sections you need beyond these; the chapters are long.

## Spikes

| Spike | Week | Checks | Cost measurements |
|---|---|---|---|
| `ingestion` | 1 | 1, 2, 3, 4, 5, 21 | — |
| `lake` | 1 | 6, 7, 18, 19 | — |
| `identity` | 2 | 8–14, 20, 23, 26, 29 | — |
| `experiences` | 2 | 15, 17, 22, 24 | — |
| `cost` | 1–3 | 16, 27, 28 | CM-01, CM-03, CM-04, CM-07, CM-09 |
| `tooling` | 2–3 | 25 | — |

Design checks 1, 5, 7 and 19 come first: if one fails, a fallback changes the design before anything else is built.
Check 29 joins them in tenants that turn off public access to Storage (chapter 18 §18.10).
Checks 11 and 19 need the Fabric administrator; check 27 may too.

## Step: kickoff

1. Check the worksheet. Record the agreed decisions and unresolved facts. Missing cloud prerequisites block cloud
   execution, not non-billable local foundation development. Part C defaults remain provisional.
2. Read-only checks of the tools and logins: `az version`, `az account show`, `bicep --version` (or
   `az bicep version`), `fab --version`, `fab auth status`, `gh auth status`, `python --version`.
   Report what is missing and offer to install it.
3. If the folder is not a git repository, propose `git init` and wait for confirmation. Add a `.gitignore` that
   covers at least `.env`, local run data, Python caches and virtual environments.
4. Create an untracked `.env` for the tenant ID, subscription ID, region and the name prefix (D1, D4). Ask the owner
   for the values; never write them anywhere else.
5. Create the working structure:
   * `spikes/` for reusable scripts only; keep throw-away diagnostics and execution records in ignored `.local`;
   * Demo bootstrap Bicep for the single F4 and approved spending guardrails; do not add a sandbox capacity.
     D16 has EUR objectives, not finalized operational budgets; agree billing-currency limits before deployment;
   * `spikes/sandbox/` scripts to resume and suspend the capacity, where the resume script suspends again on exit or
     failure;
   * `.local\spikes\results.jsonl`, the private evidence log: check/measurement ID, answer, relevant date/version,
     evidence location, documented/verified status and design impact. Reuse existing journals/reports for raw detail.
6. Validate the Bicep (`az bicep build`, then `az deployment sub what-if`). State the expected cost, ask for
   confirmation, then deploy, and confirm the capacity is suspended.

## Step: one spike

1. **Documents first.** For each check of the spike, look for the answer in Microsoft Learn and the Fabric
   documentation (Fabric MCP docs and item definitions, Azure MCP documentation, `bicepschema`, quota and pricing
   tools). Record documented answers with their source, marked *documented*.
2. **Plan the experiment** for what remains: the resources, the script, what is measured, how long the capacity is
   resumed and the expected cost. Present the plan and **wait for confirmation**.
3. **Run it** with scripts only (`az`, `fab`, Bicep, `fabric-cicd`, Python, REST). No portal clicks to create anything
   (D18); viewing results in the portal is fine. The MCP servers do not create resources.
4. **Suspend** the capacity as soon as the measurement ends, also on failure.
5. **Record** each answer and evidence location locally, marked *verified*. Keep command outputs, retries,
   query results and billing readings out of public Markdown; preserve the redacted command journal.
6. If an answer breaks the design, describe the fallback from chapter 12 §12.16 and the chapters it touches. Do not
   edit the design yet; close-out does it.

## Step: close-out

1. Check the exit criteria of chapter 14 §14.4: every check answered and dated; fallbacks chosen; price card RT-02
   calibrated; D1, D4–D10 and D16–D20 ready to close.
2. For each of these decisions, propose *Agreed* or *Revised* with the evidence, and wait for the owner.
3. Update authoritative decision/check status, the price card and affected explanations as chapter 15 §15.10
   requires. Publish concise conclusions, scope and material limits, with version/date only where useful.
   Link to one focused explanation; do not publish the local results log or a development timeline.
   Follow the writing rules in `.github/copilot-instructions.md`.
4. Add the build and test commands chosen in phase 0 to `.github/copilot-instructions.md`.
5. List the scripts worth keeping for the phase-1 bootstrap.
6. Ask for confirmation, then remove only the owned temporary spike items and identities. Preserve the single
   demo's retained datasets and shared infrastructure. Report total cost against the approved guardrails.

## Rules for every step

* Before creating, resuming or scaling anything billable: state the cost and wait for confirmation.
* Respect the tenant's rules (chapter 18): denied regions and SKUs, and settings that policy changes on the fly. A
  `RequestDisallowedByPolicy` error is a fact to record, not something to work around.
* Never leave the capacity running. End with capacity/app state and cost against confirmed D16 limits. If state or
  billing was not queried, say so; local hibernation is not cloud suspension.
* Write Giandoria as an established Italian company; all files are in English; the owner chats in Italian.
  Never name real chocolate makers, brands or products; use product categories and the partners in chapter 02.
* Prefer small, readable scripts that the bootstrap can reuse over clever one-off commands.
* Apply the reader-value test to summaries and details alike. Keep only information needed to understand,
  decide, reproduce or troubleshoot; local evidence retention does not imply public documentation.
