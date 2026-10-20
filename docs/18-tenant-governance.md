# 18 — Tenant governance: what the reference tenant allows

> The reference tenant, where Giandoria is built first, is a Microsoft-managed tenant for experimentation. Its
> governing organisation applies Azure Policy from the tenant root, switches on Microsoft Defender for Cloud and runs
> delegated automation. This chapter records what those rules deny, change and add, what they cost, and how they
> change the design. Current project-specific exceptions and verification are recorded in chapter 19.
>
> Other tenants may have no such rules, or different ones. The design and the templates work in both cases; the
> consequences of §18.10 apply only where the same rules exist. Rules change without notice: §18.12 shows how to
> repeat the audit.
>
> This chapter explains:
>
> * the tenant, the audit and the one rule the project follows (§18.1)
> * the policy assignments and what their effects do (§18.2)
> * what is denied (§18.3), changed (§18.4) and added (§18.5, §18.6)
> * delegated management, locks, roles and Privileged Identity Management (§18.7, §18.8)
> * model quota (§18.9)
> * the consequences for Giandoria, and the options for storage without public endpoints (§18.10)
> * the shared Foundry resource (§18.11)
> * how to repeat the audit, and what is still open (§18.12, §18.13)

---

## 18.1 The tenant and the audit

**Our scope.** One Giandoria `demo`, one F4, Sweden Central for all new resources. Prefer public
Entra-authenticated endpoints. We adopted the resource-scoped, non-expiring network Waivers of
[chapter 19](./19-policy-exemption-experiment.md) for Storage, ACR and shared experimental Foundry.
Ordinary Storage public access still conflicts with the Modify policy unless a valid exemption applies.
Perimeter/private access remains the fallback if tenant governance rejects or revokes the exception.

**Audit boundary.** The inherited-governance inventory below describes the baseline, not a live deployment or
compliance inventory. Project resources now exist; chapter 19 distinguishes current findings, exemptions and
data-plane proof. The shared Foundry retains its service configuration; only its registered network waiver changes.

| Item | In the reference tenant |
|---|---|
| Tenant | Managed by Microsoft for experimentation. Its IDs live only in the untracked `.env` file |
| Subscriptions | One. It hosts the shared Foundry resource (§18.11) and, later, the Giandoria environments |
| Governance | Azure Policy assigned at the tenant root management group; Defender for Cloud plans switched on by policy; one delegation to the governing organisation's automation (§18.7) |
| The owner's rights | Owner on the subscription; Owner and User Access Administrator at the tenant root; Global Reader in Microsoft Entra ID (§18.8) |
| Audit | Read-only, with the Azure CLI and Azure Resource Manager REST calls, on 18 October 2026 |

**The rule: do not change inherited governance.** Never change or delete a policy assignment, use exclusion tags,
or exempt authentication/protection controls. The agreed exceptions are the narrowly scoped network
Waivers in chapter 19, created through Azure's exemption authorization checks [F97]. They are not equivalent
network isolation; synthetic data is our reason for accepting the exposure. Tenant governance can revoke it.
Do not evade revocation or automatically recreate removed exemptions.

**What this chapter publishes.** Rules are described by their effect and their target. Tenant, subscription and
object IDs, assignment names and the names of the governing organisation's internal tools stay out of the
repository.

---

## 18.2 Policy assignments at a glance

Nine assignments apply to the subscription. Six are inherited from the tenant root management group. Defender for
Cloud created the other three at subscription scope when the plans of §18.6 were switched on.

| Assignment | Scope | Policies | Effects |
|---|---|---:|---|
| Security baseline | Tenant root | 216 | AuditIfNotExists 105, Audit 98, Disabled 13 |
| Deny set | Tenant root | 11 | Deny (§18.3) |
| Audit set | Tenant root | 44 | AuditIfNotExists 35, Audit 7, Disabled 2 |
| Deploy-and-modify set | Tenant root | 48 | DeployIfNotExists 34, Modify 13, Append 1 (§18.4 to §18.6) |
| Classic resources | Tenant root | 1 | Deny |
| West Europe | Tenant root | 1 | Deny |
| Defender for SQL servers, SQL on machines and open-source databases | Subscription | 11 | DeployIfNotExists. Giandoria uses none of these services |

