/* global console, process */
// build-how-it-works.mjs: "How Composer works", drawn as five stations on one bench with the anatomy figure kit
// (https://github.com/wheresryan22/anatomy, MIT). Adapted from claim-seal's README figure (same kit, same card).
//   ANATOMY_KIT=<anatomy kit folder> node build-how-it-works.mjs <out dir>
// Writes <out>/how-it-works.svg and <out>/how-it-works-card.html (photographed by capture-still.mjs).
// Left to right: 1 two stacks of feed sheets; 2 a screen tray the text passes through; 3 a magnifier (the lens)
// over the screened text; 4 claim-seal's card index and reject tray; 5 the sealed rack. A belt carries the claim
// cards from 2 to 5. No moving spark or bead: this is a still.
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { FIGURE_CSS, cardHtml } from './theme.mjs';

const KIT = process.env.ANATOMY_KIT;
if (!KIT) {
  console.error('REFUSED: set ANATOMY_KIT to the anatomy kit folder');
  process.exit(2);
}
const OUT = resolve(process.argv[2] ?? '.');
mkdirSync(OUT, { recursive: true });
const k = await import(pathToFileURL(join(KIT, 'kit/iso-kit.mjs')).href);

export const WIDTH = 1000;
export const HEIGHT = 450;

// The recorded brief's numbers (composer/data/recorded-run.json): 6 checked citations, 7 model calls.
const DEMO_ROWS = 6;
const DEMO_CALLS = 7;

const BENCH = { x: -334, y: -40, w: 668, d: 84, r: 8 };
const BENCH_H = 16;
const FOOT_H = 5;
const SX = [-262, -131, 0, 131, 262];
const SY = -10;
const BELT = { x: -171, y: 24, w: 463, d: 9, r: 2 };
const BELT_H = 3;
const RACK_TOP = 6 + DEMO_ROWS * 6 + 2;

const P = k.fitProjection(
  [
    ...k.boxCorners(BENCH, -BENCH_H - FOOT_H, 0),
    [SX[0] - 20, SY, 46],
    [SX[4] - 16, SY - 12, RACK_TOP + 8],
    [SX[4] + 16, SY + 12, RACK_TOP + 8],
  ],
  WIDTH,
  HEIGHT,
  { pad: 22, azimuth: 58 },
);
const at = (p) => k.iso(p, P);
const S = (paths, style) => k.solidSvg(paths, style);
const L = (d, style) => k.lineSvg(d, style);
const D = (points, style) => k.dotsSvg(points, style);
const poly = (points) => k.pathOf(points.map(at), true);
const faceY = (y, x0, x1, z0, z1) =>
  poly([
    [x0, y, z0],
    [x1, y, z0],
    [x1, y, z1],
    [x0, y, z1],
  ]);
const lineY = (y, x0, x1, z) => k.pathOf([at([x0, y, z]), at([x1, y, z])]);
const byDepth = (pts) =>
  [...pts].sort((a, b) => k.depthOf([a[0], a[1], 0], P) - k.depthOf([b[0], b[1], 0], P));
const part = (name, body) => `<g data-part="${name}">${body}</g>`;
const halo = (plan) =>
  `<path class="iso-halo" d="${k.haloOf(plan, 0, 0.1, P)}" style="filter:blur(3px)"/>`;
// text engraved on a +y face, centred on x, baseline at z
const faceText = (x, y, z, text, size, tone = 'hi') =>
  k.faceTextSvg(k.sideMatrix([x, y], z, P, 'left'), text, { size, tone, anchor: 'middle' });

function plateY(x0, x1, y, z0, z1, text, size) {
  const plate = { x: x0, y, w: x1 - x0, d: 0.9, r: 0.3 };
  return (
    S(k.slabOf(plate, z0, z1 - z0, P, 2), { tone: 'lo', crease: 'none' }) +
    faceText((x0 + x1) / 2, y + 0.9, z0 + (z1 - z0 - size * 0.72) / 2, text, size) +
    D([at([x0 + 1.4, y + 0.9, (z0 + z1) / 2]), at([x1 - 1.4, y + 0.9, (z0 + z1) / 2])], {
      size: 0.45,
      tone: 'mid',
    })
  );
}

