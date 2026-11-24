// Builds the README pictures in the style of the house's store images: a capture of the desk
// with the made-up app and the KnightSight panel, tilted like a screen, on the dark relief
// ground with the logo, beside a heading and a grey line. Each picture is 1920x1000, rendered
// at twice the size so the text stays sharp through the tilt.
//
// The captures come from capture.ps1, which runs the real KnightSight.exe on Windows.
//
// The heading is set in Bree Serif Regular and the line below in Bree Light. Neither is
// committed, so HOUSE_FONTS (default %LOCALAPPDATA%\halleluja-fonts) must hold them as TTF.
//
// Deps (global): playwright-core with its Chromium installed.
// Run: node .github/assets/screenshots/render.mjs [pick share region pinboard]
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require(`${execSync('npm root -g').toString().trim()}/playwright-core`);

const here = import.meta.dirname;
const repo = resolve(here, '..', '..', '..');
const captures = join(here, 'captures');

const SUB = 'KnightSight for Windows, eyes for your coding assistant';
const SHOTS = [
  { name: 'pick', heading: 'Pick a window. <em>It sees nothing else.</em>' },
  { name: 'share', heading: 'No secret clicks. <em>The frame tells on it.</em>' },
  { name: 'region', heading: 'Just a corner? <em>Drag a box.</em>' },
  { name: 'pinboard', heading: 'Point at it. <em>Leave a note.</em>' },
];
const wanted = process.argv.slice(2);

// The captures are 1300x700, shown 1270 wide.
const SCREEN = { width: 1270, height: 684 };

const dataUrl = (buf, type) => `data:${type};base64,${buf.toString('base64')}`;

// The house typeface is licensed, so it is read from a local folder and never committed.
const fonts = process.env.HOUSE_FONTS ?? join(process.env.LOCALAPPDATA ?? tmpdir(), 'halleluja-fonts');
const font = (file) => dataUrl(readFileSync(join(fonts, file)), 'font/ttf');

const STYLE = `
@font-face { font-family: "Bree Serif"; src: url(${font('bree-serif-regular.ttf')}); font-weight: 400; }
@font-face { font-family: Bree; src: url(${font('bree-light.ttf')}); font-weight: 300; }
* { box-sizing: border-box; margin: 0; }
body { position: relative; width: 1920px; height: 1000px; overflow: hidden; font-family: Bree, sans-serif; font-weight: 300; background: #0c0c0b; }
.backdrop, .backdrop * { position: absolute; }
.backdrop { inset: 0; overflow: hidden; }
.wall { inset: 0; background: radial-gradient(55% 60% at 62% 35%, #26231d, #0f0e0c 72%); }
.mark { width: 50%; left: -9%; top: -6%; transform: rotate(-10deg); opacity: .32;
  filter: grayscale(1) brightness(.36) contrast(1.2) drop-shadow(-2px -2px 0 rgba(255,255,255,.16)) drop-shadow(12px 18px 26px rgba(0,0,0,.85)); }
.vignette { inset: 0; box-shadow: inset 0 0 200px rgba(0,0,0,.6); }
.copy { position: absolute; left: 84px; top: 0; bottom: 0; width: 470px; display: flex; flex-direction: column; justify-content: center; gap: 28px; }
.copy img { width: 92px; }
h1 { font: 400 64px/1.12 "Bree Serif", serif; color: #f4f4f4; text-wrap: balance; }
h1 em { font-style: normal; color: #FCC419; }
.sub { font-size: 28px; line-height: 1.35; color: #9d9481; }
.stage { position: absolute; left: 600px; top: ${(1000 - SCREEN.height) / 2}px; width: ${SCREEN.width}px; height: ${SCREEN.height}px; perspective: 2400px; }
.floor { position: absolute; left: 12%; right: 12%; bottom: -4%; height: 8%; border-radius: 50%; background: rgba(0,0,0,.8); filter: blur(30px); }
.screen { position: absolute; inset: 0; transform: rotateY(-8deg) rotateX(2deg); border-radius: 14px; overflow: hidden; background: #161616;
  box-shadow: 0 0 0 1px #3c3c3c, 0 2px 4px rgba(0,0,0,.35), 0 18px 36px rgba(0,0,0,.45), 0 52px 100px rgba(0,0,0,.55); }
.screen > img { display: block; width: 100%; height: 100%; }
.glare { position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(118deg, rgba(255,255,255,.09) 0%, rgba(255,255,255,.03) 28%, rgba(255,255,255,0) 42%); }
`;

function picture(logo, shot) {
  const shown = dataUrl(readFileSync(join(captures, `${shot.name}.png`)), 'image/png');
  return `<!doctype html><html><head><meta charset="utf-8"><style>${STYLE}</style></head><body>
<div class="backdrop"><div class="wall"></div><img class="mark" src="${logo}"><div class="vignette"></div></div>
<div class="copy"><img src="${logo}"><h1>${shot.heading}</h1><p class="sub">${SUB}</p></div>
<div class="stage"><div class="floor"></div><div class="screen"><img src="${shown}"><div class="glare"></div></div></div>
</body></html>`;
}

// Drawn at twice the size and scaled down in a second page.
const browser = await chromium.launch();
try {
  const logo = dataUrl(readFileSync(join(repo, '.github', 'assets', 'logo.png')), 'image/png');
  for (const shot of SHOTS.filter((s) => !wanted.length || wanted.includes(s.name))) {
    const big = await browser.newPage({ viewport: { width: 1920, height: 1000 }, deviceScaleFactor: 2 });
    await big.setContent(picture(logo, shot));
    await big.evaluate(() => Promise.all(['400 1em "Bree Serif"', '300 1em Bree'].map((f) => document.fonts.load(f))));
    await big.evaluate(() => Promise.all([...document.images].map((img) => img.decode())));
    const png = await big.screenshot();
    await big.close();
    const small = await browser.newPage({ viewport: { width: 1920, height: 1000 } });
    await small.setContent(`<body style="margin:0"><img src="${dataUrl(png, 'image/png')}" style="display:block;width:1920px;height:1000px">`);
    await small.locator('img').evaluate((img) => img.decode());
    await small.screenshot({ path: join(here, `${shot.name}.png`) });
    await small.close();
    console.log(`wrote ${shot.name}.png`);
  }
} finally {
  await browser.close();
}
