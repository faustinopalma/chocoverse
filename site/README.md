# The Data Agent story minisite

[Read the interactive story](https://faustinopalma.github.io/chocoverse/).
The site turns the [authoritative Markdown](../docs/data-agent-story.md) into eight chapters with five
browser-only exercises. It uses captured evidence, makes no live Fabric calls and needs no Azure capacity.
It has no analytics, cookies, sign-in or client-side storage.

## Edit and validate

Edit the narrative in Markdown, presentation in `shell.html` and `style.css`, and exercises in
`learning.js` and `story.js`. The build reads daily values from the original Fabric chart rather than
maintaining a second dataset. Changed chapter structure or evidence contracts fail the build or tests.

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
both themes, keyboard controls, image zoom and Escape, reduced motion, and the article with JavaScript disabled.
Stop the preview server after use. The Markdown and answer table remain readable without JavaScript.

## Publish

The [Pages workflow](../.github/workflows/story-pages.yml) builds and tests changes on `main`, then publishes
only `site/dist` through GitHub Pages. GitHub Pages must use **GitHub Actions** as its publishing source.
The workflow can also be dispatched manually. Do not commit generated output or publish the repository root.

The [companion runbook](../docs/29-data-agent-companion.md) owns actual Fabric execution and capability gates.
Browser exercises do not turn an unverified or blocked platform feature into a passed demonstration.
