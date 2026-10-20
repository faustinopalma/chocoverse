# 19 - Authenticated public endpoints and justified policy exemptions

## Summary

We use authenticated public endpoints for the nonproduction synthetic-data lab. Network-isolation waivers are
an explicit, bounded architectural decision, not permission to publish data or bypass identity controls.
Read-only probes verify Storage access and anonymous denial; the completed two-year cloud collection also
proves the runtime-to-Storage and inference paths. No observed governance action has removed the existing waivers.
This does not guarantee future tenant acceptance. Commands are in the [infra guide](../infra/demo/README.md).

## Rationale for reviewers

**Risk proportionality.** The business data describes a fictional company, generated demand, transactions,
inventories and model briefings. It contains no real customer records, confidential business facts or regulated
personal data. Private-only routing would add a useful perimeter layer, but its incremental confidentiality
benefit is limited for this dataset. We accept that residual network exposure rather than imposing standing
private endpoint costs, private DNS, network-integrated client connectivity and additional operating complexity
on an intermittent lab. ACR Private Link would also require a different registry tier.

**Public routing is not public authorization.** The endpoint is reachable over the internet, but each data
request still needs an authorized Entra identity and its resource-scoped data role. Storage requires HTTPS and
TLS 1.2 or later; Shared Key and anonymous blobs are disabled. ACR admin credentials and anonymous pulls are
disabled. Shared Foundry local/key authentication is disabled. Managed identities avoid embedded credentials;
the deployed runtime image is pinned by digest. Existing diagnostics, Defender and usage controls are retained.
These are strong controls for the stated low-sensitivity experiment, not proof of an invulnerable system.

**What still matters.** Synthetic data reduces confidentiality impact, not the value of credentials, execution
integrity, checkpoints, cloud spending or availability. An identity compromise or vulnerable container can still
cause harm. Consequently these waivers do not exempt identity hygiene, authentication, encryption, security
notifications, vulnerability management, diagnostics or spending controls. Private connectivity is defense in
depth; Entra authentication is not claimed to provide equivalent network isolation.

**Shared Foundry boundary.** Its account-level network waiver also applies to other consumers. Giandoria's
briefings are synthetic; that does not establish the classification of every other client's inputs. The shared
endpoint is designated for low-sensitivity, nonproduction experimentation. Each new consumer must assess its
inputs and requirements before use; confidential or production usage requires a new review, not automatic
reliance on Giandoria's data classification. The waiver changes no model, role, endpoint or Defender plan.

## Exemption register

Every exemption is category **Waiver**, limited to one resource and explicit initiative members.
None exempts an entire initiative, resource group or subscription. No expiration is set: `expiresOn` is omitted
[F97]. This avoids arbitrary renewal churn for a standing design decision; it does not mean unconditional or
irrevocable acceptance. Classification changes, new consumers, production use, weakened controls or changed
tenant requirements trigger review. Administrators can revoke the exemptions at any time.

| Resource | Exemption | Initiative members covered |
|---|---|---|
| State Storage `stgiandoriademoepo4` | `giandoria-public-storage-poc` | Deploy-and-modify: `StorageAccountPublicNetworkModify` only |
| Export Storage `stgiandoriaopsdemoepo4` | `giandoria-public-storage-poc` | Same single Modify member |
| Each of the same two Storage accounts | `giandoria-public-network` | Security baseline: unrestricted-network, VNet-rules and Private Link audits only |
| ACR `crgiandoriademoepo4` | `giandoria-public-network` | Security baseline: unrestricted-network and Private Link audits only |
| Shared experimental Foundry account in `rg-shared-ai-swedencentral` | `giandoria-public-network` | Security baseline: network restriction and Private Link audits only |

The deployment resolves and verifies the exact member-to-definition mapping. Each live description states the
resource-specific rationale; metadata records retained controls, residual risk, review triggers and this chapter.
Tenant, subscription, assignment and principal IDs remain in ignored local records.

## Other policy findings: no blanket exemption

Policy history must be reduced to the newest state per resource, assignment and initiative member, including
Compliant and Exempt states. Filtering historical NonCompliant rows first can resurrect already-resolved findings.
Policy exemption creation/readback and data-plane verification are separate from eventual compliance evaluation.
Completed reevaluation marks all twelve intended network results Exempt: ten audit results and two Modify results,
covered by six exemption resources. No non-network result is suppressed.

| Finding family | Treatment and reason |
|---|---|
| Storage, ACR and Foundry network isolation | Narrow waivers above; the authenticated public design is intentional |
| Automation configuration encryption | Live configuration is encrypted; publishing explicitly requests encryption and verifies readback. No waiver |
| Foundry project diagnostics | Previously reported failure is not current noncompliance. No waiver; diagnostics remain required |
| ACR image vulnerabilities | The deployed digest is rebuilt with the published fixes for all eight reported package families; actual versions, non-root execution, dependencies and imports are verified. Fresh Defender results remain pending/unknown; retained historical findings are not deleted or exempted |
| Custom RBAC roles | Two newly evaluated audits flag the lab-control and chat-inference custom roles. Their explicit action allowlists avoid broader built-in permissions, but this alone does not close the required role/threat-model review. No waiver or privilege expansion |
| Blocked/guest identities with resource permissions | Subscription-level identity review remains required. Data classification is not evidence that an identity or its access is legitimate |
| Security contact and high-severity email notifications | Subscription-level configuration remains required; choose a monitored recipient rather than inventing one or hiding the finding |
| Defender for APIs and SQL-on-machines provisioning | No API Management, SQL server or VM workload is deployed in the inspected subscription. Record applicability for tenant review; do not broadly waive subscription protection for future workloads |

The remaining findings are not represented as compliant or harmless. IAM removals, subscription-wide notification
changes and Defender-plan changes require their own verified scope and decisions. Their presence does not negate
the evidence for authenticated Storage connectivity or justify expanding a network exemption.

## Deployment and verification contract

Initial Storage provisioning remains network-disabled: create/read back the exact Modify waiver, then enable the
endpoint. The explicit network-exemption deployment validates resource identity, ownership, location, retained
controls, exact policy members and what-if. It updates descriptions and creates only the reviewed audit waivers;
it does not change inherited assignments or actual networking. Normal reconciliation never recreates exemptions.
A previously recorded exemption that disappears is an error, not an instruction to restore it.

The Storage read-only probe checks actual settings, Modify-waiver scope and validity, and:

- Entra-authenticated reads of retained synthetic blobs on both accounts;
- authenticated state Table and Queue access;
- anonymous denial on the same existing blobs: HTTP 401/403, or HTTP 409 with `PublicAccessNotPermitted`,
  never an unrelated conflict or a missing object.

ARM success is not a data-access test. Evidence includes the authenticated/anonymous probe, actual completed
worker activity, live service controls and exemption readback. Detailed observations and policy states stay in
ignored `.local` records and the command journal, not in a public execution timeline.

## If governance changes access

Stop and inspect the waiver, actual account settings, policy compliance and Activity Log. Do not automatically
repair/recreate exemptions or infer the cause from an access failure alone. Revocation does not necessarily
disable an existing endpoint immediately: Modify can act on later writes or remediation [F92][F97].
Revisit perimeter/private access if the public approach is no longer allowed.
