// skip_flow.mjs: Skip (the button, Esc, a click or tap) at every point of the entry animation lands on the state a
// finished animation lands on.
//
//   node tests/browser/skip_flow.mjs [python]      (python: an interpreter with Composer installed; default python3)
//   PLAYWRIGHT_MODULE=<path to playwright's index.mjs> picks a Playwright install that is not in node_modules.
//   SKIP_STRIDE=<ms> (default 150)  SKIP_SLOW_STRIDE=<ms> (default 600)  SKIP_ENGINES=chromium,webkit  SKIP_WIDTHS=390,1280
//   SKIP_WORKERS=<n> (default 3: that many fixture servers run at once)  SKIP_SHOTS=<folder> saves one picture of a failure.
//
// For each engine (Chromium, WebKit) at 390 and 1280 px, against tests/browser/fixture_app.py (the real server, a
// made-up model, no internet):
//   NATURAL   one run is left alone until the brief is on the screen; a normalized snapshot of what is visible and
//             open (the stage's classes, every canvas, every overlay and sheet, the entry's own elements, the state,
//             the focus) is taken twice, and the two must be equal: that is the state Skip has to reach.
//   SWEEP     the run is started again and Skip is pressed at 0, 150, 300 ... ms (every SKIP_STRIDE) until the natural
//             run's end, once with the feeds answering at once and once with every feed answering 1.5 s late (the stages
//             then arrive one by one). The way Skip is pressed rotates: the button (with focus on it, as a keyboard user
//             has), Esc, a click on the page. For each press:
//               - at once (within 400 ms): no sand canvas, words, Retry or Skip button, no entry panel, the stage is not
//                 withheld, and the focus is on the page, not on a button that was taken away;
//               - nothing the animation drew comes back afterwards (a watcher records every such element added after the
//                 press);
//               - the brief lands (the claim marks show) in time, and the snapshot then equals the natural one.
//   FAILURE   a press while the engine is about to refuse the compose leaves the compose screen back with nothing of
//             the animation on it.
//   REDUCED   with reduced motion there is no Skip button and nothing is drawn; pressing Esc all through the run changes
//             nothing; the finished snapshot equals the one of a run with no key pressed.
//   REPLAY    the published window (docs/demo, the recorded replay with the "What goes in" sheet whose boxes untick one by
//             one): the page that frames it sends "still" (skip to the end) every 150 ms for the first 7 s, then every
//             600 ms, on a controlled clock; the snapshot after each must equal the one of a replay that ran to its end:
//             no sheet, scrim, ripple or sand left, and nothing opens again.
// Prints one PASS / FAIL line per engine, width and part; exits 1 if any failed.
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import readline from 'node:readline';
import http from 'node:http';
import fs from 'node:fs';

const here = dirname(fileURLToPath(import.meta.url));
const python = process.argv[2] || 'python3';
const pw = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const engines = (process.env.SKIP_ENGINES || 'chromium,webkit').split(',');
const widths = (process.env.SKIP_WIDTHS || '390,1280').split(',').map(Number);
const STRIDE = Number(process.env.SKIP_STRIDE || 150);
const SLOW_STRIDE = Number(process.env.SKIP_SLOW_STRIDE || 600);
const WORKERS = Number(process.env.SKIP_WORKERS || 3);
const shots = process.env.SKIP_SHOTS || '';
const DEMO = join(here, '..', '..', 'docs', 'demo');
const LAND_MS = 60000;   // a skipped run must show its brief within this long of the press (the slow feeds take about 20 s; a busy machine more)
const SETTLE_MS = 1800;  // the brief is on the screen; the ring and the fades finish within this

async function startServer(env = {}) {
  const child = spawn(python, [join(here, 'fixture_app.py')], { stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, ...env } });
  child.stderrText = '';
  child.stderr.on('data', (d) => { child.stderrText = (child.stderrText + d).slice(-4000); });
  const lines = readline.createInterface({ input: child.stdout });
  const [line] = await Promise.race([once(lines, 'line'),
    new Promise((_, reject) => setTimeout(() => reject(new Error('the fixture server did not start')), 30000))]);
  return { child, ...JSON.parse(line) };
}

async function stop(server) {
  if (server.child.exitCode !== null) return;
  const exited = once(server.child, 'exit');
  server.child.kill('SIGTERM');
  await Promise.race([exited, new Promise((r) => setTimeout(r, 5000))]);
  if (server.child.exitCode === null) server.child.kill('SIGKILL');
}