**What the effects do** [F92]:

| Effect | When it acts | What you see |
|---|---|---|
| Deny | At the request | The deployment fails with `RequestDisallowedByPolicy`; the error names the assignment |
| Modify | During creation or update, before the resource is stored | Azure stores a value that differs from the template. What-if and Terraform plans show a difference on every run, unless the template already sets the enforced value |
| Append | During creation or update | A field is added, for example IP tags on a public IP address |
| DeployIfNotExists | After a successful creation or update, with a delay | A related resource appears that no template declared, such as a diagnostic setting or a Defender plan. Deployment stacks and Terraform do not track it. Resources that already exist need a remediation task |
| Audit, AuditIfNotExists | At evaluation | A compliance result only; nothing is blocked |
| Disabled | Never | — |

* **Compliance at the audit.** Eleven audit results were non-compliant, all on the subscription itself: security
  contacts and alert e-mails, account hygiene, the export of the activity log, and two Defender settings. They block
  nothing and belong to the subscription's owner, not to the project.
* **The CLI shows only part of the picture.** `az policy assignment list` returns only the three assignments made at
  subscription scope, even with `--disable-scope-strict-match`. The REST call of §18.12 returns all nine.

---

## 18.3 What is denied

| Rule | Denies | Effect on Giandoria |
|---|---|---|
| Region | Every resource in West Europe | West Europe leaves the alternatives of decision D4. Italy North and Sweden Central are allowed |
| Classic resources (two rules) | Classic compute, storage and network resource types | None used |
| Virtual machine sizes (three rules) | GPU sizes (NC, ND, NV), HPC sizes (HB, HC) and the M series, for machines and scale sets | None used: the apps run on the Container Apps consumption plan |
| Kubernetes and scale sets | AKS clusters with more than 10 agent pools; scale sets with more than 10 instances | None used |
| Provisioned throughput | Model deployments with the SKU `ProvisionedManaged`, which is regional provisioned throughput | None used. GR-04 stays, because global and data-zone provisioned deployments are not denied (§18.10) |
| Microsoft Sentinel | Commitment tiers above 100 GB per day | None used |
| Azure SQL | SQL Database servers and SQL managed instances without Microsoft Entra-only authentication | None used. Fabric SQL databases are Fabric items, not Azure resources |
| Managed HSM | Managed HSM pools with purge protection enabled | None used |

A denied request fails at once and creates nothing. The deploy script of the shared Foundry checks the region and
the deployment type before it calls Azure, so the two rules that could matter fail early with a clear message.

---

## 18.4 What is changed or added on the fly

Modify rules change a request before Azure stores it [F92]; the Append rule adds a field.

| Target | Change | Effect on Giandoria |
|---|---|---|
| Foundry resources and other Cognitive Services accounts | Local authentication (keys) disabled | Matches the design: every call uses Microsoft Entra ID. The templates set it too, so what-if stays clean |
| Storage accounts | Shared-key access disabled; anonymous access to containers disabled | Matches AZ-03 and BS-17. Tools must sign in with Entra ID (§18.10) |
| Cosmos DB, Event Hubs, Service Bus | Local authentication disabled | Event Hubs is used only by ingestion option B (AZ-18), which is keyless by design |
| Storage accounts, key vaults, Cosmos DB accounts, SQL servers | Public network access set to `Disabled`, unless it is `SecuredByPerimeter` | **Conflicts with decision D19** for AZ-03 and BS-17 (§18.10) |
| Hub-based Foundry (Azure Machine Learning workspaces) | Public network access disabled | Not used. A Foundry resource is a Cognitive Services account, which this rule does not target, so it keeps its public endpoint |
| Virtual machines (two rules) | A managed identity for guest configuration | None used |
| Public IP addresses (Append) | Service-tag IP tags | None used: Container Apps manages its own addresses |

