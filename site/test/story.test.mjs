import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
test("built publication contains only explicit static files and public evidence", async () => {
  const dir = path.join(site, "dist");
  const files = await readdir(dir);
  assert.deepEqual(files.sort(), [".nojekyll", "assets", "index.html", "story.js", "style.css"]);
  const assets = await readdir(path.join(dir, "assets"));
  assert.ok(assets.length >= 7);
  assert.ok(assets.every((name) => /^[a-z0-9-]+\.(png|svg)$/.test(name)));
  const html = await readFile(path.join(dir, "index.html"), "utf8");
  const referencedAssets = [...new Set([...html.matchAll(/(?:href|src)="assets\/([^"]+)"/g)]
    .map(([, name]) => name))].sort();
  assert.deepEqual(assets.sort(), referencedAssets);
  assert.ok(!/<p>\s*<figure/.test(html));
  assert.equal((html.match(/<img src="[^"]+"[^>]* width="\d+" height="\d+"/g) ?? []).length, 7);
  assert.equal((html.match(/class="chapter"/g) ?? []).length, 7);
  assert.equal((html.match(/<figcaption>/g) ?? []).length, 7);
  for (let index = 1; index <= 7; index++) assert.ok(html.includes(`Exhibit 0${index}`));
  assert.equal((html.match(/data-zoom/g) ?? []).length, 7);
  assert.ok(!html.includes("{{"));
  assert.ok(!html.includes(".local/"));
  assert.ok(!html.includes("The Road Ahead"));
  assert.ok(!html.includes("[commercial-answer]"));
  assert.ok(!html.includes("src=\"https://"));
  for (const [, url] of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
    assert.ok(!url.includes("\\"));
    if (url.startsWith("#")) assert.ok(html.includes(`id="${url.slice(1)}"`), url);
    else if (!url.startsWith("https://")) await readFile(path.join(dir, url.split("?")[0]));
    else if (url.startsWith("https://github.com/faustinopalma/chocoverse/blob/main/")) {
      const relative = url.split("/blob/main/")[1].split("#")[0];
      await readFile(path.join(site, "..", relative));
    }
  }
  for (const fact of ["82 kg", "1,994 kg", "4.11%", "1,252.7", "-0.3069", "3,435,099.60", "unverified", "blocked"]) {
    assert.ok(html.includes(fact), fact);
  }
});

test("captured outputs have readable inputs and named documentation sources", async () => {
  const html = await readFile(path.join(site, "dist", "index.html"), "utf8");
  assert.equal((html.match(/<blockquote>/g) ?? []).length, 7);
  const sections = [...html.matchAll(/<section class="chapter" id="chapter-(\d)"[\s\S]+?<\/section>/g)];
  for (const [section, number] of sections) {
    if (section.includes("<figure")) {
      assert.ok(section.indexOf("<blockquote>") < section.indexOf("<figure"), `Chapter ${number} needs its input first`);
    }
  }
  assert.ok(html.includes("same commercial input above"));
  assert.match(html, /Topics retrieval remains unverified/);
  assert.ok(!/\[F\d+(?:,\s*F\d+)*\]/.test(html));
  for (const path of ["concept-data-agent", "data-agent-runtime", "data-agent-visuals", "data-agent-code-interpreter"]) {
    assert.ok(html.includes(`https://learn.microsoft.com/en-us/fabric/data-science/${path}`));
  }
  assert.ok(html.includes('href="https://github.com/faustinopalma/chocoverse"'));
  const closing = html.slice(html.indexOf("Closing note"));
  for (const phrase of ["virtual time", "Real-Time Dashboards", "Lakehouse", "Power BI", "Data Agent",
    "Decision Room", "explicit extraction and publication", "reduced-detail", "incur charges"]) {
    assert.ok(closing.includes(phrase), phrase);
  }
});

test("the recommendation precedes supplementary demos and remains readable without scripts", async () => {
  const html = await readFile(path.join(site, "dist", "index.html"), "utf8");
  assert.ok(!/<(?:input|select|form|progress)\b/.test(html));
  assert.match(html, /style\.css\?v=[a-f0-9]{12}/);
  assert.match(html, /story\.js\?v=[a-f0-9]{12}/);
  assert.ok(!/quiz|exercise|data-claim|answer-key|learning\.js|Your turn/i.test(html));
  const conclusion = html.match(/<section class="chapter" id="chapter-4"[\s\S]+?<\/section>/)?.[0];
  assert.ok(conclusion);
  for (const text of ["Prepare a bounded pilot proposal", "Launch it once",
    "Commercial value", "Supply feasibility", "Cash exposure", "budget, duration and success criteria",
    "conditional on the pilot", "rather than provide the missing launch evidence"]) {
    assert.ok(conclusion.includes(text), text);
  }
  assert.ok(!/\shidden(?:\s|=|>)|<details|<button/.test(conclusion));
  assert.ok(conclusion.includes("unavailable at the requested campaign detail"));
  for (const index of [5, 6, 7]) {
    assert.match(html, new RegExp(`<h2 id="heading-${index}">Further analysis:`));
    assert.ok(html.indexOf('id="chapter-4"') < html.indexOf(`id="chapter-${index}"`));
  }
  const script = await readFile(path.join(site, "dist", "story.js"), "utf8");
  assert.ok(!/chapter-copy|chapter-8|fetch\(|localStorage|sessionStorage/.test(script));
});

test("editing preserves the seven recorded inputs and a concise reading path", async () => {
  const source = await readFile(path.join(site, "..", "docs", "data-agent-story.md"), "utf8");
  const inputs = [...source.matchAll(/(?:^>[^\r\n]*(?:\r?\n|$))+/gm)]
    .map(([text]) => text.replace(/^>\s?/gm, "").replace(/\s+/g, " ").trim()).sort();
  const hashes = inputs.map((text) => createHash("sha256").update(text).digest("hex"));
  assert.deepEqual(hashes, [
    "114d2d5affed3d137125e7aa95903d2cdecd6446fe84f9aa48950a2ba8742b7a",
    "2ea70b637f61713d8b3af469229f3453af49325657ceb7b8bd3cdf996034adc4",
    "3e3cf1575b31a7e470f3fc78dda4326cac64aea231edfcdf1ed5c3a1fec21426",
    "972e8c3cc641239bde8d2789efab38c794584b6b5a98c6080c5de523d76a1a44",
    "7ffbead00cb10c131efbeb19efecc15bda152eccdd1e5a1fefdfd84ce001b1dc",
    "9762ae4789b9cecc18b46df2e672698261d357944d471a81d5cc10168696cddc",
    "c433f170967a82800d752c7961d1058f2cd25a60043b0f45754b7183f82f73a6",
  ]);
  assert.ok(source.trim().split(/\s+/).length <= 1600, "Keep the full reading path within 1,600 words");
  const decisionPath = source.slice(0, source.indexOf("## 5."));
  assert.ok(decisionPath.trim().split(/\s+/).length <= 750, "Keep the decision path within 750 words");
});

test("the original native chart retains all 31 captured daily values", async () => {
  const svg = await readFile(path.join(site, "dist", "assets", "native-chart.svg"), "utf8");
  const points = [...svg.matchAll(/<[^>]+aria-roledescription="point"[^>]*>/g)].map(([mark]) => {
    const [, day, kg] = mark.match(/aria-label="Virtual date: Aug (\d{2}), 2034; Sold kg: (\d+)"/);
    return { day: Number(day), kg: Number(kg) };
  });
  assert.deepEqual(points.map(({ day }) => day), Array.from({ length: 31 }, (_, index) => index + 1));
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