// The entry transition and the replay window exist as copies (the app, the window, the committed demo site). They must be
// the same bytes, or this test of one says nothing about another.
function sameCopies() {
  const web = join(here, '..', '..', 'composer', 'web');
  const groups = [[join(web, 'app', 'composer-entry-transition.js'), join(web, 'window', 'composer-entry-transition.js'), join(DEMO, 'window', 'composer-entry-transition.js')],
    [join(web, 'window', 'window.js'), join(DEMO, 'window', 'window.js')]];
  for (const g of groups) {
    const first = fs.readFileSync(g[0]);
    for (const f of g.slice(1)) if (!first.equals(fs.readFileSync(f))) throw new Error(`${f} is not the same file as ${g[0]}`);
  }
}

// ---- in the page ------------------------------------------------------------------------------------------------------

// Everything the animation owns, by selector. After Skip none of these may exist (the stage's own classes are checked apart).
const ENTRY_PARTS = ['#cmpEntryTransition', '#cwEntrySkip', '#cwWordRaster', '#cwWordSubtext', '#cwRetry', '#cwReducedWords',
  'canvas.cmp-entry-sand', 'canvas.sand-word-canvas'];

// A normalized snapshot: the state a reader sees, without text that changes from run to run (times, job ids).
function snapshot() {
  const q = (s) => document.querySelector(s);
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const shown = (e) => {
    const r = e.getBoundingClientRect();
    if (r.width < 2 || r.height < 2 || r.right < 0 || r.bottom < 0 || r.left > vw || r.top > vh) return false;
    for (let n = e; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) < 0.05) return false;
    }
    return true;
  };
  const name = (e) => e.tagName.toLowerCase() + (e.id ? `#${e.id}` : '')
    + (typeof e.className === 'string' && e.className.trim() ? `.${e.className.trim().split(/\s+/).sort().join('.')}` : '');
  const overlays = [];
  for (const e of document.querySelectorAll('body *')) {
    if (e.tagName === 'SCRIPT' || e.tagName === 'STYLE' || e.closest('svg')) continue;
    const pos = getComputedStyle(e).position;
    if ((pos === 'fixed' || pos === 'absolute') && (e.id || e.className) && shown(e)) overlays.push(name(e));
  }
  const panels = [...document.querySelectorAll('.sheet.on, .cmpsheet, .cmpscrim, .cmpsheet.on, #scrim.on, .drawer.on, [role="dialog"]')]
    .filter((e) => e.id !== 'cmp' && shown(e)).map(name);   // #cmp is the compose card itself (it has role=dialog)
  const stage = q('#cmpStage');
  const active = document.activeElement;
  return {
    state: (q('#cmp') || document.body).getAttribute('data-state'),
    body: [...document.body.classList].sort().join(' '),
    stage: stage ? [...stage.classList].sort().join(' ') : null,
    entryParts: [].concat(...['#cmpEntryTransition', '#cwEntrySkip', '#cwWordRaster', '#cwWordSubtext', '#cwRetry', '#cwReducedWords']
      .map((s) => (q(s) ? [s] : []))),
    canvases: [...document.querySelectorAll('canvas')].map((c) => c.className).sort(),
    overlays: overlays.sort(),
    panels: panels.sort(),
    status: (q('#cmpEntryStatus') || {}).textContent || '',
    head: (q('#cmpLoomHead') || {}).textContent || '',
    page: location.pathname + location.search.replace(/job-[0-9a-f]+/g, 'JOB'),
    scrollLocked: document.body.style.overflow,
    focusOk: !active || active === document.body || (document.body.contains(active) && active.id !== 'cwEntrySkip'),
  };
}

// Installed before Compose is pressed: presses Skip `at` ms after the press (on the page's own clock, so a slow test
// machine does not move the point), and watches for anything the animation drew coming back afterwards.
function arm({ at, how, parts }) {
  window.__skipTest = { pressed: null, how, early: null, returned: [], late: false };
  const T = window.__skipTest;
  const watcher = new MutationObserver((records) => {
    if (T.pressed === null) return;
    for (const r of records) for (const n of r.addedNodes) {
      if (n.nodeType !== 1) continue;
      for (const s of parts) if (n.matches(s) || n.querySelector(s)) T.returned.push(`${s} added ${Math.round(performance.now() - T.pressed)} ms after the press`);
    }
  });
  watcher.observe(document.documentElement, { childList: true, subtree: true });
  document.getElementById('cmpGo').addEventListener('click', () => {
    setTimeout(() => {
      const btn = document.getElementById('cwEntrySkip');
      if (!btn) { T.late = true; return; }   // the animation had already ended by itself
      T.pressed = performance.now();
      if (how === 'button') { btn.focus(); btn.click(); }
      else if (how === 'esc') document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
      else document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, clientX: 24, clientY: 300 }));
      if (how === 'click') document.body.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: 24, clientY: 300 }));
    }, at);
  }, { once: true, capture: true });
}

