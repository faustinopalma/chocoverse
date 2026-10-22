# The Data Agent story minisite

[Read the inventory review](https://faustinopalma.github.io/chocoverse/).
The site turns the [authoritative Markdown](../docs/data-agent-story.md) into a continuous investigation,
reaching an operational next step in four sections. Each question has a stated purpose: establish the current
inventory position, check its persistence, then assess whether product-level priorities are supported.
Other feature demonstrations remain in the [technical guide](../docs/29-data-agent-companion.md).
There are no exercises or answers to unlock.
It uses captured evidence, makes no live Fabric calls and needs no Azure capacity.
It has no analytics, cookies, sign-in or client-side storage.

The visual template is an original manufacturing-company review: a typographic masthead, ruled contents,
numbered exhibits and a closing decision table. It uses an editorial layout rather than dashboard cards.
All reasoning is visible without JavaScript; scripts only provide theme selection and an evidence viewer.

## Edit and validate

Edit the narrative in Markdown, presentation in `shell.html` and `style.css`, and viewing controls in `story.js`.
Tests retain coverage checks for the archived Fabric chart without publishing it in the new investigation.
Changed chapter structure or evidence contracts fail the build or tests.
Keep each captured output with its recorded input. Quote the original request rather than reconstructing it
from the answer; label execution traces that share an input. Use named documentation links.
The closing note links to the original repository and distinguishes live observations
from snapshot-based analysis.

From the repository root, with Node.js 24 and npm installed:

```powershell
. .\ops\CommandJournal.ps1
Invoke-RecordedNative -FilePath 'npm.cmd' -Arguments @('--prefix', 'site', 'ci')
Invoke-RecordedNative -FilePath 'npm.cmd' -Arguments @('--prefix', 'site', 'run', 'build')
Invoke-RecordedNative -FilePath 'npm.cmd' -Arguments @('--prefix', 'site', 'test')
```

The build replaces only generated `site/dist`. It copies explicitly referenced evidence images from
`docs/images/data-agent-story`; private presentations, lab records and repository contents are never site inputs.
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
