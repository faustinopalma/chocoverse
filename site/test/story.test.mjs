import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const root = path.dirname(site);
const recordPath = path.join(root, "docs", "data-agent-recovery-evidence.json");
const sha256 = value => createHash("sha256").update(value).digest("hex");
const pointLabels = svg => [...svg.matchAll(/<[^>]+aria-roledescription="point"[^>]*>/g)]
  .map(([tag]) => {
    const label = tag.match(/aria-label="([^"]+)"/)?.[1];
    assert.ok(label, tag);
    return label;
  });

test("publication contains only explicit static files and the recovery evidence", async () => {
  const dir = path.join(site, "dist");
  assert.deepEqual((await readdir(dir)).sort(), [".nojekyll", "assets", "index.html", "story.js", "style.css"]);
  const assets = (await readdir(path.join(dir, "assets"))).sort();
  assert.deepEqual(assets, ["recovery-backlog.png", "recovery-flow.png",
    "recovery-history.svg", "recovery-sales.png"]);
  const html = await readFile(path.join(dir, "index.html"), "utf8");
  const referenced = [...new Set([...html.matchAll(/(?:href|src)="assets\/([^"]+)"/g)].map(([, name]) => name))].sort();
  assert.deepEqual(assets, referenced);
  assert.ok(!/<p>\s*<figure/.test(html));
  assert.equal((html.match(/<img src="[^"]+"[^>]* width="\d+" height="\d+"/g) ?? []).length, 4);
  assert.equal((html.match(/class="chapter"/g) ?? []).length, 4);
  assert.equal((html.match(/<figcaption>/g) ?? []).length, 4);
  assert.equal((html.match(/data-zoom/g) ?? []).length, 4);
  for (let index = 1; index <= 4; index++) assert.ok(html.includes(`Exhibit 0${index}`));
  for (const privateText of ["{{", ".local/", "The Road Ahead", "Deck Pomeriggio", 'src="https://']) {
    assert.ok(!html.includes(privateText), privateText);
  }
  for (const [, url] of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
    assert.ok(!url.includes("\\"));
    if (url.startsWith("#")) assert.ok(html.includes(`id="${url.slice(1)}"`), url);
    else if (!url.startsWith("https://")) await readFile(path.join(dir, url.split("?")[0]));
    else if (url.startsWith("https://github.com/faustinopalma/chocoverse/blob/main/")) {
      await readFile(path.join(root, url.split("/blob/main/")[1].split("#")[0]));
    }
  }
  for (const fact of ["227.2 kg/day", "404.9 kg/day", "983.0 kg", "533.3 kg", "121 observed dates", "3 March 2048"]) {
    assert.ok(html.includes(fact), fact);
  }
  assert.ok(!/inventory review|7 of 30|24–26 August|rendered exports/i.test(html));
});

test("the archived 3D artwork is retained but excluded from the minisite", async () => {
  const dir = path.join(site, "dist");
  const html = await readFile(path.join(dir, "index.html"), "utf8");
  assert.ok(!/model-viewer|world-3d|chocoverse\.glb/.test(html));
  const bytes = await readFile(path.join(site, "art", "chocoverse.glb"));
  assert.ok(bytes.length < 3 * 1024 * 1024, "Keep the model below 3 MiB");
  assert.equal(bytes.toString("ascii", 0, 4), "glTF");
  assert.equal(bytes.readUInt32LE(4), 2);
  assert.equal(bytes.readUInt32LE(8), bytes.length);
  const json = JSON.parse(bytes.toString("utf8", 20, 20 + bytes.readUInt32LE(12)));
  assert.ok(json.meshes.length > 30, "Publish geometry, not a textured poster plane");
  assert.ok(json.nodes.some(node => node.name === "GIANDORIA"));
  assert.ok(json.nodes.some(node => node.name === "CHOCOVERSE"));
  for (const item of [...(json.buffers ?? []), ...(json.images ?? [])]) assert.ok(!item.uri);
  assert.ok(!json.extensionsRequired?.includes("KHR_draco_mesh_compression"));
  const script = await readFile(path.join(dir, "story.js"), "utf8");
  assert.ok(!/model-viewer|initializeWorld|chocoverse\.glb/.test(script));
});

test("each question follows a concrete decision purpose and precedes its captured answer", async () => {
  const html = await readFile(path.join(site, "dist", "index.html"), "utf8");
  assert.equal((html.match(/<blockquote>/g) ?? []).length, 3);
  const purposes = [
    "Operations first needs to identify which product sales fell during the supply disruption",
    "Operations now needs to check whether the factory is supplying the products behind the sales change.",
    "what has happened to orders still waiting to be shipped?",
  ];
  for (let number = 1; number <= 3; number++) {
    const section = html.match(new RegExp(`<section class="chapter" id="chapter-${number}"[\\s\\S]+?</section>`))?.[0];
    assert.ok(section);
    assert.ok(section.indexOf(purposes[number - 1]) >= 0);
    assert.ok(section.indexOf(purposes[number - 1]) < section.indexOf("<blockquote>"));
    assert.ok(section.indexOf("<blockquote>") < section.indexOf("<figure"));
  }
  assert.ok(html.includes("same input above"));
  assert.ok(html.includes("backlog in blue and finished stock in magenta"));
  const chart = html.match(/<figure class="evidence"><ul class="chart-legend"[\s\S]+?<\/figure>/)?.[0];
  assert.ok(chart?.includes("recovery-history.svg"));
  assert.ok(chart.includes('aria-label="Chart legend"'));
  assert.ok(chart.includes(">Backlog</li>") && chart.includes(">Finished stock</li>"));
  const styles = await readFile(path.join(site, "dist", "style.css"), "utf8");
  assert.match(styles, /\.backlog-key\s*\{\s*border-color: #637cef;/);
  assert.match(styles, /\.stock-key\s*\{\s*border-color: #e3008c;/);
  assert.ok(html.includes("complete responses and checked figures"));
  assert.ok(!/\[F\d+(?:,\s*F\d+)*\]/.test(html));
  const sources = html.slice(html.indexOf("<h2>Sources</h2>"), html.indexOf("Closing note"));
  assert.ok(sources.includes("verification limits"));
  assert.ok(!/Topics retrieval|M365 feedback|authoring-mode|Code Interpreter/.test(sources));
  const closing = html.slice(html.indexOf("Closing note"));
  for (const phrase of ["reliable supply across its channels", "Real-Time Dashboards", "Lakehouse", "Power BI",
    "Data Agent", "Decision Room", "technical guide"]) {
    assert.ok(closing.includes(phrase), phrase);
  }
});

test("the opening sets the event and questions without revealing the analytical answers", async () => {
  const source = await readFile(path.join(root, "docs", "data-agent-story.md"), "utf8");
  const opening = source.slice(0, source.indexOf("## 1."));
  for (const phrase of ["In September 2047, Giandoria expands its supermarket and export channels.",
    "an unexpected equipment", "malfunction requires unplanned maintenance on the moulding line",
    "Giandoria adds shifts in late December.",
    "is Giandoria supplying its customers again?", "How did sales fare during the disruption?",
    "Have shipments recovered?", "Are orders still waiting to be shipped?", "Let's ask a Fabric Data Agent",
    "September, before maintenance", "November, during the reduced-capacity period",
    "February, after the additional shifts"]) {
    assert.ok(opening.includes(phrase), phrase);
  }
  assert.ok(!opening.includes("create a supply-recovery review"));
  assert.ok(!/\bkg\b|1,119|983\.0|533\.3|404\.9|227\.2|260|780|closes at|has recovered/i.test(opening),
    "Introduce the setting and questions, leaving quantities and conclusions to the answers");
  const firstQuestion = source.slice(source.indexOf("## 1."), source.indexOf("**Recorded input"));
  assert.ok(firstQuestion.includes("during the supply disruption"),
    "Frame sales as commercial symptoms of the supply disruption, not a demand investigation");
  assert.ok(firstQuestion.includes("not a measure of underlying demand"));
  assert.ok(firstQuestion.includes("availability can limit what customers can buy"));
  assert.ok(!source.includes("How have customer purchases evolved?"));
  assert.ok(!source.includes("after the restriction"));
  const scenario = JSON.parse(await readFile(path.join(root, "config", "scenarios",
    "channel-expansion-maintenance.json"), "utf8"));
  const maintenance = scenario.changes.find(change => change.id === "moulding-maintenance");
  assert.match(maintenance.reason, /Unexpected equipment malfunction requires unplanned maintenance/);
  assert.equal(maintenance.tick, 152544);
  assert.deepEqual(maintenance.line_capacity_kg, { moulding: 260 });
  const html = await readFile(path.join(site, "dist", "index.html"), "utf8");
  assert.ok(!/simulat/i.test(html), "Keep simulation labels out of the reader-facing story");
  assert.ok(!/virtual time|reduced-detail runtime|Pause it, resume it|fictional|not real/i.test(html),
    "Preserve the business world's narrative immersion through the closing note");
});

test("the standalone opening introduces Giandoria and the connected business before the recovery review", async () => {
  const html = await readFile(path.join(site, "dist", "index.html"), "utf8");
  const context = html.match(/<section class="company-context"[\s\S]+?<\/section>/)?.[0];
  assert.ok(context);
  for (const phrase of ["established Italian chocolate maker", "Chocoverse", "suppliers", "planners",
    "factory teams", "logistics partners", "customers", "Finance", "Microsoft Fabric",
    "Customer orders, shared forecasts and sales information feed back into demand planning"]) {
    assert.ok(context.includes(phrase), phrase);
  }
  assert.ok(!/<(?:ol|ul|li)\b/.test(context), "Keep the introduction compact, without value-chain cards");
  assert.ok(html.indexOf(context) < html.indexOf("This recovery review"));
  assert.ok(!/<(?:img|script|iframe)\b/.test(context), "The value chain must remain readable without image or script loading");
  const title = "Investigating Giandoria's supply recovery with a Fabric Data Agent";
  assert.ok(html.includes(`<title>${title}</title>`));
  assert.ok(html.includes(`<h1>${title}</h1>`));
});

test("the operational conclusion is bounded, visible and usable without scripts", async () => {
  const html = await readFile(path.join(site, "dist", "index.html"), "utf8");
  assert.ok(!/<(?:input|select|form|progress)\b/.test(html));
  assert.match(html, /style\.css\?v=[a-f0-9]{12}/);
  assert.match(html, /story\.js\?v=[a-f0-9]{12}/);
  const conclusion = html.match(/<section class="chapter" id="chapter-4"[\s\S]+?<\/section>/)?.[0];
  assert.ok(conclusion);
  for (const phrase of ["What the investigation tells us", "milk chocolate sales recover only part",
    "404.9 kg/day", "397.2 kg/day", "533.3 kg in February", "monthly average",
    "natural-language questions", "uneven recovery"]) {
    assert.ok(conclusion.includes(phrase), phrase);
  }
  assert.ok(!/\shidden(?:\s|=|>)|<details|<button/.test(conclusion));
  assert.ok(!/increase production|lost sales were|missed deliveries were|ranked products/i.test(conclusion));
  assert.ok(!/still needs to check|next operational check|checkpoint|<table/i.test(conclusion));
  assert.ok(html.includes("cannot separate the effects of capacity and demand"));
  const script = await readFile(path.join(site, "dist", "story.js"), "utf8");
  assert.ok(!/chapter-copy|fetch\(|localStorage|sessionStorage/.test(script));
});

test("verbatim inputs, source-row oracles and real captures retain their provenance", async () => {
  const source = await readFile(path.join(root, "docs", "data-agent-story.md"), "utf8");
  const record = JSON.parse(await readFile(recordPath, "utf8"));
  const inputs = [...source.matchAll(/(?:^>[^\r\n]*(?:\r?\n|$))+/gm)]
    .map(([text]) => text.replace(/^>\s?/gm, "").replace(/\s+/g, " ").trim());
  assert.equal(record.snapshotThroughDate, "2048-03-03");
  assert.deepEqual(inputs, record.exchanges.map(exchange => exchange.input));
  assert.deepEqual(inputs.map(sha256), record.exchanges.map(exchange => exchange.inputSha256));
  assert.equal(record.exchanges[0].expected.length, 9);
  assert.equal(record.exchanges[1].expected.length, 3);
  assert.deepEqual(record.exchanges[1].expected.map(row => row.days), [30, 30, 29]);
  assert.deepEqual(record.exchanges[2].expected.months.map(row => row.observed_dates), [30, 29]);
  assert.equal(record.exchanges[2].expected.daily.length, 121);
  assert.match(record.exchanges[0].answer, /211\.5[\s\S]*147\.6[\s\S]*227\.2/);
  assert.match(record.exchanges[1].answer, /253\.1/);
  assert.match(record.exchanges[2].answer, /533\.3/);
  for (const exchange of record.exchanges) {
    assert.equal(exchange.verification, "Matched source-row oracle");
    const image = await readFile(path.join(root, "docs", "images", "data-agent-story", exchange.screenshot));
    assert.equal(sha256(image), exchange.screenshotSha256);
    assert.equal(image.subarray(1, 4).toString(), "PNG");
  }
  assert.ok(source.trim().split(/\s+/).length <= 1200, "Keep the full reading path within 1,200 words");
  const review = source.slice(source.indexOf("## This recovery review"), source.indexOf("## Sources"));
  assert.ok(review.trim().split(/\s+/).length <= 850, "Keep the investigation concise alongside the standalone context");
  const guide = await readFile(path.join(root, "docs", "29-data-agent-companion.md"), "utf8");
  assert.ok(guide.includes("/blob/1e7022f/docs/data-agent-story.md"));
  assert.ok(guide.includes("/blob/3e0642d/docs/data-agent-story.md"));
});

test("the native recovery chart retains every date and both source-checked balance series", async () => {
  const svg = await readFile(path.join(site, "dist", "assets", "recovery-history.svg"), "utf8");
  const record = JSON.parse(await readFile(recordPath, "utf8"));
  assert.equal(sha256(svg), record.chart.sha256);
  assert.equal(record.chart.points.length, 242);
  assert.equal((svg.match(/aria-roledescription="point"/g) ?? []).length, 242);
  const labels = pointLabels(svg);
  assert.deepEqual(labels, record.chart.points.map(point => point.label));
  const expected = record.exchanges[2].expected.daily;
  for (const series of ["FinishedKg", "BacklogKg"]) {
    const actual = record.chart.points.filter(point => point.series === series);
    assert.equal(actual.length, 121);
    assert.deepEqual(actual.map(point => [point.date, point.kg]),
      expected.map(row => [row.date, row[series === "FinishedKg" ? "finished_kg" : "backlog_kg"]]));
  }
});

test("the archived native inventory chart retains its independently checked recurrence", async () => {
  const svg = await readFile(path.join(root, "docs", "images", "data-agent-story", "inventory-history.svg"), "utf8");
  const labels = pointLabels(svg).map(label => {
    const match = label.match(/Observation date: ([A-Za-z]+ \d{2}); Closing balance \(kg\): (\d+); series: (FinishedKg|BacklogKg);/);
    assert.ok(match, label);
    return { date: match[1], kg: Number(match[2]), series: match[3] };
  });
  assert.equal(labels.length, 60);
  const stock = labels.filter(point => point.series === "FinishedKg");
  const backlog = labels.filter(point => point.series === "BacklogKg");
  assert.deepEqual(stock.map(point => point.kg), [
    0, 114, 111, 176, 146, 85, 77, 223, 238, 129, 339, 496, 499, 488, 508,
    42, 0, 9, 51, 0, 0, 0, 2, 0, 11, 16, 30, 35, 15, 0,
  ]);
  assert.deepEqual(backlog.map(point => point.kg), [
    417, 90, 280, 76, 256, 85, 84, 161, 49, 6, 0, 0, 0, 0, 0,
    0, 76, 12, 0, 371, 395, 402, 18, 40, 0, 42, 0, 0, 3, 37,
  ]);
  assert.equal(stock.filter((point, i) => point.kg === 0 && backlog[i].kg > 0).length, 7);
});

test("the archived native sales chart retains all 31 captured values", async () => {
  const svg = await readFile(path.join(root, "docs", "images", "data-agent-story", "native-chart.svg"), "utf8");
  const points = pointLabels(svg).map(label => {
    const match = label.match(/Virtual date: Aug (\d{2}), 2034; Sold kg: (\d+)/);
    assert.ok(match, label);
    return { day: Number(match[1]), kg: Number(match[2]) };
  });
  assert.deepEqual(points.map(point => point.day), Array.from({ length: 31 }, (_, i) => i + 1));
  assert.deepEqual(points.map(point => point.kg), [
    415, 395, 400, 396, 430, 438, 452, 399, 384, 416, 381, 398, 440, 451, 409, 411,
    404, 416, 387, 466, 454, 407, 390, 422, 419, 399, 447, 437, 402, 410, 398,
  ]);
});

test("rebuilding removes stale artifacts and preserves the generated story", async () => {
  const dir = path.join(site, "dist");
  const before = await readFile(path.join(dir, "index.html"), "utf8");
  const stale = path.join(dir, "assets", "stale-evidence.png");
  await writeFile(stale, "This file must never survive a new build.");
  execFileSync(process.execPath, [path.join(site, "build.mjs")]);
  await assert.rejects(readFile(stale), { code: "ENOENT" });
  assert.equal(await readFile(path.join(dir, "index.html"), "utf8"), before);
});
