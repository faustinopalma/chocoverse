import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
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
  assert.equal((html.match(/class="chapter"/g) ?? []).length, 8);
  assert.equal((html.match(/<figcaption>/g) ?? []).length, 7);
  for (let index = 1; index <= 7; index++) assert.ok(html.includes(`Exhibit 0${index}`));
  assert.equal((html.match(/data-zoom/g) ?? []).length, 7);
  assert.ok(!html.includes("{{"));
  assert.ok(!html.includes(".local/"));
  assert.ok(!html.includes("The Road Ahead"));
  assert.ok(!html.includes("[commercial-answer]"));
  assert.ok(!html.includes("src=\"https://"));
  assert.ok(!html.includes("fictional"));
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

test("the recommendation is readable in static HTML without questions or gated answers", async () => {
  const html = await readFile(path.join(site, "dist", "index.html"), "utf8");
  assert.ok(!/<(?:input|select|form|progress)\b/.test(html));
  assert.match(html, /style\.css\?v=[a-f0-9]{12}/);
  assert.match(html, /story\.js\?v=[a-f0-9]{12}/);
  assert.ok(!/quiz|exercise|data-claim|answer-key|learning\.js|Your turn/i.test(html));
  const conclusion = html.match(/<section class="chapter" id="chapter-8"[\s\S]+?<\/section>/)?.[0];
  assert.ok(conclusion);
  for (const text of ["Do not approve a broad expansion", "launch conditional",
    "Commercial value", "Supply feasibility", "Cash exposure", "No budget, duration or growth target",
    "expansion remains on hold"]) {
    assert.ok(conclusion.includes(text), text);
  }
  assert.ok(!/\shidden(?:\s|=|>)|<details|<button/.test(conclusion));
  const script = await readFile(path.join(site, "dist", "story.js"), "utf8");
  assert.ok(!/chapter-copy|chapter-8|fetch\(|localStorage|sessionStorage/.test(script));
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
