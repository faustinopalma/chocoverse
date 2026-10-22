import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const root = path.dirname(site);
test("publication contains only explicit static files and the new investigation evidence", async () => {
  const dir = path.join(site, "dist");
  assert.deepEqual((await readdir(dir)).sort(), [".nojekyll", "assets", "index.html", "story.js", "style.css"]);
  const assets = await readdir(path.join(dir, "assets"));
  assert.deepEqual(assets.sort(), [
    "inventory-detail.png", "inventory-history.svg", "inventory-persistence.png", "inventory-position.png",
  ]);
  const html = await readFile(path.join(dir, "index.html"), "utf8");
  const referencedAssets = [...new Set([...html.matchAll(/(?:href|src)="assets\/([^"]+)"/g)]
    .map(([, name]) => name))].sort();
  assert.deepEqual(assets, referencedAssets);
  assert.ok(!/<p>\s*<figure/.test(html));
  assert.equal((html.match(/<img src="[^"]+"[^>]* width="\d+" height="\d+"/g) ?? []).length, 4);
  assert.equal((html.match(/class="chapter"/g) ?? []).length, 4);
  assert.equal((html.match(/<figcaption>/g) ?? []).length, 4);
  for (let index = 1; index <= 4; index++) assert.ok(html.includes(`Exhibit 0${index}`));
  assert.equal((html.match(/data-zoom/g) ?? []).length, 4);
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
  for (const fact of ["0 kg", "37 kg", "7 of 30", "24–26 August", "unverified", "blocked"]) {
    assert.ok(html.includes(fact), fact);
  }
  assert.ok(!/campaign expansion|bounded pilot|campaign sales|Commercial review/i.test(html));
});

test("every captured answer follows its exact recorded input and a useful question purpose", async () => {
  const html = await readFile(path.join(site, "dist", "index.html"), "utf8");
  assert.equal((html.match(/<blockquote>/g) ?? []).length, 3);
  const purposes = [
    "Operations first needs the latest recorded finished stock and backlog.",
    "We therefore examine the preceding 30 days.",
    "Operations now needs to identify which products require attention.",
  ];
  for (let number = 1; number <= 3; number++) {
    const section = html.match(new RegExp(`<section class="chapter" id="chapter-${number}"[\\s\\S]+?</section>`))?.[0];
    assert.ok(section);
    assert.ok(section.includes(purposes[number - 1]));
    assert.ok(section.indexOf(purposes[number - 1]) < section.indexOf("<blockquote>"));
    assert.ok(section.indexOf("<blockquote>") < section.indexOf("<figure"));
  }
  assert.ok(html.includes("same input above"));
  assert.ok(html.includes("rendered exports of the actual response text"));
  assert.ok(!/\[F\d+(?:,\s*F\d+)*\]/.test(html));
  for (const name of ["concept-data-agent", "data-agent-runtime", "data-agent-visuals", "data-agent-code-interpreter"]) {
    assert.ok(html.includes(`https://learn.microsoft.com/en-us/fabric/data-science/${name}`));
  }
  assert.ok(html.includes('href="https://github.com/faustinopalma/chocoverse"'));
  const closing = html.slice(html.indexOf("Closing note"));
  for (const phrase of ["virtual time", "Real-Time Dashboards", "Lakehouse", "Power BI", "Data Agent",
    "Decision Room", "explicit extraction and publication", "reduced-detail", "incur charges"]) {
    assert.ok(closing.includes(phrase), phrase);
  }
});

test("the conclusion stays within the evidence and is readable without scripts", async () => {
  const html = await readFile(path.join(site, "dist", "index.html"), "utf8");
  assert.ok(!/<(?:input|select|form|progress)\b/.test(html));
  assert.match(html, /style\.css\?v=[a-f0-9]{12}/);
  assert.match(html, /story\.js\?v=[a-f0-9]{12}/);
  assert.ok(!/quiz|exercise|data-claim|answer-key|learning\.js|Your turn/i.test(html));
  const conclusion = html.match(/<section class="chapter" id="chapter-4"[\s\S]+?<\/section>/)?.[0];
  assert.ok(conclusion);
  for (const text of ["Review the recurring stock-and-backlog condition", "before promising additional volume",
    "Check replenishment and allocation timing", "product-level usable stock, reservations and open orders",
    "replenishment lead times before confirming volume", "Operations retains the decision"]) {
    assert.ok(conclusion.includes(text), text);
  }
  assert.ok(!/\shidden(?:\s|=|>)|<details|<button/.test(conclusion));
  assert.ok(!/increase production|lost sales were|missed deliveries were|ranked products/i.test(conclusion));
  const script = await readFile(path.join(site, "dist", "story.js"), "utf8");
  assert.ok(!/chapter-copy|fetch\(|localStorage|sessionStorage/.test(script));
});

test("all three verbatim questions match the retained execution record and stay concise", async () => {
  const source = await readFile(path.join(root, "docs", "data-agent-story.md"), "utf8");
  const record = JSON.parse(await readFile(path.join(root, "docs", "data-agent-inventory-evidence.json"), "utf8"));
  const inputs = [...source.matchAll(/(?:^>[^\r\n]*(?:\r?\n|$))+/gm)]
    .map(([text]) => text.replace(/^>\s?/gm, "").replace(/\s+/g, " ").trim());
  assert.equal(record.snapshotThroughDate, "2034-09-03");
  assert.deepEqual(inputs, record.exchanges.map(exchange => exchange.input));
  assert.deepEqual(inputs.map(text => createHash("sha256").update(text).digest("hex")), [
    "7ab79926609e3d038d336370cdbd5b42f24577304c1a663cefc532f423883cfb",
    "4760c22f6d24d26a7e60b1739d4298ec78d81d28971f4bb00ad5871bf0b6edaf",
    "7d186300156777f3ec9ed1b2b9aa6229140854cd84e3f665a73f935185f9bf83",
  ]);
  assert.match(record.exchanges[0].answer, /Backlog \(observed\): 37 kg/);
  assert.match(record.exchanges[1].answer, /Observation count: 30 observed dates/);
  assert.match(record.exchanges[1].answer, /positive backlog: 7 observations/);
  assert.match(record.exchanges[2].answer, /cannot be derived.*observed inventory balances/);
  assert.ok(source.trim().split(/\s+/).length <= 1200, "Keep the full reading path within 1,200 words");
  assert.ok(source.slice(0, source.indexOf("## Evidence")).trim().split(/\s+/).length <= 800,
    "Keep the decision path within 800 words");
  const guide = await readFile(path.join(root, "docs", "29-data-agent-companion.md"), "utf8");
  assert.ok(guide.includes("## 29.5 Recorded capability tests"));
  assert.ok(guide.includes("/blob/3e0642d/docs/data-agent-story.md"), "Retain all seven earlier inputs and captures");
});

test("the new native chart retains both complete series and the independently checked recurrence", async () => {
  const svg = await readFile(path.join(site, "dist", "assets", "inventory-history.svg"), "utf8");
  const points = [...svg.matchAll(/<[^>]+aria-roledescription="point"[^>]*>/g)].map(([mark]) => {
    const match = mark.match(/aria-label="Observation date: ([A-Za-z]+ \d{2}); Closing balance \(kg\): (\d+); series: (FinishedKg|BacklogKg);/);
    assert.ok(match, mark);
    return { date: match[1], kg: Number(match[2]), series: match[3] };
  });
  const dates = Array.from({ length: 30 }, (_, i) => i < 27 ? `Aug ${String(i + 5).padStart(2, "0")}` :
    `Sep ${String(i - 26).padStart(2, "0")}`);
  const finished = points.filter(point => point.series === "FinishedKg");
  const backlog = points.filter(point => point.series === "BacklogKg");
  assert.equal(points.length, 60);
  for (const series of [finished, backlog]) assert.deepEqual(series.map(point => point.date), dates);
  assert.deepEqual(finished.map(point => point.kg), [
    0, 114, 111, 176, 146, 85, 77, 223, 238, 129, 339, 496, 499, 488, 508,
    42, 0, 9, 51, 0, 0, 0, 2, 0, 11, 16, 30, 35, 15, 0,
  ]);
  assert.deepEqual(backlog.map(point => point.kg), [
    417, 90, 280, 76, 256, 85, 84, 161, 49, 6, 0, 0, 0, 0, 0,
    0, 76, 12, 0, 371, 395, 402, 18, 40, 0, 42, 0, 0, 3, 37,
  ]);
  assert.equal(finished.filter((point, i) => point.kg === 0 && backlog[i].kg > 0).length, 7);
});

test("the archived native sales chart retains all 31 captured values", async () => {
  const svg = await readFile(path.join(root, "docs", "images", "data-agent-story", "native-chart.svg"), "utf8");
  const points = [...svg.matchAll(/<[^>]+aria-roledescription="point"[^>]*>/g)].map(([mark]) => {
    const [, day, kg] = mark.match(/aria-label="Virtual date: Aug (\d{2}), 2034; Sold kg: (\d+)"/);
    return { day: Number(day), kg: Number(kg) };
  });
  assert.deepEqual(points.map(({ day }) => day), Array.from({ length: 31 }, (_, i) => i + 1));
  assert.deepEqual(points.map(({ kg }) => kg), [
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