// an open tray: floor, back walls, what lies inside, front walls (painter's order)
function openTray(plan, h, inside = '', tone = 'mid') {
  const t = 1.2;
  const { x, y, w, d } = plan;
  const wall = (p) => S(k.slabOf(p, 1.2, h - 1.2, P, 2, 0.2), { tone, crease: 'none' });
  return (
    S(k.slabOf(plan, 0, 1.2, P, 3, 0.3), { tone: 'lo' }) +
    wall({ x, y, w: t, d, r: 0.3 }) +
    wall({ x, y, w, d: t, r: 0.3 }) +
    inside +
    wall({ x: x + w - t, y, w: t, d, r: 0.3 }) +
    wall({ x, y: y + d - t, w, d: t, r: 0.3 })
  );
}
// a sheet lying flat, with text rules on it
function flatSheet(plan, z, rules = 4, tone = 'hi') {
  let out = S(k.slabOf(plan, z, 0.6, P, 2), { tone, crease: 'none' });
  for (let i = 0; i < rules; i++) {
    const yy = plan.y + 3 + i * ((plan.d - 5) / Math.max(1, rules - 1));
    out += L(
      k.lineOnTop([plan.x + 2.5, yy], [plan.x + plan.w - 2.5 - (i % 2) * 5, yy], z + 0.6, P),
      { tone: 'lo', free: true },
    );
  }
  return out;
}

function bench() {
  const out = [`<path class="iso-halo" d="${k.haloOf(BENCH, -BENCH_H - FOOT_H, BENCH_H, P)}"/>`];
  for (const [x, y] of byDepth(k.corners(BENCH, 20))) {
    out.push(S(k.cylinder(x, y, 8, -BENCH_H - FOOT_H, 1.6, P, 28), { tone: 'lo' }));
    out.push(
      S(k.cylinder(x, y, 6.2, -BENCH_H - FOOT_H + 1.6, FOOT_H - 1.6, P, 28), { tone: 'mid' }),
    );
  }
  out.push(S(k.slabOf(BENCH, -BENCH_H, BENCH_H, P, 8, 1.6), { tone: 'mid' }));
  out.push(L(k.planOutline(k.insetPlan(BENCH, 5), 0, P), { tone: 'faint' }));
  const screws = k.corners(BENCH, 10);
  out.push(L(screws.map(([x, y]) => k.ring(x, y, 2.4, 0, P, 16)).join(''), { tone: 'lo' }));
  out.push(D(screws.map(([x, y]) => at([x, y, 0])), { size: 0.55 }));
  const names = ['1 FEEDS', '2 SCREEN', '3 YOUR LENS', '4 CHECK', '5 SEAL'];
  SX.forEach((x, i) =>
    out.push(plateY(x - 52, x + 52, BENCH.y + BENCH.d, -14.5, -2.5, names[i], 9.0)),
  );
  // the belt that carries the claim cards from the screen to the seal
  out.push(S(k.slabOf(BELT, 0, BELT_H, P, 4, 0.4), { tone: 'lo' }));
  for (let x = BELT.x + 12; x < BELT.x + BELT.w - 6; x += 12)
    out.push(
      L(k.lineOnTop([x, BELT.y + 1.5], [x, BELT.y + BELT.d - 1.5], BELT_H, P), { tone: 'faint' }),
    );
  out.push(
    D(
      [BELT.x + 4, BELT.x + BELT.w - 4].map((x) => at([x, BELT.y + BELT.d / 2, BELT_H])),
      { size: 0.7, tone: 'mid' },
    ),
  );
  return out.join('');
}

// a claim card on the belt in front of a station
const card = (x) =>
  S(k.slabOf({ x: x - 6, y: BELT.y + 1, w: 12, d: 7, r: 0.6 }, BELT_H, 1, P, 2, 0.2), {
    tone: 'hi',
    crease: 'lo',
  }) +
  L(k.lineOnTop([x - 3.5, BELT.y + 3.2], [x + 3, BELT.y + 3.2], BELT_H + 1, P), {
    tone: 'lo',
    free: true,
  }) +
  L(k.lineOnTop([x - 3.5, BELT.y + 5], [x + 1, BELT.y + 5], BELT_H + 1, P), {
    tone: 'lo',
    free: true,
  });

