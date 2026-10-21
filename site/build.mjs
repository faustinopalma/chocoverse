import { readFile, writeFile, mkdir, copyFile, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";
import MarkdownIt from "markdown-it";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(here);
const output = path.join(here, "dist");
const sourcePath = path.join(root, "docs", "data-agent-story.md");
const source = await readFile(sourcePath, "utf8");
const github = "https://github.com/faustinopalma/chocoverse/blob/main/";
const assets = new Set();
const escape = (value) => MarkdownIt().utils.escapeHtml(value);
const references = source.match(/^\[[^\]]+\]:[^\r\n]+/gm)?.join("\n") ?? "";
const title = source.match(/^# (.+)\r?$/m)?.[1].trim();
const chapters = [...source.matchAll(/^## ([1-8])\. (.+)\r?$/gm)];
const footerStart = source.indexOf("## Evidence and further reading");
if (!title || chapters.length !== 8 || footerStart < 0) {
  throw new Error("The story must have a title, eight numbered chapters, and an evidence section.");
}
for (const [index, chapter] of chapters.entries()) {
  if (Number(chapter[1]) !== index + 1) throw new Error("Chapter order changed.");
}

function publicUrl(href) {
  if (/^https?:\/\//.test(href) || href.startsWith("#")) return href;
  const [name, fragment] = href.split("#");
  const resolved = path.resolve(path.dirname(sourcePath), name);
  const relative = path.relative(root, resolved).split(path.sep).join("/");
  if (relative.startsWith("../") || path.isAbsolute(relative)) throw new Error(`Unsafe link: ${href}`);
  if (relative.startsWith("docs/images/data-agent-story/")) {
    const filename = path.basename(resolved);
    if (!/^[a-z0-9-]+\.(png|svg)$/.test(filename)) throw new Error(`Unsupported asset: ${href}`);
    assets.add(filename);
    return `assets/${filename}`;
  }
  if (!relative.startsWith("docs/") && relative !== "README.md") throw new Error(`Unexpected link: ${href}`);
  return `${github}${relative}${fragment ? `#${fragment}` : ""}`;
}

const markdown = new MarkdownIt({ html: false, linkify: false });
const imageOnly = (token) => token?.type === "inline" && token.children?.length === 1
  && token.children[0].type === "image";
markdown.renderer.rules.paragraph_open = (tokens, index, options, env, renderer) =>
  imageOnly(tokens[index + 1]) ? "" : renderer.renderToken(tokens, index, options);
markdown.renderer.rules.paragraph_close = (tokens, index, options, env, renderer) =>
  imageOnly(tokens[index - 1]) ? "" : renderer.renderToken(tokens, index, options);
const linkOpen = markdown.renderer.rules.link_open ?? ((tokens, index, options, env, renderer) =>
  renderer.renderToken(tokens, index, options));
markdown.renderer.rules.link_open = (tokens, index, options, env, renderer) => {
  tokens[index].attrSet("href", publicUrl(tokens[index].attrGet("href")));
  return linkOpen(tokens, index, options, env, renderer);
};
markdown.renderer.rules.image = (tokens, index) => {
  const token = tokens[index];
  const src = publicUrl(token.attrGet("src"));
  const alt = escape(token.content);
  const bytes = readFileSync(path.join(root, "docs", "images", "data-agent-story", path.basename(src)));
  const dimensions = src.endsWith(".png")
    ? [bytes.readUInt32BE(16), bytes.readUInt32BE(20)]
    : ["width", "height"].map((name) => Number(bytes.toString().match(new RegExp(`<svg[^>]*\\b${name}="([\\d.]+)"`))?.[1]));
  if (dimensions.some((value) => !Number.isFinite(value) || value <= 0)) {
    throw new Error(`Missing image dimensions: ${src}`);
  }
  return `<figure class="evidence"><a class="capture" href="${src}" data-zoom aria-label="Enlarge: ${alt}">
    <img src="${src}" alt="${alt}" width="${dimensions[0]}" height="${dimensions[1]}" loading="lazy" decoding="async">
    <span class="capture-label">Fabric evidence <span aria-hidden="true">↗</span></span>
    </a></figure>`;
};
const render = (text) => markdown.render(`${text}\n\n${references}`);
const nativeChart = await readFile(path.join(root, "docs", "images", "data-agent-story", "native-chart.svg"), "utf8");
const daily = [...nativeChart.matchAll(/<[^>]+aria-roledescription="point"[^>]*>/g)].map(([mark]) => {
  const match = mark.match(/aria-label="Virtual date: Aug (\d{2}), 2034; Sold kg: (\d+)"/);
  if (!match) throw new Error("Unrecognized native chart point.");
  return { day: Number(match[1]), kg: Number(match[2]) };
});
if (daily.length !== 31 || daily.some((item, index) => item.day !== index + 1)) {
  throw new Error("The native chart must contain all 31 ordered August dates.");
}

const widget = (label, content) => `<aside class="lab" data-reveal>
  <p class="lab-label">Try the reasoning <span>Browser exercise · no live query</span></p>
  <h3>${label}</h3>${content}</aside>`;
const widgets = {
  2: widget("Choose the fair denominator", `
    <p>We have 82 kg of campaign sales. Which total belongs below that number?</p>
    <div class="choice-stack" data-comparison>
      <button type="button" data-answer="wide">All company sales, across products and territories</button>
      <button type="button" data-answer="fair">All channels, same product, territory and month</button>
    </div>
    <p class="feedback" id="comparison-feedback" role="status">Choose a comparison before reading the result.</p>
    <div class="share-result" hidden><strong>82 <span>/ 1,994 kg</span></strong><span>4.11%</span>
      <div class="share-track" aria-hidden="true"><span></span></div></div>`),
  4: widget("Two choices. Which rule wins?", `
    <p>Select cover days. A single selection uses that value; any other selection uses the published default.</p>
    <fieldset class="policy-options"><legend>Cover days</legend>
      ${[2, 3, 4, 5, 7].map((day) => `<label><input type="checkbox" value="${day}"
        ${day === 2 || day === 4 ? "checked" : ""}><span>${day} days</span></label>`).join("")}
    </fieldset>
    <div class="policy-result" role="status"><strong id="cover-value">3 days</strong>
      <p id="cover-reason">Two selections use the default. The observed three-day target is 1,252.7 kg.</p></div>
    <p class="small">This replays the selection rule. Other stock targets require a model query.
    Production is unchanged.</p>`),
  5: widget("Find the missing six days", `
    <p>Compare a 25-row preview with the full month. Then explore an individual day.</p>
    <label class="toggle-line"><input id="full-month" type="checkbox" checked> Include all 31 days</label>
    <div class="day-grid" aria-hidden="true">${daily.map(({ day, kg }) =>
      `<span class="day-cell" data-day="${day}" title="August ${day}: ${kg} kg">${day}</span>`).join("")}</div>
    <p id="coverage-status" role="status">31 of 31 days included. The month is complete.</p>
    <label for="day-slider">Inspect a day in the captured data</label>
    <input id="day-slider" type="range" min="1" max="31" value="31">
    <output id="day-value" for="day-slider">31 August · 398 kg</output>
    <p class="small">Values are read from the original Fabric chart below. This exercise runs locally.</p>`),
  7: widget("Change the grain, watch the boundary", `
    <label for="grain-select">Requested level of detail</label>
    <select id="grain-select">
      <option value="company">Whole company</option>
      <option value="product">One product</option>
      <option value="slice" selected>Product + channel + territory</option>
    </select>
    <div id="grain-result" class="grain-cards" role="status"></div>
    <p class="small">Supported means the recorded dimensions allow the calculation. It does not supply a new result.</p>`),
};
const claims = [...source.matchAll(/^\| ([ABC]) \| (.+?) \|\r?$/gm)];
if (claims.length !== 3) throw new Error("Expected the story's three briefing claims.");
const quiz = widget("Your signature goes on one sentence", `
  <div class="choice-stack" id="briefing-quiz">${claims.map(([, key, claim]) =>
    `<button type="button" data-claim="${key}"><span class="claim-letter">${key}</span>${escape(claim)}</button>`).join("")}
  </div><p id="quiz-feedback" class="feedback" role="status">Choose the sentence you can defend.</p>
  <div class="briefing-stamp" hidden><span aria-hidden="true">✓</span> Ready to brief: evidence before inference.</div>`);

const sectionHtml = chapters.map((chapter, index) => {
  const number = Number(chapter[1]);
  const end = chapters[index + 1]?.index ?? source.lastIndexOf("---", footerStart);
  let html = render(source.slice(chapter.index + chapter[0].length, end));
  if (widgets[number]) {
    if (!html.includes("<figure")) throw new Error(`Chapter ${number} lost its evidence image.`);
    html = html.replace("<figure", `${widgets[number]}<figure`);
  }
  if (number === 8) {
    html = html.replace("<table>", `${quiz}<table>`);
    html = html.replace(/<p><strong>A is supported<\/strong>[\s\S]*?<\/p>/,
      (answer) => `<div class="answer-key">${answer}</div>`);
  }
  return `<section class="chapter" id="chapter-${number}" data-step="${number}" aria-labelledby="heading-${number}">
    <div class="chapter-heading" data-reveal><span class="chapter-number" aria-hidden="true">${String(number).padStart(2, "0")}</span>
    <h2 id="heading-${number}">${escape(chapter[2].trim())}</h2></div>${html}
    ${number < 8 ? `<a class="next-chapter" href="#chapter-${number + 1}">Continue the investigation <span aria-hidden="true">↓</span></a>` : ""}
    </section>`;
}).join("\n");
const nav = chapters.map((chapter) => `<li><a href="#chapter-${chapter[1]}" data-nav="${chapter[1]}">
  <span>${chapter[1]}</span>${escape(chapter[2].trim())}</a></li>`).join("");
const template = await readFile(path.join(here, "shell.html"), "utf8");
const html = template.replace("{{TITLE}}", escape(title))
  .replace("{{INTRO}}", render(source.slice(source.indexOf("\n") + 1, chapters[0].index)))
  .replace("{{NAV}}", nav)
  .replace("{{CHAPTERS}}", sectionHtml)
  .replace("{{EVIDENCE}}", render(source.slice(footerStart)))
  .replace("{{DAILY}}", JSON.stringify(daily));
if (/\{\{[A-Z]+\}\}/.test(html)) throw new Error("Unfilled template field.");
await rm(output, { recursive: true, force: true });
await mkdir(path.join(output, "assets"), { recursive: true });
await writeFile(path.join(output, "index.html"), html);
await writeFile(path.join(output, ".nojekyll"), "");
for (const file of ["style.css", "story.js", "learning.js"]) {
  await copyFile(path.join(here, file), path.join(output, file));
}
for (const asset of assets) {
  await copyFile(path.join(root, "docs", "images", "data-agent-story", asset), path.join(output, "assets", asset));
}
console.log(`Built ${chapters.length} chapters, ${assets.size} public evidence assets, ${daily.length} checked dates.`);