// ---- driving one run --------------------------------------------------------------------------------------------------

async function openApp(browser, server, width, opts = {}) {
  const ctx = await browser.newContext({ viewport: { width, height: width < 500 ? 844 : 900 }, ...opts });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
  await page.goto(server.app, { waitUntil: 'load' });
  await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 15000 });
  return { ctx, page, errors };
}

// the brief is on the screen: the claim marks show. Returns how long after `since` (ms on Node's clock).
async function landed(page, since, why) {
  try {
    await page.locator('.cmark').first().waitFor({ state: 'visible', timeout: LAND_MS });
  } catch (e) {
    const where = await page.evaluate(() => {
      const c = window.__compositionController;
      return `${c ? c.state : 'no controller'}, loom "${(document.getElementById('cmpLoomHead') || {}).textContent || ''}"`;
    }).catch(() => 'page gone');
    throw new Error(`${why}: the brief never showed, the page is stuck (${where})`);
  }
  return Date.now() - since;
}

async function natural(browser, server, width, opts) {
  const { ctx, page } = await openApp(browser, server, width, opts);
  // when the Skip button goes by itself (the animation ends before the brief shows): presses after that have nothing to press
  await page.evaluate(() => {
    document.getElementById('cmpGo').addEventListener('click', () => {
      const t0 = performance.now();
      const iv = setInterval(() => { if (!document.getElementById('cwEntrySkip')) { window.__buttonGone = performance.now() - t0; clearInterval(iv); } }, 20);
    }, { once: true, capture: true });
  });
  const since = Date.now();
  await page.click('#cmpGo');
  const took = await landed(page, since, 'a run left alone');
  await page.waitForTimeout(SETTLE_MS);
  const snap = await page.evaluate(snapshot);
  const buttonGone = await page.evaluate(() => window.__buttonGone || 0);
  await ctx.close();
  return { took, snap, buttonGone };
}

const HOWS = ['button', 'esc', 'click'];

async function pressAt(browser, server, width, at, how) {
  const { ctx, page, errors } = await openApp(browser, server, width);
  await page.evaluate(arm, { at, how, parts: ENTRY_PARTS });
  const since = Date.now();
  await page.click('#cmpGo');
  // wait for the press to happen (it is in the page), then look at once
  await page.waitForFunction(() => window.__skipTest && (window.__skipTest.pressed !== null || window.__skipTest.late), null, { timeout: at + 6000, polling: 50 });
  const pressed = await page.evaluate(() => window.__skipTest.pressed !== null);
  let early = null;
  if (pressed) {
    await page.waitForTimeout(400);
    early = await page.evaluate((parts) => ({
      left: parts.filter((s) => document.querySelector(s)),
      withheld: !!document.getElementById('cmpStage') && document.getElementById('cmpStage').classList.contains('entry-loom-withheld'),
      focusOk: !document.activeElement || document.activeElement === document.body
        || (document.body.contains(document.activeElement) && document.activeElement.id !== 'cwEntrySkip'),
      brief: !!document.querySelector('.cmark'),
    }), ENTRY_PARTS);
  }
  let took;
  try { took = await landed(page, since, `Skip by ${how} at ${at} ms`); } catch (e) {
    if (shots) await page.screenshot({ path: `${shots}/stuck-${how}-${at}-${width}.png` }).catch(() => {});
    await ctx.close();
    throw e;
  }
  await page.waitForTimeout(SETTLE_MS);
  const snap = await page.evaluate(snapshot);
  const test = await page.evaluate(() => window.__skipTest).catch(() => null);
  await ctx.close();
  return { pressed, early, snap, returned: (test && test.returned) || [], errors, took };
}

function diff(a, b) {
  const out = [];
  for (const k of Object.keys(a)) if (JSON.stringify(a[k]) !== JSON.stringify(b[k])) out.push(`${k}: ${JSON.stringify(b[k])} instead of ${JSON.stringify(a[k])}`);
  return out;
}