// 1: the feeds, two stacks of sheets (one per source), the top sheet of each ruled
function feeds() {
  const x = SX[0];
  const out = [];
  [[x - 34, SY - 20], [x + 2, SY - 6]].forEach(([sx, sy], n) => {
    const src = { x: sx, y: sy, w: 26, d: 20, r: 0.6 };
    out.push(halo(k.insetPlan(src, -1)));
    for (let i = 0; i < 4; i++)
      out.push(
        i < 3
          ? S(k.slabOf({ ...src, x: src.x + i * 1.2, y: src.y - i * 1.2 }, i * 1.4, 1.2, P, 2), {
              tone: 'mid',
              crease: 'none',
            })
          : flatSheet({ ...src, x: src.x + 3.6, y: src.y - 3.6 }, 4.2, 5),
      );
    out.push(
      S(k.slabOf({ x: src.x + 10, y: src.y - 4.4, w: 8, d: 3, r: 0.6 }, 4.8, 1.4, P, 2), {
        tone: n ? 'hi' : 'lo',
      }),
    );
  });
  return out.join('');
}

// 2: the screen, a shallow tray with a mesh floor; risky strings are caught, the rest passes on
function screen() {
  const x = SX[1];
  const tray = { x: x - 28, y: SY - 20, w: 50, d: 34, r: 1.2 };
  const mesh = [];
  for (let i = 1; i < 10; i++)
    mesh.push(L(k.lineOnTop([tray.x + i * 5, tray.y + 2], [tray.x + i * 5, tray.y + tray.d - 2], 1.3, P), { tone: 'faint', free: true }));
  for (let j = 1; j < 7; j++)
    mesh.push(L(k.lineOnTop([tray.x + 2, tray.y + j * 5], [tray.x + tray.w - 2, tray.y + j * 5], 1.3, P), { tone: 'faint', free: true }));
  const caught = S(k.slabOf({ x: tray.x + 30, y: tray.y + 8, w: 9, d: 6, r: 0.5 }, 1.4, 1, P, 2, 0.2), { tone: 'lo', crease: 'lo' });
  const out = [halo(tray), openTray(tray, 6, mesh.join('') + caught, 'mid')];
  return out.join('') + card(x);
}

// 3: write through the lens, a magnifier over the screened feed text; one model call writes the brief
function lens() {
  const x = SX[2];
  const sheet = { x: x - 10, y: SY - 17, w: 32, d: 28, r: 0.5 };
  const out = [flatSheet(sheet, 0, 6)];
  // the located passage
  out.push(
    L(
      k.planOutline({ x: sheet.x + 2, y: sheet.y + 10.4, w: 22, d: 4.4, r: 0.6 }, 0.6, P, 2),
      { tone: 'hi' },
    ),
  );
  const post = [x - 22, SY + 8];
  out.push(halo({ x: post[0] - 9, y: post[1] - 9, w: 18, d: 18, r: 9 }));
  out.push(S(k.cylinder(post[0], post[1], 9, 0, 4, P, 32, 0.4), { tone: 'mid' }));
  out.push(S(k.cylinder(post[0], post[1], 2, 4, 36, P, 18), { tone: 'mid', crease: 'none' }));
  out.push(S(k.cylinder(post[0], post[1], 3.2, 36, 5, P, 20), { tone: 'mid' }));
  out.push(
    S(k.slabOf({ x: post[0], y: post[1] - 1.6, w: 20, d: 3.2, r: 1.2 }, 37, 2.6, P, 2), {
      tone: 'mid',
      crease: 'none',
    }),
  );
  const lens = [x + 6, SY - 3];
  out.push(S(k.cylinder(lens[0], lens[1], 13, 34, 3, P, 56, 0.5), { tone: 'mid' }));
  out.push(
    `<path d="${k.ring(lens[0], lens[1], 10.5, 37, P, 56)}" style="fill:rgba(255,255,255,.07);stroke:var(--anatomy-hi);stroke-width:.7px;vector-effect:non-scaling-stroke"/>`,
  );
  out.push(L(k.ring(lens[0], lens[1], 11.6, 37, P, 56), { tone: 'lo' }));
  out.push(
    L(k.lineOnTop([lens[0] - 6, lens[1] - 4], [lens[0] - 2, lens[1] - 7.5], 37, P), {
      tone: 'hi',
      free: true,
    }),
  );
  return out.join('') + card(x);
}

