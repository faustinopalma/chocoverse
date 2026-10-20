# Screenshot guide

These images accompany the [Chocoverse illustrated introduction](../../../README.md).
They are captures of the authenticated laboratory, not fabricated business results or generated UI mockups.
The company and business data are synthetic.

## Additional views

| View | What to notice |
|---|---|
| [Live finance](./live-finance.png) | Cash is a balance; revenue, purchases and conversion are posting flows |
| [Shared semantic model](./semantic-model.png) | One-way fact/dimension relationships and disconnected helper tables |
| [Unfiltered calendar](./report-calendar.png) | Multiple virtual years, rolling comparisons and the optional reading guide |
| [Filtered calendar](./report-calendar-filtered.png) | A complete-year selection changes the narrative and visual context |
| [Commercial mix](./report-mix.png) | Channel/product composition, not product-level financial allocation |
| [Territory](./report-territory.png) | Virtual calendar and territory/weekday exploration |
| [Flows versus stocks](./report-flows.png) | Different physical flows and semi-additive inventory |
| [Cash versus revenue](./report-cash.png) | Recognized revenue is not cash movement; purchases are not automatically COGS |
| [Default cover policy](./report-stock.png) | The default three-day arithmetic scenario |
| [Four-day cover policy](./report-stock-four-days.png) | A parameter changes the illustrative target, not the running company |
| [Ontology instances](./ontology-instances.png) | Actual bound rows with date/channel/product/territory identity |
| [OneLake snapshot](./lakehouse-snapshot.png) | The immutable Delta source behind the ontology's business instances |
| [Hosted investigation](./decision-investigation.png) | An actual AI answer, labelled as such and tied to the fixed snapshot |
| [Private journal](./decision-journal.png) | A clearly labelled synthetic review with evidence, question and reasoning |
| [Dark theme](./decision-dark.png) | The same enterprise evidence and framework components in the alternate theme |

The temporary showcase review was removed after verifying persistence, verdict update and confirmed deletion.
Its screenshot demonstrates the workflow, not a current business approval.
No other review was removed, and no review changed the simulation.

## Capture and publication method

Use [Save-LabScreenshot.ps1](../../../ops/Save-LabScreenshot.ps1) with an already authenticated,
fully rendered page in **Edge LaQuantistica**:

```powershell
.\ops\Save-LabScreenshot.ps1 `
    -DocumentName 'Giandoria Decision Room' `
    -ExpectedText 'Virtual data through' `
    -OutputPath '.\docs\images\showcase\decision-inbox.png'
```

The script verifies the window/profile, exact visible document title and expected feature text.
It captures that window with `PrintWindow` and crops to the document, without a desktop-capture fallback.
For Fabric portal pages, `-CropTop 56` removes the global account header in the observed desktop layout;
inspect the result because viewport scale and portal layout can change.
Optional `CropLeft`, `CropRight` and `CropBottom` offsets remove unused framing without altering chart data.

Review the **actual image**, not only its accessibility tree: loading documents can briefly expose stale text,
and tutorials, tooltips or dialogs can obscure the feature. Confirm the data is rendered, the snapshot/live
contract is visible or explained by its caption, and there are no account details, tenant URLs or secrets.
Cropping is presentation/privacy hygiene, not evidence that an underlying tenant can be made public.

Business values remain unchanged. No number, chart, AI answer or error state is painted over or substituted.
Images reflect the observed product experience; filters, page framing and preview notices are not mockups.
Technical health screens, raw command output and deployment identities stay in ignored local evidence.

When replacing images, exercise the relevant feature first, compare measured outputs with their governed
source and retain bounded operational evidence in the command journal. Do not publish raw inference traces,
credentials, private reviews from other users or unrelated browser tabs.