// run `jobs` (async fns taking a worker's server) over WORKERS fixture servers
async function pool(env, jobs) {
  const servers = [];
  const failures = [];
  let next = 0;
  let n = 0;
  try {
    for (let i = 0; i < Math.min(WORKERS, jobs.length); i += 1) servers.push(await startServer(env));
    await Promise.all(servers.map(async (server) => {
      while (next < jobs.length) {
        const job = jobs[next]; next += 1;
        try { await job(server); n += 1; } catch (e) { failures.push(String(e.message || e).split('\n')[0].slice(0, 400)); }
      }
    }));
  } finally {
    await Promise.all(servers.map(stop));
  }
  return { n, failures };
}

async function sweep(browser, engine, width, feedDelay, stride, log) {
  const env = feedDelay ? { FIXTURE_FEED_DELAY: String(feedDelay) } : {};
  const probe = await startServer(env);
  let base;
  try {
    const first = await natural(browser, probe, width);
    const second = await natural(browser, probe, width);
    const unstable = diff(first.snap, second.snap);
    if (unstable.length) throw new Error(`two runs left alone do not end the same, so the snapshot is not a fair yardstick: ${unstable.join('; ')}`);
    if (first.snap.entryParts.length || first.snap.stage !== 'cmpstage entry-frame-only entry-sand-frame-solidifying'
      || !first.snap.canvases.includes('cmp-entry-sand-rest') || first.snap.panels.length) {
      throw new Error(`a run left alone does not end the way this test expects: ${JSON.stringify(first.snap)}`);
    }
    base = { snap: first.snap, took: Math.min(first.took, second.took), buttonGone: Math.min(first.buttonGone, second.buttonGone) };
  } finally { await stop(probe); }
  const last = Math.max(stride, (base.buttonGone || base.took) - 300);
  const jobs = [];
  let landedPresses = 0;
  let i = 0;
  for (let at = 0; at <= last; at += stride) {
    const how = HOWS[i % HOWS.length]; i += 1;
    jobs.push(async (server) => {
      const r = await pressAt(browser, server, width, at, how);
      if (!r.pressed) return;   // the animation had ended by itself first: nothing to skip
      landedPresses += 1;
      const where = `Skip by ${how} at ${at} ms`;
      if (r.early.left.length) throw new Error(`${where}: still on the screen at once: ${r.early.left.join(', ')}`);
      if (r.early.withheld) throw new Error(`${where}: the composition stayed withheld`);
      if (!r.early.focusOk) throw new Error(`${where}: the focus stayed on a button that is gone`);
      if (r.returned.length) throw new Error(`${where}: drawn again after the press: ${r.returned.join('; ')}`);
      if (r.errors.length) throw new Error(`${where}: the page raised ${r.errors[0]}`);
      const d = diff(base.snap, r.snap);
      if (d.length) throw new Error(`${where}: the end state differs from a finished animation: ${d.join('; ')}`);
    });
  }
  const { n, failures } = await pool(env, jobs);
  if (!failures.length && landedPresses < Math.ceil(jobs.length * 0.9)) {
    throw new Error(`only ${landedPresses} of ${jobs.length} presses found the Skip button (the animation ended first: the machine is too slow for this test, nothing was proved)`);
  }
  if (failures.length) {
    const stuck = failures.filter((f) => /never showed/.test(f));
    const first = stuck[0] || failures[0];
    throw new Error(`${failures.length} of ${jobs.length} presses failed (${stuck.length} left the page stuck, ${failures.length - stuck.length} ended in a different state), first: ${first}`);
  }
  log.push(`${feedDelay ? 'slow' : 'fast'} feeds: ${landedPresses} presses of ${jobs.length} to ${last} ms (the Skip button is there for ${Math.round(base.buttonGone)} ms, the brief shows at ${base.took} ms)`);
}

async function failureAfterSkip(browser, engine, log) {
  const server = await startServer();
  try {
    const { ctx, page } = await openApp(browser, server, 1280);
    await page.route('**/compose', async (route) => {
      await new Promise((r) => setTimeout(r, 2500));
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'the test engine refused' }) });
    });
    await page.click('#cmpGo');
    await page.locator('#cwEntrySkip').waitFor({ state: 'visible', timeout: 5000 });
    await page.waitForTimeout(900);
    await page.keyboard.press('Escape');
    await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 12000 })
      .catch(() => { throw new Error('the compose screen did not come back after the refusal'); });
    const snap = await page.evaluate(snapshot);
    if (snap.entryParts.length || snap.canvases.some((c) => /sand/.test(c))) throw new Error(`the animation is still there: ${JSON.stringify(snap)}`);
    if (/entry-/.test(snap.stage || '')) throw new Error(`the stage keeps ${snap.stage}`);
    if (snap.state !== 'choose') throw new Error(`the screen is "${snap.state}", not the compose screen`);
    await ctx.close();
    log.push('a refused compose after Skip returns to the compose screen');
  } finally { await stop(server); }
}