// 4: check, claim-seal's card index of source titles (one raised: a cited title that exists), a reject tray for one that does not
function check() {
  const x = SX[3];
  const box = { x: x - 26, y: SY - 18, w: 38, d: 30, r: 2 };
  const out = [halo(box), S(k.slabOf(box, 0, 14, P, 3, 0.6), { tone: 'mid' })];
  out.push(L(k.planOutline(k.insetPlan(box, 2.4), 14, P, 3), { tone: 'lo' }));
  for (let i = 0; i < 6; i++) {
    const cx = box.x + 6 + i * 5;
    const tall = i === 3;
    out.push(
      S(
        k.slabOf(
          { x: cx, y: box.y + 3.5, w: 1.1, d: box.d - 7, r: 0.3 },
          6,
          tall ? 24 : 12 + (i % 3) * 1.5,
          P,
          2,
        ),
        { tone: tall ? 'hi' : 'mid', crease: 'none' },
      ),
    );
    if (tall)
      out.push(
        S(k.slabOf({ x: cx, y: box.y + 5, w: 1.1, d: 7, r: 0.3 }, 30, 3, P, 2), {
          tone: 'hi',
          crease: 'none',
        }),
      );
  }
  out.push(L(faceY(box.y + box.d, box.x + 12, box.x + 26, 5, 10), { tone: 'lo' }));
  out.push(D([at([box.x + 19, box.y + box.d, 7.5])], { size: 0.8, tone: 'hi' }));
  // the reject tray: the citation that matched no title lies here and goes no further
  const tray = { x: x + 16, y: SY - 2, w: 20, d: 16, r: 1 };
  const reject = S(k.slabOf({ x: tray.x + 4, y: tray.y + 4, w: 12, d: 7, r: 0.6 }, 1.2, 1, P, 2, 0.2), {
    tone: 'mid',
    crease: 'lo',
  });
  out.push(halo(tray), openTray(tray, 5, reject, 'lo'));
  return out.join('') + card(x);
}

// 5: the seal, a rack of the claim-evidence rows joined by one chain, the seal value on top
function seal() {
  const x = SX[4];
  const base = { x: x - 18, y: SY - 14, w: 36, d: 28, r: 2 };
  const out = [halo(base), S(k.slabOf(base, 0, 6, P, 3, 0.6), { tone: 'mid' })];
  const postAt = [
    [base.x + 2, base.y + 2],
    [base.x + base.w - 5, base.y + 2],
    [base.x + 2, base.y + base.d - 5],
    [base.x + base.w - 5, base.y + base.d - 5],
  ];
  const post = ([px, py]) =>
    S(k.slabOf({ x: px, y: py, w: 3, d: 3, r: 0.6 }, 6, RACK_TOP - 6, P, 2), {
      tone: 'mid',
      crease: 'none',
    });
  const back = byDepth(postAt).slice(0, 2);
  const front = byDepth(postAt).slice(2);
  back.forEach((p) => out.push(post(p)));
  const row = { x: base.x + 3.5, y: base.y + 3.5, w: base.w - 7, d: base.d - 7, r: 0.8 };
  for (let i = 0; i < DEMO_ROWS; i++) {
    const z = 8 + i * 6;
    out.push(S(k.slabOf(row, z, 2.2, P, 2, 0.3), { tone: i === DEMO_ROWS - 1 ? 'hi' : 'mid' }));
    out.push(
      L(k.lineOnTop([row.x + 3, row.y + 4], [row.x + row.w - 9, row.y + 4], z + 2.2, P), {
        tone: 'lo',
        free: true,
      }),
    );
  }
  front.forEach((p) => out.push(post(p)));
  // the cap and the chain value
  out.push(
    S(k.slabOf(k.insetPlan(base, 1), RACK_TOP, 2.4, P, 3, 0.5), { tone: 'mid' }),
  );
  const c = [x, SY];
  out.push(S(k.cylinder(c[0], c[1], 9, RACK_TOP + 2.4, 2.6, P, 40, 0.4), { tone: 'hi', lit: true }));
  out.push(`<path class="rm-amber" d="${k.ring(c[0], c[1], 6.4, RACK_TOP + 5, P, 40)}"/>`);
  out.push(
    `<circle class="rm-amber-dot" cx="${at([c[0], c[1], RACK_TOP + 5])[0].toFixed(1)}" cy="${at([c[0], c[1], RACK_TOP + 5])[1].toFixed(1)}" r="1"/>`,
  );
  // the chain down the front face: one link between each pair of rows, row k's hash feeds row k+1
  const fy = row.y + row.d + 0.1;
  const cx = row.x + row.w - 5;
  for (let i = 0; i < DEMO_ROWS; i++) {
    const z = 9.1 + i * 6;
    out.push(`<path class="rm-amber" d="${k.sideRing([cx, fy, z], 1.6, 'y', P, 20)}"/>`);
    if (i < DEMO_ROWS - 1)
      out.push(
        `<path class="rm-amber" d="${k.pathOf([at([cx, fy, z + 1.6]), at([cx, fy, z + 4.4])])}"/>`,
      );
  }
  out.push(
    `<path class="rm-amber" d="${k.pathOf([at([cx, fy, 9.1 + (DEMO_ROWS - 1) * 6 + 1.6]), at([cx, fy, RACK_TOP])])}"/>`,
  );
  out.push(faceText(x, base.y + base.d, 1.4, 'SHA-256', 3.4, 'mid'));
  return out.join('') + card(x);
}