**`SecuredByPerimeter`** means that a network security perimeter governs the resource's public access [F90]. A
perimeter is generally available in all public regions. Storage, Key Vault, Event Hubs, Service Bus, Azure Monitor,
Azure AI Search and Foundry can join one; Cosmos DB, SQL Database and App Configuration are in preview. Inbound rules
admit IP prefixes or whole subscriptions, outbound rules admit domain names, and traffic through private endpoints
is always allowed. A perimeter starts in Transition mode, which logs and falls back to the resource's own settings,
and moves to Enforced mode once the logs show that every caller is covered.

---

## 18.5 Diagnostic settings that policy adds

DeployIfNotExists rules give these resources a diagnostic setting that sends **all logs and all metrics** to a
governance Log Analytics workspace:

* Foundry resources and Foundry projects, hub-based Foundry and Azure Machine Learning workspaces;
* Logic Apps (both kinds), function apps and Synapse workspaces;
* nine more services for security logging: Batch, Data Factory, Azure Cache for Redis (both tiers), Service Bus,
  Stream Analytics, Front Door, IoT Hub and Data Share.

Container Apps, Container Registry, Storage and Event Hubs are **not** covered.

| Fact | Value |
|---|---|
| Where the workspace lives | In this subscription, in a resource group that the policy created, in **West US 2** |
| Pricing and retention | Pay per GB; 30 days |
| Daily cap | None |
| When the setting appears | About ten minutes after the resource is created: eleven on the shared Foundry (§18.11). Calls made before it, or in its first minutes, leave no logs; their metrics still arrive |
| Logs | Of the five log categories (Audit, RequestResponse, AzureOpenAIRequestUsage, Trace, ManagedNetworkEvent), a chat call writes two rows of about 0.9 KB each, about seven minutes later. *RequestResponse* holds the caller's Entra object ID, the caller's IP address with the last octet masked, the operation, the deployment, model and version, prompt and completion tokens, request and response sizes, duration and HTTP status. *AzureOpenAIRequestUsage* adds cached tokens and the times to the first and the last token. **No prompt or completion text** |
| Metrics | 7–11 minutes after the minute they cover; 4–12 KB for each minute with calls. Totals for the whole resource: the deployment and the model are dropped, while the resource's own metrics in Azure Monitor keep them |
| Public ingestion and query | Enabled |
| Price | The first 5 GB a month free, then $2.30 per GB ingested; $0.10 per GB a month for longer retention [F3][F61]. Whether the free 5 GB are shared with Giandoria's own workspaces is *(verify)* |

* **The logs leave the European Union.** For Foundry they hold request metadata, not prompts or completions (table
  above). The caller's object ID and partial IP address are personal data when the caller is a person; Giandoria's
  services call with managed identities. With synthetic data this is acceptable; a reuse with real data must take it
  into account.
* **The cost is billed here.** At Giandoria volumes it is close to nothing: about 10,000 model calls in a demo run
  *(estimate)* at about 1.8 KB each make about 18 MB, plus less than 1 MB of metrics an hour.
* **No second copy.** AZ-17 still sends the Container Apps environment to AZ-01, because no policy covers it. It
  does not add a second setting for Foundry, which would pay twice for the same logs (§18.10).
* **Hands off.** The workspace, its resource group and the settings that the policy creates are not the project's.
  No Giandoria script deletes or changes them, and the safety net never sees them, because it selects resources by
  tag (chapter 12 §12.15).

---

## 18.6 Microsoft Defender for Cloud

DeployIfNotExists rules switch on twelve Defender plans at subscription level. They were switched on on 16 and
17 October 2026, so the 30-day trials end around **15–16 November 2026** [F89]. List prices apply after that.