// reload onto a run that is still going (the app joins it: "rejoin"), then press Skip: the page must still land on the brief
async function rejoinSkip(browser, engine, log) {
  const server = await startServer({ FIXTURE_FEED_DELAY: '1.5' });
  try {
    for (const at of [300, 1500, 4000]) {
      const { ctx, page, errors } = await openApp(browser, server, 1280);
      await page.click('#cmpGo');
      await page.waitForFunction(() => /[?&]job=/.test(location.search), null, { timeout: 15000 });
      const job = await page.evaluate(() => (location.search.match(/job=([^&]+)/) || [])[1]);
      await page.goto(new URL(`/app/?job=${job}`, server.app).href, { waitUntil: 'load' });
      const since = Date.now();
      await page.locator('#cwEntrySkip').waitFor({ state: 'visible', timeout: 10000 })
        .catch(() => { throw new Error('rejoining a running compose shows no Skip button'); });
      await page.waitForTimeout(at);
      if (await page.locator('#cwEntrySkip').count()) await page.keyboard.press('Escape');
      await landed(page, since, `Skip after rejoining, ${at} ms in`);
      await page.waitForTimeout(SETTLE_MS);
      const left = await page.evaluate((parts) => parts.filter((s) => document.querySelector(s)), ENTRY_PARTS);
      if (left.length) throw new Error(`after rejoining and Skip at ${at} ms ${left.join(', ')} is still on the screen`);
      if (errors.length) throw new Error(`the page raised ${errors[0]}`);
      await ctx.close();
    }
    log.push('rejoining a running compose, Skip at 3 points');
  } finally { await stop(server); }
}

async function reduced(browser, engine, width, log) {
  const server = await startServer();
  try {
    const opts = { reducedMotion: 'reduce' };
    const base = await natural(browser, server, width, opts);
    const { ctx, page, errors } = await openApp(browser, server, width, opts);
    const since = Date.now();
    await page.click('#cmpGo');
    for (let i = 0; i < 12 && !(await page.locator('.cmark').count()); i += 1) {
      await page.keyboard.press('Escape');
      await page.waitForTimeout(250);
      const drawn = await page.evaluate(() => ['canvas.cmp-entry-sand', 'canvas.sand-word-canvas', '#cwEntrySkip'].filter((s) => document.querySelector(s)));
      if (drawn.length) throw new Error(`reduced motion drew ${drawn.join(', ')}`);
    }
    await landed(page, since, 'reduced motion with Esc pressed');
    await page.waitForTimeout(SETTLE_MS);
    const d = diff(base.snap, await page.evaluate(snapshot));
    if (d.length) throw new Error(`Esc changed the reduced-motion end state: ${d.join('; ')}`);
    if (errors.length) throw new Error(`the page raised ${errors[0]}`);
    await ctx.close();
    log.push('reduced motion: no Skip button, Esc changes nothing');
  } finally { await stop(server); }
}


// ---- the published window (docs/demo) -----------------------------------------------------------------------------------

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css' };

