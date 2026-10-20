# Phase 0 — decision worksheet

> Our implementation baseline and remaining tenant facts. Chapter 15 §15.2 is the authoritative decision table.
>
> * Answers may be written in Italian or English. The design documents stay in English.
> * Every decision already has a recommended default, and the whole design is written with it. Ticking
>   "Accept the default" is a perfectly good answer.
> * Thirteen decisions close at the end of phase 0 (chapter 15 §15.3): D1, D4 to D10, and D16 to D20. Some of them
>   are needed **before** phase 0 starts, because the sandbox is built with them; the others wait for the evidence
>   that the spikes produce.

**Our decisions.** Giandoria is a demo, not a production platform. There is one Azure
environment, `demo`, one Fabric F4 capacity, and Sweden Central is the region for all new resources. Local
development and short-lived spike resources do not introduce separate `dev`, `stress` or sandbox environments.
Persist the generated dataset and run state across shutdowns; hibernation must never delete them.

---

## How to use this file

| Part | What it holds | When to fill it in |
|---|---|---|
| A | Facts about your tenant and accounts that the sandbox needs | Before phase 0 starts |
| B | Eight decisions needed, at least provisionally, to build the sandbox: D1, D4, D7, D16, D17, D18, D19, D20 | Before phase 0 starts |
| C | Five decisions that wait for the spikes: D5, D6, D8, D9, D10 | Think about them now; confirm at the end of phase 0 |
| D | Decisions of later phases | Nothing to do now |

For each decision: tick one box, add notes if you want, and leave the **Status** line to the closing session.

---

## A. Facts the sandbox needs

Identifiers such as tenant and subscription IDs are not secrets, but they are kept out of the documents: the phase-0
session stores them in an untracked `.env` file. Here, write only whether they are available and who owns them.

| # | Question | Why it matters | Your answer |
|---:|---|---|---|
| A1 | Which Azure subscription hosts the demo? | Use the context checked by the scripts | The subscription already configured in the untracked `.env`, used by the context-checking scripts |
| A2 | Do you have **Owner** on that subscription, or Contributor plus User Access Administrator? | The sandbox creates role assignments, a budget and a policy | |
| A3 | Can you create **app registrations and service principals** in Microsoft Entra ID? | Temporary identities stand in for the runtime, control and deploy identities (chapter 14 §14.4) | |
| A4 | Who is the **Fabric administrator** of the tenant, and are they available in weeks 1–2? | Checks 11 and 19 change tenant settings; check 27 may need a one-time look at overage | |
| A5 | Is Fabric enabled in the tenant, and may a new **F4** capacity be created in the chosen region? | The sandbox runs on F4 (chapter 14 §14.4) | |
| A6 | Which e-mail addresses receive **budget alerts**? | Budgets alert at 50% of actual cost, 80% of forecast and 100% of actual cost (chapter 12, GR-05) | |
| A7 | Are the required deployment tools available? | The spikes use them (chapter 11 §11.8) | Follow the infra guide prerequisites; `fab` is optional for the implemented REST path. Terraform is not required |
| A8 | GitHub account or organisation, and repository name, for the project | Phase 0 works locally with git; phase 1 needs the GitHub repository for OIDC (CI-01) | |
| A9 | Any company policy that forbids public endpoints, Global Standard model deployments or a region? | It may change D4 and D19 | Chapters 18 and 19 record reference constraints and waiver scope; validate effective policy and access in the configured deployment context |

**What the audit of the reference tenant found** (chapter 18). These are facts to confirm for your tenant, not
answers. West Europe is denied. Provisioned throughput for Azure OpenAI is denied; Global Standard is allowed. Public
network access to Storage is turned off unless a network security perimeter secures the account or an authorized
exemption applies. We use the account-scoped networking exemptions of D19. The
operator holds Owner on the subscription; the Entra and Fabric administrator roles of A3 and A4 may need to be activated
in Privileged Identity Management first (chapter 18 §18.8).

---

## B. Decisions needed before phase 0 starts

### D1 — Names (chapter 15 §15.4)

**Question.** What are the company, the universe and the cloud resources called?

| Option | Meaning |
|---|---|
| **Giandoria** | Company and demo name: Giandoria; resource prefix `giandoria`; environment `demo`; workspace `ws-giandoria-demo` |
| Other fictional names | Same rules: everything fictional, products named by category, never by a trademark |

* **Needed now:** the name prefix that the sandbox uses. **Final by:** the end of phase 0, before the bootstrap.
* **If it changes later:** after phase 1, a new universe name means a teardown and a rebuild.
* **Evidence from the spikes:** checks 13 and 14 shape the name pattern (suffixes), not the names.

- [ ] Accept the default
- [x] Other names: Giandoria replaces both former company and universe names.
- Notes: No existing shared infrastructure is renamed.
- Status: *Agreed*

### D4 — Region and models (chapter 15 §15.5)

**Question.** In which Azure region does everything run, and which models do the agents use?

