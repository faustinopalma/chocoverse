import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { coverDays, coverOptions, supportedGrain, assessClaim } from "../learning.js";

test("all 32 stock-policy selections follow the unique-value rule", () => {
  for (let mask = 0; mask < 32; mask++) {
    const values = coverOptions.filter((_, index) => mask & (1 << index));
    assert.equal(coverDays(values), values.length === 1 ? values[0] : 3);
  }
  assert.equal(coverDays([5, 7]), 3);
  assert.equal(coverDays([2, 2]), 2);
  assert.throws(() => coverDays([9]), TypeError);
  assert.throws(() => coverDays(null), TypeError);
});

test("grain support never allocates cash or production to unsupported dimensions", () => {
  assert.deepEqual(supportedGrain("company"), { sales: true, production: true, cash: true });
  assert.deepEqual(supportedGrain("product"), { sales: true, production: true, cash: false });
  assert.deepEqual(supportedGrain("slice"), { sales: true, production: false, cash: false });
  assert.throws(() => supportedGrain("__proto__"), TypeError);
});

test("only the evidence-backed briefing claim is accepted", () => {
  assert.equal(assessClaim("A").correct, true);
  assert.equal(assessClaim("B").correct, false);
  assert.equal(assessClaim("C").correct, false);
  assert.throws(() => assessClaim("unknown"), TypeError);
});

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
test("built publication contains only explicit static files and public evidence", async () => {
  const dir = path.join(site, "dist");
  const files = await readdir(dir);
  assert.deepEqual(files.sort(), [".nojekyll", "assets", "index.html", "learning.js", "story.js", "style.css"]);
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
  assert.equal((html.match(/class="lab"/g) ?? []).length, 5);
  assert.equal((html.match(/data-zoom/g) ?? []).length, 7);
  assert.ok(!html.includes("{{"));
  assert.ok(!html.includes(".local/"));
  assert.ok(!html.includes("The Road Ahead"));
  assert.ok(!html.includes("[commercial-answer]"));
  assert.ok(!html.includes("src=\"https://"));
  assert.ok(!html.includes("fictional"));
  const data = JSON.parse(html.match(/<script id="daily-data" type="application\/json">(.+)<\/script>/)[1]);
  assert.equal(data.length, 31);
  assert.deepEqual(data[0], { day: 1, kg: 415 });
  assert.deepEqual(data[15], { day: 16, kg: 411 });
  assert.deepEqual(data[30], { day: 31, kg: 398 });
  for (const [index, point] of data.entries()) assert.equal(point.day, index + 1);
  for (const [, url] of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
    assert.ok(!url.includes("\\"));
    if (url.startsWith("#")) assert.ok(html.includes(`id="${url.slice(1)}"`), url);
    else if (!url.startsWith("https://")) await readFile(path.join(dir, url));
    else if (url.startsWith("https://github.com/faustinopalma/chocoverse/blob/main/")) {
      const relative = url.split("/blob/main/")[1].split("#")[0];
      await readFile(path.join(site, "..", relative));
    }
  }
  for (const fact of ["1,252.7", "-0.3069", "3,435,099.60", "unverified", "blocked"]) {
    assert.ok(html.includes(fact), fact);
  }
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