async function startStatic() {
  const server = http.createServer((q, r) => {
    const f = join(DEMO, q.url.split('?')[0].replace(/\/$/, '/index.html'));
    fs.readFile(f, (e, b) => {
      if (e) { r.writeHead(404); r.end(); } else { r.writeHead(200, { 'content-type': TYPES[f.slice(f.lastIndexOf('.'))] || 'application/octet-stream' }); r.end(b); }
    });
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  return { server, base: `http://127.0.0.1:${server.address().port}` };
}

// what only the replay draws (added to the generic snapshot)
function replayExtras() {
  const q = (s) => document.querySelectorAll(s);
  return { replay: document.body.getAttribute('data-replay'), sheets: q('.cmpsheet, .cmpscrim').length, ripples: q('.lw-touch').length,
    pressed: q('.lw-tap, .lw-press').length, html: [...document.documentElement.classList].sort().join(' '),
    pieces: q('.cmp-assembly-piece.is-in').length, slot: ((document.querySelector('button.cmpslot[data-kind="sources"]') || {}).textContent || ''),
    sandText: q('#cwWordRaster, #cwWordSubtext').length };
}

async function replayAt(browser, base, width, at) {
  const ctx = await browser.newContext({ viewport: { width, height: width < 500 ? 844 : 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
  await page.clock.install({ time: 0 });
  await page.goto(`${base}/index.html`, { waitUntil: 'load' });
  const frame = () => page.frame({ url: /window\/index/ });
  if (at === null) {
    for (let i = 0; i < 80 && (await frame().evaluate(() => document.body.getAttribute('data-replay'))) !== 'done'; i += 1) await page.clock.runFor(500);
  } else {
    await page.clock.runFor(at);
    await page.evaluate(() => document.getElementById('cw').contentWindow.postMessage({ lensmithHost: 'still' }, location.origin));
    await page.clock.runFor(2500);   // a little more replay time: nothing may come back in it
  }
  await page.waitForTimeout(900);    // CSS transitions run on the real clock
  const snap = { ...(await frame().evaluate(snapshot)), ...(await frame().evaluate(replayExtras)) };
  delete snap.entryParts;   // a replay that ran to its end leaves its entry elements in the page, hidden; what is on the screen is compared
  delete snap.sandText;
  await ctx.close();
  return { snap, errors };
}

async function replay(browser, engine, width, log) {
  const { server, base } = await startStatic();
  try {
    const a = await replayAt(browser, base, width, null);
    const b = await replayAt(browser, base, width, null);
    const unstable = diff(a.snap, b.snap);
    if (unstable.length) throw new Error(`two replays that ran to the end differ: ${unstable.join('; ')}`);
    if (a.snap.replay !== 'done' || a.snap.sheets || a.snap.ripples) throw new Error(`a replay that ran to its end is not clean: ${JSON.stringify(a.snap)}`);
    const points = [];
    for (let at = 0; at <= 7200; at += STRIDE) points.push(at);
    for (let at = 7200 + 600; at <= 24000; at += 600) points.push(at);
    let next = 0;
    const failures = [];
    await Promise.all(Array.from({ length: WORKERS }, async () => {
      while (next < points.length) {
        const at = points[next]; next += 1;
        try {
          const r = await replayAt(browser, base, width, at);
          const d = diff(a.snap, r.snap);
          if (d.length) throw new Error(`skip to the end at ${at} ms: ${d.join('; ')}`);
          if (r.errors.length) throw new Error(`skip to the end at ${at} ms: the page raised ${r.errors[0]}`);
        } catch (e) { failures.push(String(e.message || e).split('\n')[0].slice(0, 500)); }
      }
    }));
    if (failures.length) {
      const open = failures.filter((f) => /sheets: [1-9]/.test(f)).length;
      throw new Error(`${failures.length} of ${points.length} skips failed (${open} left the source sheet open), first: ${failures[0]}`);
    }
    log.push(`window replay: ${points.length} skips to the end`);
  } finally { server.close(); }
}

const parts = (process.env.SKIP_PARTS || 'app,replay').split(',');   // SKIP_PARTS=replay runs only the published window
try { sameCopies(); } catch (e) { console.log(`FAIL copies: ${e.message}`); console.log('skip flow: FAILED (1 failed)'); process.exit(1); }
let failed = 0;
for (const engine of engines) {
  const browser = await pw[engine].launch();
  for (const width of widths) {
    const log = [];
    let problem = '';
    try {
      if (parts.includes('app')) {
        await sweep(browser, engine, width, 0, STRIDE, log);
        await sweep(browser, engine, width, 1.5, SLOW_STRIDE, log);
        if (width >= 1000) { await failureAfterSkip(browser, engine, log); await rejoinSkip(browser, engine, log); }
        await reduced(browser, engine, width, log);
      }
      if (parts.includes('replay')) await replay(browser, engine, width, log);
    } catch (e) { problem = String(e.message || e); }
    if (problem) { failed += 1; console.log(`FAIL ${engine} ${width}px skip: ${problem}  [${log.join('; ')}]`); }
    else console.log(`PASS ${engine} ${width}px skip: ${log.join('; ')}`);
  }
  await browser.close();
}
console.log(`skip flow: ${failed ? 'FAILED' : 'all passed'} (${failed} failed)`);
process.exit(failed ? 1 : 0);