| Plan | State and settings | List price (October 2026) [F3] | What it bills in a Giandoria environment |
|---|---|---|---|
| Defender CSPM | Standard; serverless and API posture on | $0.007 per hour ≈ $5.11 per billable resource a month | Storage accounts with containers (AZ-03, BS-17); Container Apps and container instances, billable since 1 July 2026 (AZ-06 to AZ-12) [F93]. How apps scaled to zero and jobs are counted is *(verify)* |
| Storage | Standard, per account; malware scanning on upload (up to 10,000 GB per account a month); sensitive-data discovery on | ≈ $9.78 per account a month; $0.15 per GB scanned; transactions beyond an included amount *(verify)* | AZ-03 and BS-17 |
| AI services | Standard; prompt evidence on; sharing with Microsoft Purview on; model scanning off | $0.80 per million text tokens | Every model call. Image and audio tokens are not scanned [F88] |
| Resource Manager | Standard, per subscription | ≈ $5 per subscription a month | The subscription, with or without Giandoria |
| Containers | Standard; registry vulnerability assessment and the sensor on | $0.29 per image scanned beyond an allowance *(verify)*; per vCore-hour for clusters | A few images per release (AZ-04); no clusters |
| Key Vault | Standard, per vault | ≈ $0.25 per vault a month | None: Giandoria has no key vault |
| Servers (plan 2), App Service | Standard | $0.02 per server or app an hour | None |
| SQL, SQL on machines, open-source databases, Cosmos DB | Standard | Per instance, per node or per throughput | None |
| Kubernetes and registries (older plans), DNS, APIs | Free | — | — |

**What it adds to Giandoria** *(estimate)*:

The following is a full-build reference estimate, not a minimum required footprint. Keep the initial demo smaller
where possible. Storage/Defender charges persist while compute is stopped, and existing subscription-wide charges
must not be counted again as if a new subscription were being created. Current billed costs still need verification.
Sweden Central applies to project-controlled deployments; governance can still send logs to West US 2 (§18.5).

| Item | Per environment |
|---|---:|
| Storage plan, two accounts | ≈ $19.6 a month |
| CSPM, two storage accounts | ≈ $10.2 a month |
| CSPM, zero to seven container apps and jobs | ≈ $0–36 a month |
| **At rest, total** | **≈ $30–65 a month**, against ≈ $7–10 for an idle month in chapter 13 §13.3 |
| AI services, a `dev` run of about 5 million tokens | ≈ $4 a run |
| AI services, a `demo` run of about 30 million tokens | ≈ $24 a run |
| Malware scanning of snapshots and decision records, 1–5 GB a run | ≈ $0.15–0.75 a run |

* **Defender for AI scans text only.** Image generation is not scanned, and not billed by this plan [F88].
* **Prompt evidence and Purview.** Alerts keep the suspicious part of a prompt and of the response, and prompts and
  responses are shared with Microsoft Purview. Harmless with synthetic data; a reuse with real data must take it
  into account.
* **The shared Foundry adds no fixed Defender cost.** Foundry resources are not CSPM billable resources [F93]; only
  their text tokens are billed by the AI plan.

---

## 18.7 Delegated management, locks and deny assignments

* **Delegated management.** One Azure Lighthouse delegation gives an automation identity of the governing
  organisation, in a Microsoft-managed tenant, the **Contributor** role on the subscription. It creates and remediates
  what the policies require, such as the governance resource group and workspace of §18.5.
* **Resource locks:** none. **Deny assignments:** none.
* **What it means.** Resources that the project did not create may appear in the subscription at any time. Teardown
  scripts delete only what their own stack or tags identify; the shared Foundry's removal script deletes only its own
  resource group (§18.11).

---

## 18.8 Roles and Privileged Identity Management

The owner's roles at the audit:

| Role | Scope | Assignment |
|---|---|---|
| Owner | Subscription | Permanent, active |
| Owner | Tenant root management group | Permanent, active |
| User Access Administrator | Tenant root management group | Permanent, active |
| Global Reader | Microsoft Entra ID | Active |
| Roles eligible through Privileged Identity Management | Microsoft Entra ID, Fabric | Not readable with the current rights *(verify with the owner)* |

What the work needs, and from whom:

| Task | Role needed | Status in the reference tenant |
|---|---|---|
| Deploy the shared Foundry (§18.11) | Owner on the subscription, or Contributor plus Role Based Access Control Administrator | Available |
| Bootstrap, Azure part: provider registrations, resource groups, identities, custom role, role assignments, ops storage, quota checks (BS-10 to BS-12, BS-15 to BS-18) and the guardrails (GR-01 to GR-12) | Owner on the subscription | Available |
| Bootstrap: security groups and their members (BS-01 to BS-05, BS-14) | Groups Administrator, unless users may create security groups *(verify)* | Ask the owner (phase-0 question A3) |
| Bootstrap: app registrations, service principals, federated credentials, app-role assignments (BS-06, BS-07, BS-13) | Application Administrator or Cloud Application Administrator, unless users may register applications *(verify)* | Ask the owner (A3) |
| Fabric tenant settings (BS-08); the workspace in workspace option B (BS-20) | Fabric Administrator | Ask the owner (A4) |
| Admin consent to Microsoft Graph permissions | Not needed: CI never queries Microsoft Graph, and the Lab Control API exposes only its own app roles | — |

Activating an eligible role is a short personal step, with a justification and possibly multi-factor
authentication, and the role stays active for a limited time *(verify)*. It happens right before the bootstrap and
is not part of any script.

---

## 18.9 Model quota

| Model (Global Standard) | Limit at the audit | Used by |
|---|---:|---|
| gpt-6-astra, gpt-6.1-sol, gpt-5.6-terra, gpt-6-luna | 250 units each (250K tokens per minute) | The shared Foundry, which takes all of it (§18.11) |
| gpt-5-mini | 1,000 units (1M tokens per minute) | Giandoria's default `chat-medium` (decision D4) |
| gpt-5-nano | 5,000 units (5M tokens per minute) | Giandoria's default `chat-small` (D4) |
| Image models | 2–6 requests per minute each | The shared Foundry, which takes all of it; for FLUX, the Sweden Central pool only |

* **Units.** One unit of a chat model allows 1,000 tokens and one request per minute; one unit of an image model is
  one request per minute [F84].
* **One pool per subscription.** The Usages API reports the Global Standard limits under a scope named *Global*.
  After the shared Foundry took its capacity in Sweden Central, East US 2, Italy North and West US 3 reported the
  same capacity as used, for the GPT and MAI models alike: one pool serves every region of the subscription. The
  quota page still describes quota per region and subscription [F84]. The FLUX models have regional pools instead:
  their usage counted only in Sweden Central.
* **"The maximum" means all of it.** Once the shared Foundry takes the whole pool of a model, no other account in the
  subscription can deploy that model, in any region. The deploy script can leave a share free (`-QuotaShare`), and
  more quota can be requested [F84].
* **Giandoria's defaults are not affected.** gpt-5-mini has 1,000K tokens per minute, more than the ≥ 300K that
  `chat-medium` needs at S = 8,760 (chapter 09 §9.7). In this subscription, on the audit date, the quota part of
  BS-18 passes for both default models.
* **A shared model as `chat-medium`** would offer 250K tokens per minute, below 300K. Agent-heavy runs would then
  need a lower speed, about S = 7,300 *(derivation: tokens per wall minute grow with S)*, or roles spread over two
  model families, or more quota.

---

## 18.10 Consequences for Giandoria

