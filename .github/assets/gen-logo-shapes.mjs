/**
 * Turns the logo masters into the shape tables the three programs draw from:
 *
 *   knightsight.svg      the bare logo  (Windows, macOS and Linux)
 *   knightsight-app.svg  the app tile   (macOS only, for the app icon)
 *
 * Each shape is a fill and a path of absolute moves, lines and cubic curves in the master's
 * own units, counted from the top left of its viewBox. The rects come out as four corners
 * with their transform applied, so the programs only need to fill paths.
 *
 * Run: node .github/assets/gen-logo-shapes.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..", "..");

function attributes(text) {
  const out = {};
  for (const [, name, value] of text.matchAll(/([\w:-]+)="([^"]*)"/g)) out[name] = value;
  return out;
}

const numbers = (text) => (text.match(/[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?/gi) ?? []).map(Number);

// A 2D affine matrix [a, b, c, d, e, f], applied as x' = a x + c y + e, y' = b x + d y + f.
const multiply = (m, n) => [
  m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1],
  m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3],
  m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5],
];

function transform(text = "") {
  let m = [1, 0, 0, 1, 0, 0];
  for (const [, op, args] of text.matchAll(/(\w+)\s*\(([^)]*)\)/g)) {
    const v = numbers(args);
    let step;
    if (op === "matrix") step = v;
    else if (op === "translate") step = [1, 0, 0, 1, v[0], v[1] ?? 0];
    else if (op === "scale") step = [v[0], 0, 0, v[1] ?? v[0], 0, 0];
    else if (op === "rotate") {
      const r = (v[0] * Math.PI) / 180, cos = Math.cos(r), sin = Math.sin(r);
      const [cx = 0, cy = 0] = v.slice(1);
      step = multiply(multiply([1, 0, 0, 1, cx, cy], [cos, sin, -sin, cos, 0, 0]), [1, 0, 0, 1, -cx, -cy]);
    } else throw new Error(`transform ${op} is not supported`);
    m = multiply(m, step);
  }
  return m;
}

const apply = (m, [x, y]) => [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]];

// Path data reduced to M, L, C and Z with absolute points, the shorthands written out.
function pathOps(d) {
  const ops = [];
  let x = 0, y = 0, startX = 0, startY = 0, lastControl = null;
  for (const [, letter, args] of d.matchAll(/([a-zA-Z])([^a-zA-Z]*)/g)) {
    const cmd = letter.toUpperCase(), rel = letter !== cmd, v = numbers(args);
    const ox = () => (rel ? x : 0), oy = () => (rel ? y : 0);
    if (cmd === "Z") {
      ops.push(["Z"]);
      x = startX; y = startY; lastControl = null;
      continue;
    }
    const arity = { M: 2, L: 2, H: 1, V: 1, C: 6, S: 4 }[cmd];
    if (!arity) throw new Error(`path command ${letter} is not supported`);
    for (let i = 0; i < v.length; i += arity) {
      const a = v.slice(i, i + arity);
      if (cmd === "M" && i === 0) {
        x = a[0] + ox(); y = a[1] + oy(); startX = x; startY = y;
        ops.push(["M", x, y]); lastControl = null;
      } else if (cmd === "M" || cmd === "L") {
        x = a[0] + ox(); y = a[1] + oy();
        ops.push(["L", x, y]); lastControl = null;
      } else if (cmd === "H") {
        x = a[0] + ox();
        ops.push(["L", x, y]); lastControl = null;
      } else if (cmd === "V") {
        y = a[0] + oy();
        ops.push(["L", x, y]); lastControl = null;
      } else {
        // S mirrors the previous curve's second control point, or starts at the current point.
        const [c1x, c1y] = cmd === "C" ? [a[0] + ox(), a[1] + oy()] : lastControl ? [2 * x - lastControl[0], 2 * y - lastControl[1]] : [x, y];
        const b = cmd === "C" ? a.slice(2) : a;
        const c2x = b[0] + ox(), c2y = b[1] + oy(), ex = b[2] + ox(), ey = b[3] + oy();
        ops.push(["C", c1x, c1y, c2x, c2y, ex, ey]);
        lastControl = [c2x, c2y]; x = ex; y = ey;
      }
    }
  }
  return ops;
}

function drawing(file) {
  const svg = readFileSync(join(here, file), "utf8");
  const [minX, minY, width, height] = numbers(attributes(svg.match(/<svg\b[^>]*>/)[0]).viewBox);
  const fills = {};
  for (const [, name, color] of svg.matchAll(/\.([\w-]+)\s*\{\s*fill:\s*#([0-9a-f]{3,6})\s*;/gi)) {
    fills[name] = (color.length === 3 ? [...color].map((c) => c + c).join("") : color).toUpperCase();
  }
  const shapes = [];
  for (const [, tag, attrText] of svg.matchAll(/<(rect|path)\b([^>]*?)\/?>/g)) {
    const a = attributes(attrText);
    const fill = fills[a.class];
    if (!fill) throw new Error(`${file}: no fill for class ${a.class}`);
    let ops;
    if (tag === "rect") {
      const x = +a.x, y = +a.y, w = +a.width, h = +a.height, m = transform(a.transform);
      const corners = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]].map((p) => apply(m, p));
      ops = [["M", ...corners[0]], ...corners.slice(1).map((p) => ["L", ...p]), ["Z"]];
    } else {
      if (a.transform) throw new Error(`${file}: a path with a transform is not supported`);
      ops = pathOps(a.d);
    }
    const shift = (op) => [op[0], ...op.slice(1).map((v, i) => v - (i % 2 ? minY : minX))];
    const text = ops.map(shift).map(([op, ...v]) => [op, ...v.map((n) => +n.toFixed(2))].join(" ")).join(" ");
    shapes.push({ fill, path: text });
  }
  return { file, width, height, shapes };
}

const bare = drawing("knightsight.svg");
const tile = drawing("knightsight-app.svg");
const source = (d) => `.github/assets/${d.file}`;

function write(path, text) {
  writeFileSync(join(repo, path), text);
  console.log(`wrote ${path}`);
}

const csShapes = (d) => d.shapes.map((s) => `            new Shape(0x${s.fill}, "${s.path}"),`).join("\n");
write("src/LogoShapes.cs", `// Written by .github/assets/gen-logo-shapes.mjs from ${source(bare)}.
namespace KnightSight
{
    public static partial class Logo
    {
        static readonly Drawing Bare = new Drawing(${bare.width}f, ${bare.height}f, new[]
        {
${csShapes(bare)}
        });
    }
}
`);

const swiftShapes = (d) => d.shapes.map((s) => `        Shape(0x${s.fill}, "${s.path}"),`).join("\n");
write("macos/Sources/KnightSight/LogoShapes.swift", `// Written by .github/assets/gen-logo-shapes.mjs from ${source(bare)} and ${source(tile)}.
extension Logo {
    static let bare = Drawing(width: ${bare.width}, height: ${bare.height}, shapes: [
${swiftShapes(bare)}
    ])

    static let tile = Drawing(width: ${tile.width}, height: ${tile.height}, shapes: [
${swiftShapes(tile)}
    ])
}
`);

const pyShapes = (d) => d.shapes.map((s) => `    (0x${s.fill}, "${s.path}"),`).join("\n");
write("linux/knightsight/logo_shapes.py", `"""Written by .github/assets/gen-logo-shapes.mjs from ${source(bare)}."""

WIDTH, HEIGHT = ${bare.width}, ${bare.height}

SHAPES = [
${pyShapes(bare)}
]
`);
