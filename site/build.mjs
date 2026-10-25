import { readFile, writeFile, mkdir, copyFile, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import MarkdownIt from "markdown-it";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(here);
const output = path.join(here, "dist");
const assets = new Set();

async function buildEdition(language) {
  const italian = language === "it";
  const sourcePath = path.join(root, "docs", italian ? "data-agent-story.it.md" : "data-agent-story.md");
  const source = await readFile(sourcePath, "utf8");
  const github = "https://github.com/faustinopalma/chocoverse/blob/main/";
  let exhibit = 0;
  const escape = (value) => MarkdownIt().utils.escapeHtml(value);
  const references = source.match(/^\[[^\]]+\]:[^\r\n]+/gm)?.join("\n") ?? "";
  const title = source.match(/^# (.+)\r?$/m)?.[1].trim();
  const chapters = [...source.matchAll(/^## ([1-4])\. (.+)\r?$/gm)];
  const footerStart = source.indexOf(italian ? "## Fonti" : "## Sources");
  const contextStart = source.indexOf(italian ? "## Giandoria nel Chocoverse" : "## Giandoria in the Chocoverse");
  const reviewStart = source.indexOf(italian ? "## Questa analisi della ripresa" : "## This recovery review");
  if (!title || chapters.length !== 4 || footerStart < 0 || contextStart < 0 || reviewStart < contextStart) {
    throw new Error("The story must have a title, company context, recovery introduction, four chapters and sources.");
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
    if (!relative.startsWith("docs/") && !["README.md", "infra/demo/README.md",
      "config/scenarios/channel-expansion-maintenance.json"].includes(relative)) {
      throw new Error(`Unexpected link: ${href}`);
    }
    return `${github}${relative}${fragment ? `#${fragment}` : ""}`;
  }

  const markdown = new MarkdownIt({ html: false, linkify: false });
  if (italian) markdown.renderer.rules.blockquote_open = () => '<blockquote lang="en">\n';
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
    const legend = src.endsWith("/recovery-history.svg")
      ? `<ul class="chart-legend" aria-label="${italian ? "Legenda del grafico" : "Chart legend"}">
        <li><span class="series-key backlog-key" aria-hidden="true"></span>${italian ? "Ordini arretrati" : "Backlog"}</li>
        <li><span class="series-key stock-key" aria-hidden="true"></span>${italian ? "Scorte di prodotto finito" : "Finished stock"}</li></ul>` : "";
    return `<figure class="evidence">${legend}<a class="capture" href="${src}" data-zoom aria-label="${italian ? "Apri il documento originale" : "View original evidence"}: ${alt}">
      <img src="${src}" alt="${alt}" width="${dimensions[0]}" height="${dimensions[1]}" loading="lazy" decoding="async">
      </a><figcaption><span class="exhibit-number">${italian ? "Documento" : "Exhibit"} ${String(++exhibit).padStart(2, "0")}</span>
      ${alt}</figcaption></figure>`;
  };
  const render = (text) => markdown.render(`${text}\n\n${references}`);
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
  let template = await readFile(path.join(here, "shell.html"), "utf8");
  if (italian) {
    for (const [english, translated] of [
      ['<html lang="en">', '<html lang="it">'],
      ["Follow Giandoria's supply recovery through sales, production and backlog, using real Fabric Data Agent executions.",
        "Segui la ripresa di Giandoria tra vendite, produzione e ordini arretrati, con esecuzioni reali del Fabric Data Agent."],
      ["Skip to the report", "Vai all'analisi"],
      ["Giandoria / Data Agent investigation", "Giandoria / Analisi con il Data Agent"],
      ['aria-label="Language"', 'aria-label="Lingua"'],
      ["Dark edition", "Tema scuro"],
      ["Viewing controls could not start.", "Impossibile avviare i controlli di visualizzazione."],
      ["The full report remains readable. Evidence links open the original images.",
        "L'analisi rimane leggibile. I collegamenti ai documenti aprono le immagini originali."],
      ["Giandoria / Sales, supply and orders", "Giandoria / Vendite, forniture e ordini"],
      ["Data Agent investigation", "Analisi con il Data Agent"],
      ["Sales &amp; supply recovery<br>A Fabric Data Agent investigation",
        "Ripresa di vendite e forniture<br>Un'analisi con il Fabric Data Agent"],
      ["Giandoria and its value chain", "Giandoria e la sua filiera"],
      ["An illustrated chocolate business connecting ingredients, factory production, deliveries and retail.",
        "Un'azienda del cioccolato illustrata: ingredienti, produzione, consegne e negozi collegati."],
      ["Giandoria's connected business. AI-generated conceptual illustration.",
        "Il business interconnesso di Giandoria. Illustrazione concettuale generata con AI."],
      ["Review period", "Periodo di analisi"],
      ["September 2047–February 2048", "Settembre 2047–febbraio 2048"],
      ["Time basis", "Riferimento temporale"],
      ["Business dates", "Date di business"],
      ["Report contents", "Indice dell'analisi"],
      ["Follow the investigation", "Segui l'analisi"],
      ["Recovery review", "Analisi della ripresa"],
      ["Markdown edition", "Versione Markdown"],
      ["Back to the cover ↑", "Torna all'inizio ↑"],
      ["Whiteboard annotations stay in this browser.", "Le annotazioni restano in questo browser."],
      ["Execution evidence", "Documenti delle esecuzioni"],
      ["Close evidence", "Chiudi il documento"],
      ["Close ×", "Chiudi ×"],
      ["Open the original image", "Apri l'immagine originale"],
      ["/main/docs/data-agent-story.md", "/main/docs/data-agent-story.it.md"],
    ].sort(([left], [right]) => right.length - left.length)) {
      if (!template.includes(english)) throw new Error(`Missing translation target: ${english}`);
      template = template.replaceAll(english, translated);
    }
  }
  const assetVersion = async (filename) => createHash("sha256")
    .update((await readFile(path.join(here, filename), "utf8")).replace(/\r\n/g, "\n"))
    .digest("hex").slice(0, 12);
  const html = template.replaceAll("{{TITLE}}", escape(title))
    .replace("{{EN_CURRENT}}", italian ? "" : 'aria-current="page"')
    .replace("{{IT_CURRENT}}", italian ? 'aria-current="page"' : "")
    .replace("{{STYLE_VERSION}}", await assetVersion("style.css"))
    .replace("{{SCRIPT_VERSION}}", await assetVersion("story.js"))
    .replace("{{CONTEXT}}", render(source.slice(contextStart, reviewStart)))
    .replace("{{INTRO}}", render(source.slice(reviewStart, chapters[0].index)))
    .replace("{{NAV}}", nav)
    .replace("{{CHAPTERS}}", sectionHtml)
    .replace("{{EVIDENCE}}", render(source.slice(footerStart)));
  if (/\{\{[A-Z]+\}\}/.test(html)) throw new Error("Unfilled template field.");
  await writeFile(path.join(output, italian ? "it.html" : "index.html"), html);
}

await rm(output, { recursive: true, force: true });
await mkdir(path.join(output, "assets"), { recursive: true });
await buildEdition("en");
await buildEdition("it");
await writeFile(path.join(output, ".nojekyll"), "");
for (const file of ["style.css", "story.js", "whiteboard.js"]) {
  await copyFile(path.join(here, file), path.join(output, file));
}
for (const asset of assets) {
  await copyFile(path.join(root, "docs", "images", "data-agent-story", asset), path.join(output, "assets", asset));
}
await copyFile(path.join(here, "art", "giandoria-editorial.webp"),
  path.join(output, "assets", "giandoria-editorial.webp"));
console.log(`Built English and Italian editions, four chapters each, ${assets.size} shared public evidence assets.`);
