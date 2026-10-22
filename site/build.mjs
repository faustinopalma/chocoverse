import { readFile, writeFile, mkdir, copyFile, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import MarkdownIt from "markdown-it";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(here);
const output = path.join(here, "dist");
const sourcePath = path.join(root, "docs", "data-agent-story.md");
const source = await readFile(sourcePath, "utf8");
const github = "https://github.com/faustinopalma/chocoverse/blob/main/";
const assets = new Set();
let exhibit = 0;
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
  if (!relative.startsWith("docs/") && !["README.md", "infra/demo/README.md"].includes(relative)) {
    throw new Error(`Unexpected link: ${href}`);
  }
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
  return `<figure class="evidence"><a class="capture" href="${src}" data-zoom aria-label="View original evidence: ${alt}">
    <img src="${src}" alt="${alt}" width="${dimensions[0]}" height="${dimensions[1]}" loading="lazy" decoding="async">
    </a><figcaption><span class="exhibit-number">Exhibit ${String(++exhibit).padStart(2, "0")}</span>
    ${alt}</figcaption></figure>`;
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

const sectionHtml = chapters.map((chapter, index) => {
  const number = Number(chapter[1]);
  const end = chapters[index + 1]?.index ?? source.lastIndexOf("---", footerStart);
  const html = render(source.slice(chapter.index + chapter[0].length, end));
  return `<section class="chapter" id="chapter-${number}" aria-labelledby="heading-${number}" tabindex="-1">
    <header class="chapter-heading"><span class="chapter-number" aria-hidden="true">${String(number).padStart(2, "0")}</span>
    <h2 id="heading-${number}">${escape(chapter[2].trim())}</h2></header><div class="chapter-copy">${html}</div></section>`;
}).join("\n");
const nav = chapters.map((chapter) => `<li><a href="#chapter-${chapter[1]}" data-nav="${chapter[1]}">
  <span>${chapter[1]}</span>${escape(chapter[2].trim())}</a></li>`).join("");
const template = await readFile(path.join(here, "shell.html"), "utf8");
const assetVersion = async (filename) => createHash("sha256")
  .update((await readFile(path.join(here, filename), "utf8")).replace(/\r\n/g, "\n"))
  .digest("hex").slice(0, 12);
const html = template.replace("{{TITLE}}", escape(title))
  .replace("{{STYLE_VERSION}}", await assetVersion("style.css"))
  .replace("{{SCRIPT_VERSION}}", await assetVersion("story.js"))
  .replace("{{INTRO}}", render(source.slice(source.indexOf("\n") + 1, chapters[0].index)))
  .replace("{{NAV}}", nav)
  .replace("{{CHAPTERS}}", sectionHtml)
  .replace("{{EVIDENCE}}", render(source.slice(footerStart)));
if (/\{\{[A-Z]+\}\}/.test(html)) throw new Error("Unfilled template field.");
await rm(output, { recursive: true, force: true });
await mkdir(path.join(output, "assets"), { recursive: true });
await writeFile(path.join(output, "index.html"), html);
await writeFile(path.join(output, ".nojekyll"), "");
for (const file of ["style.css", "story.js"]) {
  await copyFile(path.join(here, file), path.join(output, file));
}
for (const asset of assets) {
  await copyFile(path.join(root, "docs", "images", "data-agent-story", asset), path.join(output, "assets", asset));
}
console.log(`Built ${chapters.length} chapters, ${assets.size} public evidence assets, ${daily.length} checked dates.`);