| Element | Default | Alternatives |
|---|---|---|
| Region of Fabric and the core resources | **Sweden Central (`swedencentral`)** | No automatic regional fallback; report unavailable services or quota |
| Region of Foundry | **Sweden Central** | A different region requires a new owner decision |
| Foundry resource | **Shared Foundry first** | Dedicated economical deployments only when shared cost/quality/quota is inadequate |
| Deployment type | **Global Standard** | Data Zone (EU), if data residency matters more than price |
| Models | **Cost/quality/quota-tested aliases, pinned versions** | Historic model examples are not current bindings |

* **Needed now:** the sandbox region. **Final by:** the end of phase 0.
* **Evidence from the spikes:** at least 300k tokens per minute for `chat-medium` (BS-18); check 17 (the data
  agent's region and SKU); model availability per region.

- [ ] Accept the default
- [x] Other region or models: Sweden Central for every new resource.
- Notes: Sweden Central for new resources; shared models first. Global Standard does not guarantee Sweden-only
  processing. Bind aliases only after cost, quality and quota checks; newest generation is not the selection rule.
- Status: *Agreed region; adopted model strategy; actual bindings unverified*

### D7 — Infrastructure as code (chapter 15 §15.5)

**Question.** Which tools create and update the elements of chapter 12?

| Layer | Default | Alternative |
|---|---|---|
| Azure resources, including the Fabric capacity | **Bicep with Azure Verified Modules** | Terraform `azurerm` or `azapi` |
| Fabric workspace, roles and capacity assignment | **Idempotent `fab`/REST scripts** | Terraform only if later justified |
| Fabric item definitions | **`fabric-cicd`** | Targeted REST automation for supported APIs not covered by the library |
| Tenant settings and post-deploy wiring | **`fab` CLI** and the Fabric admin REST API | Scripted REST calls |

* **Needed now:** the sandbox is scripted with `az`, `fab` and Bicep. **Final by:** the end of phase 0.
* **Trade-off:** no Terraform state or second IaC language; explicit reconciliation checks are needed for workspace
  configuration. Each object has one managing tool; deletion is explicit and project-scoped.
* **Evidence from the spikes:** library/API coverage; checks 3, 15, 21, 24 and 28 remain open.

- [ ] Accept the default
- [ ] All Terraform
- [x] Other: Bicep/AVM + `fab`/REST + `fabric-cicd`; no initial Terraform dependency.
- Notes: Coverage gaps are reported, not silently skipped.
- Status: *Agreed*

### D16 — Cost limits (chapter 15 §15.7)

**Question.** How much may each environment and each run spend?

| Objective | Our direction |
|---|---|
| Whole subscription monthly budget | **EUR 500**, including other projects and shared/governance resources; a ceiling, not a spending target or a Giandoria-only allocation |
| Initial dataset and setup | Up to about **EUR 200** if necessary; less is preferable |
| Active demo day | A few tens of euros, generating and retaining useful data |
| Hibernation | Low recurring cost; retain data and restart state; no active capacity, compute or model calls |
| Necessary recurring infrastructure | Small fixed costs such as required private endpoints are acceptable; minimize the footprint and price it before deployment |
| Exact budgets, per-run/token limits and billing-currency conversion | Pricing, Defender baseline and measurements pending; bounded experiments are authorized, full runtime limits not yet enforced |

* **Needed before continuous business execution:** concrete alert budgets and enforceable per-run/token/time limits in the
  billing currency for the single `demo`. Do not create `dev` or `stress`.
* **Evidence from the spikes:** the price card calibrated with CM-01, CM-03 and CM-06.
* Re-estimate phase 0 and the retained initial dataset on F4 in Sweden Central before spending.

- [ ] Accept the default
- [ ] Other limits:
- Notes: EUR 500 monthly for the whole subscription; minimize actual spend and
  use on-demand resources. Required private endpoint costs are acceptable, not a mandate to privatize every service.
  Historic USD estimates are not approved budgets; Azure budget creation and per-run limits remain pending.
- Status: *Agreed objectives; numeric operational limits pending*

### D17 — Capacity strategy (chapter 15 §15.7)

**Question.** Which Fabric SKU runs, when, and under which billing rules?

| Element | Default | Alternatives |
|---|---|---|
| SKU | **One F4 in `demo`, including initial verification** | A larger SKU requires a new explicit owner approval |
| Billing | **Pay-as-you-go**, suspended whenever no lease is held | A reservation: cheaper per hour, but billed every hour |
| Overage | **Off** | On, with a 24-hour limit, for a demo that must never throttle |
| Eventhouse minimum consumption | **Unset**, so it can suspend when idle | Set: faster first queries, never suspends |

* **Needed now:** the sandbox SKU. **Final by:** the end of phase 0.
* **Evidence from the spikes:** CM-04, check 27; CM-08 confirms it in phases 1 and 5.

- [x] Accept the default
- [ ] Other:
- Notes: F4, single demo environment, pay-as-you-go, overage off, suspended when unused.
  Reduce load, fidelity or speed if needed; no automatic scaling above F4.
- Status: *Agreed*

### D18 — What the user interface may be used for (chapter 15 §15.7)

**Question.** Nothing is created through a graphical interface. Where exactly is the line?

| Use | Default |
|---|---|
| Viewing dashboards, reports, monitoring and the Capacity Metrics app | **Allowed** |
| Taking part in a run, such as approving a decision | **Allowed** |
| Designing dashboards, reports and rules visually in the stopped `demo`, then exporting them to Git and redeploying | **Allowed**, without creating a second environment |
| A one-time administrator check that overage is off, if no API exists (check 27) | **Allowed**, the only portal step |
| Creating or changing any element of chapter 12 in any other way | **Not allowed** |

* **Needed now:** it also governs the spikes. In phase 0, viewing results in the portal is fine; creating is not.

- [x] Accept the default
- [ ] Other:
- Notes: Visual authoring uses the single stopped demo, followed by export and scripted redeployment.
- Status: *Agreed*

### D19 — Networking (chapter 15 §15.8)

**Question.** Public endpoints or private networks?

| Option | Trade-off |
|---|---|
| **Default: public endpoints with Microsoft Entra ID** | No keys or secrets; enough for synthetic data; simplest and cheapest |
| Public endpoints, with Storage behind a network security perimeter | Needed where tenant policy turns off public access to Storage, as in the reference tenant (chapter 18 §18.10); check 29 tests it |
| Private networking | Virtual network, private endpoints and Fabric private links: more cost and complexity |

* **Needed now:** the sandbox uses public endpoints. **Revisit:** when an audience or a policy requires it (A9). In a
  tenant that turns off public access to Storage, the identity spike tests the perimeter (check 29).

- [x] Accept the default, with the reviewed resource-scoped network waivers of chapter 19
- [ ] Public endpoints, with Storage behind a network security perimeter
- [ ] Private networking
- Notes: Use public endpoints without private endpoints. Non-expiring Waivers cover only the registered network
  members on each Storage account, ACR and shared experimental Foundry. Preserve authentication, encryption,
  diagnostics and vulnerability management. Observe revocation without automatic recreation.
- Status: *Adopted; authenticated Storage access and anonymous denial verified. The authoritative rationale,
  exact waiver register and residual findings are in [chapter 19](../docs/19-policy-exemption-experiment.md).*

### D20 — Technology stack (chapter 15 §15.8)

**Question.** Which language and libraries build the simulators and services?

| Concern | Default |
|---|---|
| Language | **Python 3.13**, with project-local dependencies |
| Simulation, optimisation, forecasting | SimPy-style processes; OR-Tools and HiGHS; light statistical forecasting |
| Backward planning | Reverse-time simulation on SimPy, the method introduced in chapter 17 (chapter 17) |
| Events and agents | Event Hubs protocol to the Eventstream endpoints; Microsoft Agent Framework with Foundry models |
| Observability and packaging | OpenTelemetry to Application Insights; containers on Container Apps |

* **Needed now:** the spike scripts and the throw-away event generator are written in it. **Final by:** the end of
  phase 0; the speed criteria of phases 3 and 4 confirm it.
* **If it changes:** the contracts stay the same; libraries and skills change.

- [x] Accept the default
- [ ] Other:
- Notes: Python 3.13 for the application; PowerShell 7.4+ for
  infrastructure scripts; Bicep/AVM, `fab`, `fabric-cicd`. Add and pin specialist libraries when their phase begins.
- Status: *Agreed; performance validation remains open*

---

## C. Adopted implementation assumptions

We proceed with these choices. Experiments validate dependencies; they are not further approval gates.

| ID | Decision | Adopted choice | Evidence still required | Status |
|---|---|---|---|---|
| D5 | Deployment mode | Modular monolith; separate batch mode for backfill | CM-10 | Adopted |
| D6 | Ingestion | Persistent outbox → Eventstream → Eventhouse; no extra Event Hubs by default | Checks 1, 4, 5, 16 | Adopted |
| D8 | Workspace/truth | Reuse existing workspace; evaluation data excluded from agent access | Checks 1, 7; item roles alone do not isolate workspace members | Adopted |
| D9 | Automation identity | Dedicated secretless identity; do not recreate the existing workspace | Checks 11, 14; CI repository and permissions | Adopted |
| D10 | Latency | 10–30-second batches; optimize only after measurement | Check 4 | Adopted |

---

## D. Adopted later-stage assumptions

| ID | Decision | Validation point |
|---|---|---|
| D2 | Easter scenario, size/speed calibrated to F4; no promised year/hour | Simulation performance |
| D3 | Telemetry fidelity | Start of phase 3, week 11 |
| D12 | Where plan lines live | Start of phase 4, week 15 |
| D11 | Retained rules-based backfill and replay | First useful history |
| D14 | Few meaningful agents, introduced progressively | Cost/quality scenario suite |
| D15 | Controlled role-scoped tools; no autonomous Fabric queries initially | Agent access tests |
| D13 | Simple Lab Control approval after automatic flow works | First interactive rehearsal |

---

## Ready to start phase 0?

- [ ] Part A answered, including the Fabric administrator (A4)
- [x] D1-D20 recorded as decisions or adopted implementation assumptions
- [x] Part C implementation choices adopted; technical dependencies remain explicit
- [ ] A Fabric administrator slot booked for the identity spike in week 2
