# Giandoria Decision Room

A native Fabric App for investigating enterprise signals and recording a private judgement.
The interface uses React, Radix Themes and Rayfin's authenticated Fabric services.
It reads a verified published snapshot, not the advancing simulation; reviews never execute business actions.

Start with [the app authoring and architecture guide](../../docs/27-decision-room.md).
Publication and authentication commands belong to the
[lab runbook](../../infra/demo/README.md#native-decision-room-app).

## Workspace ownership

| Location | Purpose |
|---|---|
| `packages/frontend` | Decision inbox, explorer, arithmetic workbench, review journal and responsive theme |
| `packages/data` | Decorated `DecisionReview` entity and server-side authenticated-owner policy |
| `packages/shared` | Browser-safe contracts, evidence query and generated local source context |
| `packages/functions` | Hosted Data Agent investigation, source guards and bounded MCP transport |
| `rayfin/rayfin.yml` | Fabric services, protected assets, authentication and semantic connector |
| `scripts` | Capability tooling and source-contract verification |
| `tests/service.test.mjs` | Transport, definition hashing, operation polling and cleanup tests |

Keep the stable `@rayfin-app/*` package names. Install dependencies from this directory only; there is one
workspace lockfile. Capability packs are applied serially and generated Function types are not hand-edited.
Source coordinates, `.env` files and the deployment registry are local ignored configuration.

## Development checks

From this directory, run serially:

```powershell
npm run typecheck
npm run build
npm run lint
npm test
```

The build uses `--noCheck`, so it does not replace typecheck. Tests include frontend behaviour and the
Node service suite. The installed Rayfin CLI is run through the repository wrapper with pinned Node 22;
do not assume the machine's default Node version is compatible.

Preparation requires the verified semantic-model, Data Agent and ontology publications. From the repository
root, `ops\Invoke-DecisionRoom.ps1` supplies Prepare, Login, Query, Sources, Dev, Preview, Deploy and Status
actions while preserving the approved workspace and recording operational commands.
Local frontend readiness does not prove local Functions readiness; validate both explicitly.

## Behaviour and limits

* All business windows and dates use virtual time and the fixed published cutoff.
* Evidence comes from the real enterprise semantic connector. Missing or unsupported values are not zero.
* The Data Agent generates an answer on request; source hashes are checked before and after inference.
* Stock-cover policies are labelled arithmetic sensitivity, not causal simulations.
* Personal reviews persist in the app-managed SQL database with server-side owner authorization.
* App assets remain protected and the existing sign-in boundary is preserved.
* External Function access uses the item owner's Fabric identity; app sharing must respect that audience.
* No business writeback, hidden-truth access, automatic inference retry or live company control is provided.

After deployment, verify the actual hosted app and perform a test review's
create/reload/update/reload/delete/reload lifecycle. Publication success alone is insufficient.
The lab's independent shutdown schedule still applies, and retained SQL/storage can cost money while F4 is idle.

The official Rayfin scaffold's [license](LICENSE) and source notices remain in place.