| # | Element | Rule | Consequence | Updated in |
|---:|---|---|---|---|
| 1 | Decision D4: region | West Europe denied | Sweden Central selected by the owner; no regional fallback without approval | Chapter 15 D4; chapter 11 §11.7 |
| 2 | D4: models; AZ-13 to AZ-15; BS-18 | One quota pool per model; the shared Foundry takes all of its models' quota | The default models keep their own pools (§18.9). Using a shared model means calling the shared deployment, not deploying it again | Chapter 12 AZ-13; chapter 15 D4 |
| 3 | Role for model calls | Foundry guidance on roles [F85] | **Foundry User** replaces *Cognitive Services OpenAI User*. Roles whose names start with "Cognitive Services" are not to be assigned for Foundry | Chapters 09, 11, 12 |
| 4 | AZ-03 and BS-17 storage accounts | Public network access forced to `Disabled` unless perimeter-secured or exempt | D19 now authorizes individual network waivers for the public PoC (chapter 19); perimeter/private access and check 29 remain fallback options | Chapter 12 AZ-03 and §12.16; chapter 15 D19 |
| 5 | Every Storage access | Shared key and anonymous access disabled | Tools use Entra ID, such as `--auth-mode login` for `az storage`. D7 requires no Terraform state account | Chapter 12 AZ-03 |
| 6 | AZ-18 Event Hubs (ingestion option B) | Local authentication disabled | Entra ID only, as designed | — |
| 7 | AZ-17 diagnostic settings | Policy sends Foundry logs and metrics to the governance workspace | AZ-17 keeps only the Container Apps environment; no second copy for Foundry | Chapter 12 AZ-17 |
| 8 | GR-04 | Only `ProvisionedManaged` denied | GR-04 stays, to block global and data-zone provisioned throughput as well | Chapter 12 GR-04 |
| 9 | Cost | Defender plans and governance logs billed in the subscription | ≈ $30–65 a month per environment at rest; $0.80 per million text tokens; logs ≈ $0 | Chapter 13 §13.3 |
| 10 | Bootstrap identities and tenant settings | Entra and Fabric administrator roles needed (§18.8) | The owner activates the eligible roles right before the bootstrap | Phase-0 questions A3, A4, A9 |
| 11 | Teardown and safety net | Governance resources live in the same subscription (§18.5, §18.7) | Never touch resources the project did not create. The safety net selects by tag; the teardown deletes only its own stacks | — |

### Storage without public endpoints: fallback if exemptions are unavailable

The original perimeter-first recommendation below is retained as a fallback, not the current PoC selection.
Chapter 19 records the agreed exemption experiment and its observations.

The Lab-state account (AZ-03) and ops account (BS-17) have five kinds of callers: runtime/control identities,
Automation, CI (scenarios, leases and retained exports), the Fabric bridge notebook and people. There is no Terraform
state caller after D7. Test actual Entra principals and service support; a subscription membership rule is not proof
that every caller can connect.

| Option | How | What changes | Cost *(estimate)* |
|---|---|---|---|
| **A network security perimeter** (recommended; test first) | Both accounts join a perimeter, with `publicNetworkAccess` set to `SecuredByPerimeter` [F90]. Inbound rules admit the subscription, so managed identities of this subscription pass *(verify)*, and the operators' IP prefixes. Transition mode first, then Enforced | GitHub-hosted runners have no identity in the subscription and change IP addresses: CI moves its storage steps to self-hosted runners in Container Apps jobs, or adds and removes its own address around a job *(verify)*. The bridge notebook uses the fallback of check 8: a file in OneLake that the watchdog picks up | No charge for the perimeter is known *(verify)* |
| Private networking | A Container Apps environment in a virtual network; private endpoints with DNS zones for blob, table and queue; self-hosted runners inside the network | As above for CI and the bridge notebook. Operators reach data through the Lab Control API. More elements to build and test (decision D19) | ≈ $30 a month per environment: four private endpoints and three DNS zones |
| Fewer callers (with either option) | Nothing outside Azure writes to Storage: Activator and people go through the Lab Control API | Simpler rules, one more path through Lab Control | — |

The question of fact behind the first option, which callers a subscription rule admits, is **check 29** of chapter 12
§12.16. Phase 0 answers it in the identity-and-control spike (chapter 14 §14.4).

---

## 18.11 The shared Foundry resource

The owner asked for one Foundry resource whose models several projects share, in a resource group of its own. It is
built by [`infra/shared-foundry`](../infra/shared-foundry/README.md), only from code:

