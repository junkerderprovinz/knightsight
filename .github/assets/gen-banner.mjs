/**
 * Generates the 1600x500 banners:
 *
 *   knightsight-banner.svg/.png       light, logo, name and claim  (README)
 *   knightsight-banner-dark.svg/.png  dark, logo, name and claim   (README, GitHub dark)
 *   knightsight-banner-logo.svg/.png  light, logo only
 *
 * The logo is logo.png, which render-logo.ps1 draws from the program's own code; its steel
 * greys read on either background. Text becomes SVG paths, so the SVG renders the same
 * everywhere without the fonts.
 *
 * Deps (global): opentype.js, @resvg/resvg-js. Fonts are fetched to the OS temp dir.
 * Run: node .github/assets/gen-banner.mjs
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { createRequire } from "node:module";
import { execSync } from "node:child_process";

const require = createRequire(import.meta.url);
const groot = execSync("npm root -g").toString().trim();
const opentype = require(`${groot}/opentype.js`);
const { Resvg } = require(`${groot}/@resvg/resvg-js`);

const __dir = dirname(fileURLToPath(import.meta.url));

const NAME = "KnightSight";
const CLAIM = "Eyes on one window. Hands off the rest.";
const W = 1600, H = 500;
const LOGO = 400;
// Sizes and gaps shared by the banners of all repos.
const claimSize = 44, gap = 70, lineGap = 8, margin = 60;

const THEMES = [
  { suffix: "", bg: "#ffffff", name: "#1f2328", claim: "#5a5d5e" },
  { suffix: "-dark", bg: "#0d1117", name: "#e6edf3", claim: "#9aa4ad" },
];

async function font(file, url) {
  const path = join(tmpdir(), file);
  if (!existsSync(path)) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`font fetch ${res.status}: ${url}`);
    writeFileSync(path, Buffer.from(await res.arrayBuffer()));
  }
  return opentype.parse(readFileSync(path));
}
const nameFont = await font("KnightSight-BreeSerif-Regular.ttf", "https://github.com/google/fonts/raw/main/ofl/breeserif/BreeSerif-Regular.ttf");
const claimFont = await font("KnightSight-Lato-Regular.ttf", "https://github.com/google/fonts/raw/main/ofl/lato/Lato-Regular.ttf");

// The shared name size is 132; a name too long for the row beside the logo is set smaller rather than run off.
const room = W - 2 * margin - LOGO - gap;
const nameSize = Math.min(132, Math.floor((132 * room) / nameFont.getAdvanceWidth(NAME, 132)));
const textW = Math.max(nameFont.getAdvanceWidth(NAME, nameSize), claimFont.getAdvanceWidth(CLAIM, claimSize));
const LX = Math.round((W - (LOGO + gap + textW)) / 2), LY = (H - LOGO) / 2;
const textX = LX + LOGO + gap;

const nameAsc = nameFont.ascender * (nameSize / nameFont.unitsPerEm);
const nameDesc = -nameFont.descender * (nameSize / nameFont.unitsPerEm);
const claimAsc = claimFont.ascender * (claimSize / claimFont.unitsPerEm);
const blockH = nameAsc + nameDesc + lineGap + claimAsc;
const nameBaseline = H / 2 - blockH / 2 + nameAsc;
const claimBaseline = nameBaseline + nameDesc + lineGap + claimAsc;

// Drawn at the origin and moved into place, since opentype.js puts a NaN into some Lato
// curves at large coordinates, and written from the commands for the same reason.
const pathData = (path) => path.commands.map((c) => (c.type === "Z" ? "Z"
  : c.type + [c.x1, c.y1, c.x2, c.y2, c.x, c.y].filter((v) => v !== undefined).map((v) => v.toFixed(2)).join(" "))).join("");
const namePath = pathData(nameFont.getPath(NAME, 0, 0, nameSize));
const claimPath = pathData(claimFont.getPath(CLAIM, 0, 0, claimSize));
if (/NaN/.test(namePath + claimPath)) throw new Error("a glyph came out as NaN");

const logo = `data:image/png;base64,${readFileSync(join(__dir, "logo.png")).toString("base64")}`;
const image = (x, y) => `<image x="${x}" y="${y}" width="${LOGO}" height="${LOGO}" href="${logo}"/>`;

function emit(name, svg, bg) {
  writeFileSync(join(__dir, `${name}.svg`), svg);
  const png = new Resvg(svg, { background: bg, fitTo: { mode: "width", value: W } }).render().asPng();
  writeFileSync(join(__dir, `${name}.png`), png);
  console.log(`wrote ${name}.svg and .png`);
}

for (const t of THEMES) {
  emit(`knightsight-banner${t.suffix}`, `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <rect width="${W}" height="${H}" fill="${t.bg}"/>
  ${image(LX, LY)}
  <path transform="translate(${textX} ${nameBaseline.toFixed(2)})" d="${namePath}" fill="${t.name}"/>
  <path transform="translate(${textX} ${claimBaseline.toFixed(2)})" d="${claimPath}" fill="${t.claim}"/>
</svg>
`, t.bg);
}

const lt = THEMES[0];
emit("knightsight-banner-logo", `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <rect width="${W}" height="${H}" fill="${lt.bg}"/>
  ${image((W - LOGO) / 2, LY)}
</svg>
`, lt.bg);