const PARTS = [
  ['bench', bench()],
  ['feeds', feeds()],
  ['screen', screen()],
  ['lens', lens()],
  ['check', check()],
  ['seal', seal()],
];

const LABEL =
  'How Composer works, drawn as five stations on one bench. 1, two stacks of feed sheets, one per source. 2, a screen tray with a mesh floor that catches risky strings. 3, a magnifier, the lens, over the screened text: one model call writes the brief. 4, claim-seal: a card index of source titles with one card raised, and a reject tray for a cited title that matched nothing. 5, the seal: six rows on a rack joined by an amber chain, an amber seal on top. A belt carries the claim cards from 2 to 5.';
const body = PARTS.map(([name, svg]) => part(name, svg)).join('');
const svgStandalone = k
  .figureSvg({ width: WIDTH, height: HEIGHT, label: LABEL, body, standalone: 'dark' })
  .replace('</style>', `${FIGURE_CSS}</style>`);
writeFileSync(join(OUT, 'how-it-works.svg'), svgStandalone);

export const LEGEND = [
  { n: 1, name: 'Feeds.', text: 'Your chosen sources: any RSS or Atom feed, Hacker News, or a news page. Titles, links and short descriptions only.' },
  { n: 2, name: 'Screen.', text: 'Plain code, no model. Hidden characters are removed and text that reads like an instruction is broken up.' },
  { n: 3, name: 'Your lens.', text: 'One model call writes the brief through your words. Each claim must cite a title it was shown.' },
  { n: 4, name: 'Check.', text: 'claim-seal: a cited title must exist (plain code), then one model call per claim judges support.' },
  { n: 5, name: 'Seal.', text: 'Each checked citation becomes a row in a SHA-256 chain. The brief keeps titles and links, never the articles.', amber: true },
];
const stage = k
  .figureSvg({ width: WIDTH, height: HEIGHT, label: LABEL, body, className: 'iso' })
  .replace('<svg', '<svg data-theme="dark"');
writeFileSync(
  join(OUT, 'how-it-works-card.html'),
  cardHtml({
    title: 'How Composer <em>works</em>',
    fig: 'Fig 1',
    hint: '1 call writes · 1 call per claim checks',
    readout: `Recorded brief: ${DEMO_CALLS} model calls · ${DEMO_ROWS} sealed checks`,
    stage: `<div class="iso" data-theme="dark">${stage}</div>`,
    legend: LEGEND,
    caption:
      'The check says whether the cited source backs a claim, not whether the claim is true. The chain has no key, so it counts only next to version history.',
    kitCss: k.ISO_CSS + 'li{font-size:15.5px}.cap{font-size:14px}',
  }),
);
console.log(`wrote ${OUT}/how-it-works.svg (${svgStandalone.length} B), how-it-works-card.html; parts: ${PARTS.map(([n]) => n).join(', ')}`);