| Aspect | Choice |
|---|---|
| Template | Bicep with the Azure Verified Module for Cognitive Services accounts [F91], deployed as a subscription-scope deployment stack, which deletes what leaves the template [F82]. Known limits of stacks are in [F83] |
| Region | Sweden Central by default: all four GPT families and the image models are offered there, and it is not denied |
| Models | One deployment per family listed in `model-selection.json`, at the newest version that is not retiring soon, with the capacity set to the free quota at deploy time (§18.9) [F84] |
| Access | Keys disabled (§18.4); **Foundry User** for people, groups and the identity of each project [F85]; the v1 API with Entra tokens [F86] |
| Removal | The stack deletes the resource group; the script then purges the soft-deleted account, which would otherwise keep its name for 48 hours [F87] |
| Tenant rules | Region and deployment type checked before deploying; the policy-made diagnostic setting and Defender for AI are left to the tenant (§18.5, §18.6) |
| Cost | Nothing at rest; tokens and images at the model's price; Defender for AI on text tokens |

**Status.** Deployed in Sweden Central on 18 October 2026 with the ten deployments of the plan, and each one answered
a [smoke test](../infra/shared-foundry/README.md#smoke-test). The account kept key access off and public access on;
no policy changed them.

**How Giandoria can use it** (part of decision D4):

* **Its own Foundry resource, the default.** AZ-13 to AZ-15 as designed, with gpt-5-mini and gpt-5-nano behind the
  aliases. Their quota is free (§18.9) and the cost of each environment stays separate.
* **The shared resource.** A Giandoria project in the shared account, and the aliases point at shared deployments.
  Nothing to deploy for models, but Azure no longer separates Giandoria's model cost from that of other projects.
  The cost meter of chapter 13 §13.6 still counts tokens per run, so the lab's own limits keep working.

---

## 18.12 Repeating the audit

The commands below read everything this chapter reports. They change nothing.

```powershell
$sub = az account show --query id -o tsv
$arm = "https://management.azure.com/subscriptions/$sub/providers"

# Every policy assignment that applies to the subscription, including those inherited from management groups
az rest --method get --url "$arm/Microsoft.Authorization/policyAssignments?api-version=2023-04-01"
# The members of a policy set: use the policyDefinitionId of an assignment
az rest --method get --url "https://management.azure.com<policyDefinitionId>?api-version=2023-04-01"

# Compliance
az policy state summarize
az policy state list --filter "complianceState eq 'NonCompliant'"

# Defender plans, delegated management, deny assignments, locks
az rest --method get --url "$arm/Microsoft.Security/pricings?api-version=2024-01-01"
az rest --method get --url "$arm/Microsoft.ManagedServices/registrationAssignments?api-version=2022-10-01"
az rest --method get --url "$arm/Microsoft.Authorization/denyAssignments?api-version=2022-04-01"
az lock list

# Your own role assignments at every scope
az role assignment list --assignee <your-object-id> --all --include-inherited

# Model quota in a region
az cognitiveservices usage list --location swedencentral
```

* **On Windows,** `az` is a batch file, so arguments that contain `&`, `(` or `)` are mangled. Call URLs with several
  query parameters from PowerShell with a token from `az account get-access-token`, and avoid JMESPath functions in
  `--query`.
* **When to repeat it:** before phase 0, before phase 9, and after any unexplained `RequestDisallowedByPolicy`.

---

## 18.13 Open points

| # | Open point | How it closes | Where |
|---:|---|---|---|
| 1 | Which Entra and Fabric administrator roles the owner can activate | The owner answers A3 and A4 | Phase-0 decisions |
| 2 | Which callers a perimeter's subscription rule admits; how CI reaches its state | Check 29 | Chapter 12 §12.16 |
| 3 | Defender cost after the trials, and how CSPM counts apps scaled to zero and jobs | The first invoice after mid-November 2026; the daily reconciliation | Chapter 13 §13.6 |
| 4 | Whether the governance workspace shares the free 5 GB of Log Analytics | The invoice | §18.5 |

Closed after the first deployment of the shared Foundry (18 October 2026): Global Standard quota is one pool per
subscription (§18.9), and Foundry request logs reach the governance workspace without prompts or completions
(§18.5).
