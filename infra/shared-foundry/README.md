# Shared Foundry

One Microsoft Foundry account whose model deployments several projects share. It lives in its own resource group,
apart from any single workload, and it is created only from code: Bicep with Azure Verified Modules (AVM), deployed
as a subscription-scope deployment stack by a PowerShell script. No step needs the Azure portal.

Giandoria uses it for its LLM agents ([chapter 09](../../docs/09-llm-agents.md)); other repositories can use it too.

> **Read two sections before the first deployment.** [Quota](#quota-what-maximum-means): by default the plan takes
> all the free quota of each selected model, and for most models that pool is shared by every region of the
> subscription. [Cost](#what-it-costs): there is no fixed fee, but tenant policies can add charges.

---

## What it creates

| Resource | Default name | Settings |
|---|---|---|
| Resource group | `rg-shared-ai-<region>` | Tags `scope=shared`, `workload=ai-models`, `managed-by=bicep` |
| Foundry account (`Microsoft.CognitiveServices/accounts`, kind `AIServices`, SKU S0) | `aif-shared-<region>-<hash>` | System-assigned identity; project management on; key access off; public endpoint on, optionally limited to IP ranges |
| Model deployments | The model name, for example `gpt-6-astra` | One per family of `model-selection.json`; deployment type Global Standard; version pinned; capacity sized to the free quota |
| Project | `proj-shared-playground` | System-assigned identity; a place to try the models from the Foundry portal or SDK |
| Role assignments | — | **Foundry User** on the account for the users and groups in `.env` (default: whoever deploys) and for the identity of each project |
| Deployment stack | `stack-shared-ai-<region>` | Subscription scope; tracks every resource above and deletes what leaves the template |

The `<hash>` is six characters of `uniqueString(subscription ID, region)`: stable for one subscription and region,
and unique enough for the account name, which is also the global endpoint subdomain.

It does **not** create a Log Analytics workspace, private endpoints, a key vault, storage, Azure AI Search or
Defender plans. You can pass an existing workspace for an own diagnostic setting (see `.env`). In the reference
tenant, Azure Policy adds a diagnostic setting and Defender for AI by itself; see
[Settings that tenant governance imposes](#settings-that-tenant-governance-imposes).

---

## The models

Snapshot of `model-plan.json`, generated on 18 October 2026 for Sweden Central. The file is the source of truth; a
new run of the resolver can change it.

| Deployment | Use | Version | Status | Capacity | Quota pool | Retires |
|---|---|---|---|---:|---|---|
| `gpt-6-astra` | Chat | 2026-09-03 | GA | 250K TPM | Global | 2028-01-11 |
| `gpt-6.1-sol` | Chat | 2026-09-29 | GA | 250K TPM | Global | 2028-03-11 |
| `gpt-5.6-terra` | Chat | 2026-07-09 | GA | 250K TPM | Global | 2028-01-11 |
| `gpt-6-luna` | Chat | 2026-09-22 | GA | 250K TPM | Global | 2028-03-11 |
| `gpt-image-2.5-flare` | Image | 2026-09-08 | GA | 2 RPM | Global | 2027-09-08 |
| `gpt-image-2.5-sunburst` | Image | 2026-09-08 | GA | 2 RPM | Global | 2027-09-08 |
| `MAI-Image-2.6` | Image | 2026-07-31 | Preview | 6 RPM | Global | 2027-01-09 |
| `MAI-Image-2.6-Flash` | Image | 2026-07-31 | Preview | 6 RPM | Global | 2027-01-09 |
| `FLUX.2-pro` | Image | 1 | GA | 4 RPM | Sweden Central | None announced |
| `FLUX.2-flex` | Image | 1 | GA | 4 RPM | Sweden Central | None announced |

* **Units.** One capacity unit of a chat model allows 1,000 tokens and one request per minute, so capacity 250 is
  250K tokens per minute (TPM) and 250 requests per minute. One unit of an image model is one request per minute
  (RPM). The model catalog states both rates (`skus[].rateLimits`).
* **Skipped.** The `mai-image-pro` family: its only version, `MAI-Image-2.5-Pro`, retires on 15 November 2026, within
  the 60 days that `model-selection.json` requires. The family comes back by itself when a newer version appears.
* **Preview.** The MAI image models are in preview: no service-level agreement, and they can change or go away.
  Families accept preview models only when `allowPreview` is true.
* **Version upgrades.** The OpenAI deployments use `NoAutoUpgrade`: a version changes only when you deploy a new
  plan. A deployment stops serving when its version retires *(verify)*, which is why the resolver refuses versions
  that retire within `minDaysToRetirement` days and why you should re-run it from time to time. The resolver sets
  the option only for the OpenAI format; the MAI and FLUX deployments get the service default,
  `OnceNewDefaultVersionAvailable`, so Azure can move them to a newer default version by itself. Run the resolver
  before the next deployment: with `-SkipResolve` the plan would ask for the older version again *(verify)*.

---

## Files

| File | Edited by | Role |
|---|---|---|
| [`main.bicep`](./main.bicep) | People | Subscription scope: the resource group and the account module; outputs |
| [`modules/foundry.bicep`](./modules/foundry.bicep) | People | The account (AVM `cognitive-services/account`), deployments, projects and role assignments |
| [`types.bicep`](./types.bicep) | People | Types of the deployments, users and projects |
| [`main.bicepparam`](./main.bicepparam) | People | Reads `model-plan.json` and the tenant-specific values from environment variables |
| [`model-selection.json`](./model-selection.json) | People | Which model families to deploy, with which SKU and rules |
| [`model-plan.json`](./model-plan.json) | The resolver | Lock file: exact models, versions and capacities for one region |
| [`scripts/Resolve-ModelPlan.ps1`](./scripts/Resolve-ModelPlan.ps1) | — | Turns the selection into the plan, reading the model catalog and the quota |
| [`scripts/Deploy-SharedFoundry.ps1`](./scripts/Deploy-SharedFoundry.ps1) | — | Preview, validation, confirmation, deployment |
| [`scripts/Remove-SharedFoundry.ps1`](./scripts/Remove-SharedFoundry.ps1) | — | Deletes everything and purges the soft-deleted account |
| [`scripts/common.ps1`](./scripts/common.ps1) | — | Shared helpers: `.env` loading, sign-in checks, JSON calls to the Azure CLI |

---

## Prerequisites

* **Tools.** PowerShell 7.4 or later, the Azure CLI and the Bicep CLI, on Windows, Linux or macOS. Tested with
  PowerShell 7.6.7, Azure CLI 2.89.1 and Bicep 0.42.1. If `bicep` is on the `PATH`, the scripts tell the Azure CLI
  to use it. The first build downloads the AVM module from `mcr.microsoft.com`.
* **Permissions on the subscription.** Owner, or Contributor plus Role Based Access Control Administrator, because
  the template creates role assignments. If your role is eligible through Privileged Identity Management (PIM),
  activate it first. Reading quota needs Reader or Cognitive Services Usages Reader.
* **A region that offers the models.** Check with `Resolve-ModelPlan.ps1 -Location <region>`: it lists what it
  found and what it skipped, without deploying anything. The reference tenant denies `westeurope`.

---

## Sign in with an isolated Azure CLI profile

The scripts work with one tenant and one subscription and refuse to run against anything else. An isolated Azure
CLI profile keeps that tenant's tokens apart from your other sign-ins: the Azure CLI keeps everything in the folder
named by `AZURE_CONFIG_DIR`.

```powershell
# Windows PowerShell 7; on Linux or macOS use a path such as $HOME/.azure-profiles/my-lab
$env:AZURE_CONFIG_DIR = 'C:\AzureCliProfiles\my-lab\.azure'
az login --tenant <tenant-id> --use-device-code
az account set --subscription <subscription-id>
```

The scripts read `AZURE_CONFIG_DIR` from `.env`, so later sessions need no `$env:` line. Without it, they use your
default profile.

---

## Configure `.env`

Copy [`.env.example`](../../.env.example) to `.env` at the repository root and fill it in. Git ignores `.env`, so
no tenant ID, subscription ID or object ID is committed. A variable already set in the shell wins over the file.

| Variable | Meaning | Default |
|---|---|---|
| `AZURE_CONFIG_DIR` | Isolated Azure CLI profile folder | The default profile |
| `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | The only tenant and subscription the scripts accept | Required |
| `SHARED_FOUNDRY_LOCATION` | Region of the account | The region of `model-plan.json` |
| `SHARED_FOUNDRY_USER_OBJECT_IDS` | Comma-separated Entra object IDs of users that get Foundry User | The signed-in user, when both lists are empty |
| `SHARED_FOUNDRY_GROUP_OBJECT_IDS` | Comma-separated Entra object IDs of groups that get Foundry User | Empty |
| `SHARED_FOUNDRY_ALLOWED_IP_RANGES` | Comma-separated public IPv4 addresses or CIDR ranges allowed to call the endpoints | Empty: all networks, with Entra authentication |
| `SHARED_FOUNDRY_LOG_ANALYTICS_WORKSPACE_ID` | Resource ID of a workspace for an own diagnostic setting | Empty: none |
| `SHARED_FOUNDRY_ENABLE_TELEMETRY` | AVM usage telemetry | `true` |

---

## Choose the models

[`model-selection.json`](./model-selection.json) names model **families**, not versions:

| Field | Meaning |
|---|---|
| `sku` | Deployment type of every deployment, `GlobalStandard` by default |
| `openAiVersionUpgradeOption` | Upgrade policy of the OpenAI-format deployments, `NoAutoUpgrade` by default |
| `minDaysToRetirement` | Refuse versions that stop serving within this many days |
| `families[].family`, `purpose` | Label and use (`chat` or `image`), copied into the plan |
| `families[].format` | Publisher format in the catalog: `OpenAI`, `Microsoft`, `Black Forest Labs`, … |
| `families[].match` | Regular expression on the model name; its named group `gen` orders the generations |
| `families[].allowPreview` | Accept preview models; otherwise only generally available ones |

[`scripts/Resolve-ModelPlan.ps1`](./scripts/Resolve-ModelPlan.ps1) turns the selection into the plan:

1. it lists the models that the region offers to Foundry accounts (kind `AIServices`);
2. per family, it keeps the models with the right name, format and SKU, the right lifecycle, and no retirement
   within `minDaysToRetirement` days;
3. it picks the newest generation, then the newest version;
4. it sizes each deployment to the free quota (next section) and rounds to the step that the SKU requires;
5. it writes `model-plan.json`, prints a table, and warns about every family it skipped and why.

```powershell
./infra/shared-foundry/scripts/Resolve-ModelPlan.ps1                     # region from .env or the plan
./infra/shared-foundry/scripts/Resolve-ModelPlan.ps1 -Location italynorth
./infra/shared-foundry/scripts/Resolve-ModelPlan.ps1 -QuotaShare 0.5      # take half of the free quota
```

`model-plan.json` works as a lock file. The resolver rewrites it only when something besides the timestamp changes,
so its Git diff shows exactly what a deployment would change. To add a model family, add an entry to the selection;
to drop one, remove it. Do not edit the plan by hand.

---

## Quota: what "maximum" means

Quota is a rate limit per subscription, per model and per deployment type. It is not a reservation and it costs
nothing: Global Standard deployments are billed only per token or per image used.

* **The scope of a pool varies.** The Usages API reports it per entry. In October 2026 the Global Standard quota
  of the OpenAI and MAI models had scope `Global`: **one pool for all regions of the subscription**. The first
  deployment confirmed it: East US 2, Italy North and West US 3 then reported the capacity taken in Sweden Central
  as used, although the quota documentation still describes quota per region. Data Zone Standard quota is shared
  within a data zone (`DataZone/eur`), and the FLUX models had a regional pool (`Classic/swedencentral`): their
  usage counted only in Sweden Central.
* **Consequence.** With `-QuotaShare 1` (the default) the plan takes the whole free pool: after the deployment, no
  other deployment of those models can be created anywhere in the subscription until capacity is released. Models
  outside the plan, for example `gpt-5-mini`, have their own pools and are not affected. Use `-QuotaShare 0.5` to
  leave half free, or lower the capacity of one deployment in the plan by re-running with a smaller share.
* **Re-runs do not shrink the account.** The free quota counts the capacity that this stack already holds as
  available to it, so a second run keeps the same capacity unless the limits change.
* **Quota grows.** Limits are raised over time, or on request through the quota page of the Foundry portal. Run the
  resolver again to grow the deployments.
* **Race.** If someone takes quota between the resolver and the deployment, the deployment fails with
  `InsufficientQuota`; run it again and the resolver adapts.

---

## Deploy

Preview first. `-WhatIfOnly` runs every check and stops before creating anything:

```powershell
./infra/shared-foundry/scripts/Deploy-SharedFoundry.ps1 -WhatIfOnly
./infra/shared-foundry/scripts/Deploy-SharedFoundry.ps1                 # asks you to type 'deploy'
./infra/shared-foundry/scripts/Deploy-SharedFoundry.ps1 -SkipResolve    # deploy the committed plan as it is
```

The script:

1. loads `.env` and checks that the Azure CLI is signed in to the expected tenant and subscription;
2. registers the `Microsoft.CognitiveServices` resource provider if needed;
3. refreshes `model-plan.json` with the resolver, unless `-SkipResolve`;
4. chooses who gets the Foundry User role;
5. lints the Bicep files and builds the parameters;
6. runs a what-if of the same template as a plain subscription deployment, because deployment stacks have no
   what-if yet, and lists the model deployments that the stack would delete;
7. validates the stack;
8. asks for confirmation, unless `-Force`, then creates or updates the stack.

Deployments are created one at a time, so the first run takes several minutes. The stack uses:

* `--action-on-unmanage deleteResources`: a model removed from the plan, or a project removed from the template, is
  **deleted** at the next deployment. Step 6 lists such deletions before you confirm.
* `--deny-settings-mode none`: deny settings could block other repositories from adding projects and role
  assignments under the shared account.

Without `-SkipResolve`, a deployment can pick up newer versions or more quota; review the diff of `model-plan.json`
and commit it. With `-SkipResolve`, the deployment repeats the committed plan exactly, if the quota still allows it.

---

## Call the models

Key access is disabled, so every call uses a Microsoft Entra token and the caller needs the **Foundry User** role
on the account. A new role assignment can take several minutes before calls succeed.

| Endpoint | Use |
|---|---|
| `https://<account>.openai.azure.com/openai/v1/` | OpenAI-compatible v1 API (chat completions, responses, images) with the OpenAI SDKs |
| `https://<account>.services.ai.azure.com/api/projects/<project>` | Foundry project endpoint for the Foundry SDK and Agent Service |
| `https://<account>.services.ai.azure.com/` | Routes of other publishers: the MAI and FLUX image models ([Image models](#image-models)) |
| `https://<account>.cognitiveservices.azure.com/` | Account endpoint (output `endpoint`) |

The `model` field of a request is the **deployment name**. The stack outputs list the names and endpoints:

```powershell
az stack sub show --name stack-shared-ai-swedencentral --query outputs
```

A quick test from PowerShell:

```powershell
$account = az stack sub show --name stack-shared-ai-swedencentral --query outputs.foundryName.value -o tsv
$token = az account get-access-token --scope https://ai.azure.com/.default --query accessToken -o tsv
$body = @{ model = 'gpt-6-luna'; messages = @(@{ role = 'user'; content = 'Say hello.' }) } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri "https://$account.openai.azure.com/openai/v1/chat/completions" `
    -Headers @{ Authorization = "Bearer $token" } -ContentType 'application/json' -Body $body
```

In Python, pass `get_bearer_token_provider(DefaultAzureCredential(), "https://ai.azure.com/.default")` as the
`api_key` of the `OpenAI` client, with `base_url` set to the v1 endpoint.

### Image models

Each publisher has its own route and request body. All three return the image as base64 in `data[0].b64_json`.

| Deployments | Route (POST) | Body |
|---|---|---|
| `gpt-image-2.5-flare`, `gpt-image-2.5-sunburst` | `https://<account>.openai.azure.com/openai/v1/images/generations` | `model`, `prompt`, `size` (for example `1024x1024`), `quality` (for example `low`), `n`; returns PNG |
| `MAI-Image-2.6`, `MAI-Image-2.6-Flash` | `https://<account>.services.ai.azure.com/mai/v1/images/generations` | `model`, `prompt`, `width`, `height`; returns PNG |
| `FLUX.2-pro`, `FLUX.2-flex` | `https://<account>.services.ai.azure.com/providers/blackforestlabs/v1/<path>?api-version=preview`, where `<path>` is `flux-2-pro` or `flux-2-flex`, not the deployment name | `model`, `prompt`, `width`, `height`, `output_format` (for example `jpeg`), `num_images`; FLUX.2 [flex] also takes `guidance` and `steps` |

The FLUX.2 models are not on the OpenAI-compatible images route, which among the FLUX models serves only
`FLUX.1-Kontext-pro` and `FLUX-1.1-pro`. An example with an MAI model:

```powershell
$token = az account get-access-token --scope https://cognitiveservices.azure.com/.default --query accessToken -o tsv
$body = @{ model = 'MAI-Image-2.6'; prompt = 'A box of assorted pralines'; width = 1024; height = 1024 } |
    ConvertTo-Json
$r = Invoke-RestMethod -Method Post -Uri "https://$account.services.ai.azure.com/mai/v1/images/generations" `
    -Headers @{ Authorization = "Bearer $token" } -ContentType 'application/json' -Body $body
[IO.File]::WriteAllBytes("$PWD/image.png", [Convert]::FromBase64String($r.data[0].b64_json))
```

### Smoke test

The pinned model plan was smoke-tested with Entra authentication on 2026-10-18: all listed chat deployments
answered on v1 chat completions, and all image deployments generated images through the publisher-specific routes
above. `gpt-6.1-sol` also answered on v1 responses. This establishes route compatibility, not a latency benchmark.
Both `https://ai.azure.com/.default` and `https://cognitiveservices.azure.com/.default` worked for chat;
image checks used the latter, as documented for MAI and FLUX. Recheck compatibility when the plan changes.

---

## Share the account with other repositories

* **People.** Add their object IDs, or better a group, to `.env` and deploy again.
* **Apps and managed identities.** Grant Foundry User from the other repository's own Bicep, with a module scoped to
  this resource group:

  ```bicep
  // Deploy with scope: resourceGroup('rg-shared-ai-swedencentral')
  param accountName string
  param principalId string

  resource account 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
    name: accountName
  }

  resource foundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
    name: guid(account.id, principalId, '53ca6127-db72-4b80-b1b0-d745d6d5456d')
    scope: account
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions',
        '53ca6127-db72-4b80-b1b0-d745d6d5456d')
      principalId: principalId
      principalType: 'ServicePrincipal'
    }
  }
  ```

* **Projects.** Either add the project to the `projects` parameter of `main.bicep`, or create it from the other
  repository as `Microsoft.CognitiveServices/accounts/projects` under this account. A project created elsewhere
  is not tracked by this stack: updates leave it alone, but [Remove](#remove) deletes it with the resource group.
* **Do not create model deployments by hand.** They would use the quota that the plan expects. Add a family to the
  selection instead.

---

## Keep it up to date

* **New models or versions.** Run the deploy script without `-SkipResolve`, or the resolver alone, and review the
  diff of `model-plan.json`. A new version of the same model updates its deployment in place. Deployment names are
  model names, so when a family moves to a new generation, for example from `gpt-6-astra` to a later one, the old
  deployment is deleted and a new one is created under the new name, and callers must switch names. This is
  deliberate: a model change is never hidden behind a stable name.
* **AVM module.** The version is pinned in `modules/foundry.bicep`. Read the module's release notes, change the
  version, run `-WhatIfOnly`.
* **API versions.** The projects use `Microsoft.CognitiveServices/accounts/projects@2025-12-01`, the newest version
  with types in Bicep 0.42.1. Newer versions can be used when the Bicep CLI knows them.

---

## Remove

```powershell
./infra/shared-foundry/scripts/Remove-SharedFoundry.ps1
```

The script deletes the stack with `--action-on-unmanage deleteAll`: Azure deletes the resource group and
**everything in it**, including projects and deployments that other repositories added. It lists that content
first and asks you to type the account name. It then purges the soft-deleted account: a deleted account keeps its
name for 48 hours otherwise, and a new deployment with the same name would fail. Use `-KeepSoftDeleted` to keep the
account recoverable for those 48 hours.

Subscription-level settings that tenant policies created, such as the Defender for AI plan, stay in place.

---

## Settings that tenant governance imposes

The reference tenant is a Microsoft-managed experimentation tenant with Azure Policy at the tenant root.
[Chapter 18](../../docs/18-tenant-governance.md) documents the full audit; the settings below follow from it.
Other tenants may have fewer or different rules; the template works in both cases.

| Setting | Value in the template | Why |
|---|---|---|
| `disableLocalAuth` | `true` | A Modify policy forces it anyway; matching it avoids drift between the template and Azure |
| `publicNetworkAccess` | `Enabled`, explicitly | The AVM module disables public access when it gets no value and no network rules, which would make the account unreachable without private endpoints |
| `networkAcls` | Only when IP ranges are set | Default action `Deny` with the listed ranges; trusted Azure services bypass |
| `restrictOutboundNetworkAccess` | `false` | `true` would block agent tools and inputs given as URLs |
| Deployment type | `GlobalStandard` | A Deny policy blocks regional provisioned throughput (`ProvisionedManaged`) |
| Region | Not `westeurope` | A Deny policy blocks that region |
| Diagnostic settings | Not managed here | A DeployIfNotExists policy adds one that sends all logs and metrics to a governance workspace in the same subscription, in West US 2, without a daily cap; the stack does not track it. After the first deployment the policy created it eleven minutes after the account; calls made before it, or in its first minutes, leave no logs. The logs hold metadata such as the caller, the deployment, tokens and duration, never prompt or completion text. The metrics hold totals for the whole account: for figures per deployment, use the account's metrics in Azure Monitor. Details in chapter 18 §18.5 |
| Defender for AI | Not managed here | A policy enables it at subscription level, with prompt evidence and sharing with Microsoft Purview; it scans and bills text tokens only, after a trial |

---

## What it costs

| Item | Cost |
|---|---|
| Account (S0), projects, quota, role assignments, stack | No fixed fee |
| Model deployments (Global Standard) | Nothing at rest; per token or per image when called, at the model's price |
| Defender for AI services (enabled by tenant policy) | $0.0008 per 1,000 text tokens scanned, after a free trial of 30 days *(list price, October 2026)*. Image generation is not scanned |
| Diagnostic logs (tenant policy) | Ingested into the governance workspace, billed to this subscription: the first 5 GB a month free, then $2.30 per GB *(list price, October 2026)*. Request logs are small: about 1.8 KB per chat call, as measured on the first deployment |
| Other Defender plans (tenant policy) | Billed for other resources of the subscription, such as storage accounts and container apps; nothing for the Foundry account itself. See chapter 18 §18.6 |
| AVM telemetry | Free: an empty deployment whose name starts with `46d3xbcp` |

Example: 10 million tokens through the chat models add $8 of Defender for AI scanning to the model price.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `InsufficientQuota` | Quota changed after the plan was made; run the deploy script again without `-SkipResolve`, or lower `-QuotaShare` |
| `RequestDisallowedByPolicy` | A tenant policy denied the request, for example region `westeurope` or SKU `ProvisionedManaged`; the error names the policy; see chapter 18 |
| HTTP 401 or 403 on a model call | No Foundry User role, the role is still propagating (wait a few minutes), or a key was used instead of a token |
| `FlagMustBeSetForRestore` or "name already in use" | A soft-deleted account with the same name exists; purge it (`az cognitiveservices account purge`) or recover it |
| `RoleAssignmentUpdateNotPermitted` on a project | The project was deleted and recreated outside the stack, so its identity changed; delete the old role assignment and deploy again |
| The resolver skips a family | The reason is printed: not offered in the region, retiring soon, no quota entry, or no free quota |
| `model-plan.json targets <region>` | The plan was made for another region; run the resolver with `-Location` |

---

## Sources

Read in October 2026.

* Deployment stacks: <https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/deployment-stacks> and
  known issues: <https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/deployment-stacks-known-issues>
* Quota of Foundry models: <https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/quota>
* Role-based access control for Foundry, including the role renames:
  <https://learn.microsoft.com/en-us/azure/foundry/concepts/rbac-foundry>
* v1 API and Entra authentication: <https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle>
* Image models of other publishers, MAI:
  <https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image>;
  FLUX: <https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-flux>
* Recover or purge deleted resources: <https://learn.microsoft.com/en-us/azure/ai-services/recover-purge-resources>
* AVM module `cognitive-services/account`:
  <https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/cognitive-services/account>
* Defender for AI services: <https://learn.microsoft.com/en-us/azure/defender-for-cloud/ai-threat-protection>;
  price from the Azure Retail Prices API (`Microsoft Defender for AI Services`, meter `Standard Tokens`)
