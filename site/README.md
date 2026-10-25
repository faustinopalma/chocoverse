# The Data Agent story minisite

[Read the recovery review](https://faustinopalma.github.io/chocoverse/).
The site turns the [authoritative Markdown](../docs/data-agent-story.md) into a continuous investigation,
opening with Giandoria's connected value chain and reaching a synthesis in four sections.
The opening sets the company context, capacity changes and questions without revealing the results.
Quantities and insights appear after their recorded Data Agent answers; the final section connects those findings.
Each question has a stated purpose: establish the current
product sales, trace the factory flow, then assess how far company backlog has recovered.
Other feature demonstrations remain in the [technical guide](../docs/29-data-agent-companion.md).
There are no exercises or answers to unlock.
It uses captured evidence, makes no live Fabric calls and needs no Azure capacity.
It has no analytics, cookies or sign-in. Whiteboard annotations are stored in browser
local storage, separately for each language; they stay on that browser profile and are not
included in print or shared with report recipients.
The whiteboard toolbar is hidden on touch-first and narrow-screen devices. On desktop it
appears only after the browser detects a hovering pen; mouse drawing remains an explicit
toolbar option. Browsers expose a generic pen pointer type, not the pen's manufacturer,
so Wacom-specific detection is not available.

The language selector links two static editions: English (`index.html`, the default) and Italian (`it.html`).
The [Italian translation](../docs/data-agent-story.it.md) follows the English source's structure and results.
Both editions share the same untouched screenshots and native chart; original recorded questions remain English.
Story text, captions, navigation, legend and viewing controls are translated.
Language switching works without JavaScript; with scripts it also retains the chapter and selected theme.
There is no automatic language detection or stored language preference.

The visual template is an original manufacturing-company review: a typographic masthead, ruled contents,
numbered exhibits and a closing synthesis. A short prose introduction establishes Giandoria and Chocoverse
before the review, without a value-chain card grid. It uses an editorial layout rather than a dashboard.
An AI-generated conceptual illustration accompanies that introduction; it is labelled separately from
the authentic, numbered Data Agent exhibits. The static WebP lives in `art/giandoria-editorial.webp`.
All reasoning remains readable without JavaScript; scripts provide theme selection, evidence viewing and
local whiteboard annotations.

## Retained 3D artwork

The 3D illustration is retained for reuse but is not included in the minisite or its published assets.

The original [scene builder](./art/build-chocoverse.py) uses the existing BlenderMCP archive's
`scripts/gallery_common.py` geometry helpers. It runs in a separate factory-startup Blender process;
it does not change an open Blender session or any archived scene.
The checked-in [GLB](./art/chocoverse.glb) contains actual meshes and materials, with no remote assets or decoders.
`@google/model-viewer` 4.3.1 remains pinned for reuse; its bundle is not published or loaded by the minisite.

To regenerate with Blender 5.2 and the local archive (adjust the paths if needed):

```powershell
. .\ops\CommandJournal.ps1
Invoke-RecordedNative -FilePath 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  -Arguments @('--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
    '--python', 'site\art\build-chocoverse.py', '--', 'C:\code\BlenderMCP') -TimeoutSeconds 240
```

The editable Blender file and inspection render stay in ignored `.local/chocoverse-art`.

## Edit and validate

Edit both narrative editions in Markdown, presentation in `shell.html` and `style.css`,
UI translations in `build.mjs`, and viewing controls in `story.js`.
Tests retain coverage checks for the archived Fabric chart without publishing it in the new investigation.
Changed chapter structure or evidence contracts fail the build or tests.
Keep each captured output with its recorded input. Quote the original request rather than reconstructing it
from the answer; label execution traces that share an input. Use named documentation links.
The closing note links to the wider project; the sources note links to reproducibility and verification limits.

From the repository root, with Node.js 24 and npm installed:

```powershell
. .\ops\CommandJournal.ps1
Invoke-RecordedNative -FilePath 'npm.cmd' -Arguments @('--prefix', 'site', 'ci')
Invoke-RecordedNative -FilePath 'npm.cmd' -Arguments @('--prefix', 'site', 'run', 'build')
Invoke-RecordedNative -FilePath 'npm.cmd' -Arguments @('--prefix', 'site', 'test')
```

The build replaces only generated `site/dist`. It copies explicitly referenced evidence images from
`docs/images/data-agent-story` and the company illustration from `art/giandoria-editorial.webp`.
Private presentations and lab records are never site inputs.
Tests check the publication files, local links, numerical facts, date completeness and reasoning boundaries.

Serve `site/dist` with a local static HTTP server for browser checks. Check narrow and wide screens,
both themes, keyboard navigation, image viewing and Escape, and the full recommendation with JavaScript disabled.
There is no animated or scroll-triggered content. Stop the preview server after use.

## Publish

The [Pages workflow](../.github/workflows/story-pages.yml) builds and tests changes on `main`, then publishes
only `site/dist` through GitHub Pages. GitHub Pages must use **GitHub Actions** as its publishing source.
The workflow can also be dispatched manually. Do not commit generated output or publish the repository root.

The [companion runbook](../docs/29-data-agent-companion.md) owns actual Fabric execution and capability gates.
The report keeps unverified and blocked platform features separate from the demonstrated results.
