// csp_flow.mjs: the sand animation draws under the page's own Content-Security-Policy (style-src 'self': no inline style).
//
//   node tests/browser/csp_flow.mjs [python]      (python: an interpreter with Composer installed; default python3)
//   PLAYWRIGHT_MODULE=<path to playwright's index.mjs> picks a Playwright install that is not in node_modules.
//   CSP_ENGINES=webkit,chromium (default both; the owner tests in Safari, so WebKit is the one that matters)
//
// Why: the sand canvas was given its position and stacking with `el.style.cssText = "..."`, an inline style that
// WebKit's policy check refused on a page whose policy has no 'unsafe-inline' (the Hugging Face Space builder met it,
// 2026-11-09). The fix sets each property through the style object. For each engine this checks, with a listener for
// `securitypolicyviolation` and for console messages about the policy installed before the page's own scripts run:
//   DEMO  docs/demo/window (the page's own meta policy): after Replay the sand canvas anchored to the loom exists, is
//         position:absolute with z-index 3 (the values the old code set), and has ink; no violation at any moment.
//   APP   the real server (tests/browser/fixture_app.py, its real policy header): a compose draws its sand and word canvases
//         (ink on them) and no violation is reported from the start of the page to the end of the run.
// Prints one PASS / FAIL line per engine and part; exits 1 if any failed.
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import net from 'node:net';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import readline from 'node:readline';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..', '..');
const python = process.argv[2] || 'python3';
const pw = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const engines = (process.env.CSP_ENGINES || 'webkit,chromium').split(',');

const WATCH = () => {
  window.__csp = [];
  document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(`${e.violatedDirective} ${String(e.sourceFile || '').split('/').pop()}:${e.lineNumber}`));
};
const INK = `(() => [...document.querySelectorAll('canvas')].map((c) => {
  let ink = -1;
  try { const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; ink = 0; for (let k = 3; k < d.length; k += 4) if (d[k]) ink++; } catch (e) { ink = -1; }
  const s = getComputedStyle(c);
  return { cls: c.className, position: s.position, z: s.zIndex, ink };
}))()`;

async function freePort() {
  return await new Promise((resolve) => { const s = net.createServer(); s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => resolve(p)); }); });
}
async function untilTrue(page, fn, ms) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { const v = await page.evaluate(fn).catch(() => null); if (v) return v; await page.waitForTimeout(200); }
  return null;
}
async function stop(child) {
  if (child.exitCode !== null) return;
  const exited = once(child, 'exit');
  child.kill('SIGTERM');
  await Promise.race([exited, new Promise((r) => setTimeout(r, 5000))]);
  if (child.exitCode === null) child.kill('SIGKILL');
}

async function demo(browser) {
  const port = await freePort();
  const srv = spawn(python, ['-m', 'http.server', String(port), '--bind', '127.0.0.1', '--directory', join(root, 'docs', 'demo')], { stdio: 'ignore' });
  try {
    await new Promise((r) => setTimeout(r, 1000));
    const page = await (await browser.newContext({ viewport: { width: 420, height: 760 } })).newPage();
    const console_ = [];
    page.on('console', (m) => { if (/content security|refused to apply|violates/i.test(m.text())) console_.push(m.text().slice(0, 160)); });
    await page.addInitScript(WATCH);
    await page.goto(`http://127.0.0.1:${port}/window/index.html`, { waitUntil: 'load' });
    await page.click('#cmpGo');
    const rest = await untilTrue(page, `(${INK}).find((c) => /rest/.test(c.cls) && c.ink > 0) || null`, 40000);
    if (!rest) throw new Error('the sand canvas anchored to the loom never appeared with ink in it');
    if (rest.position !== 'absolute' || rest.z !== '3') throw new Error(`anchored sand canvas is position ${rest.position}, z-index ${rest.z}; wanted absolute and 3`);
    const v = await page.evaluate(() => window.__csp);
    if (v.length || console_.length) throw new Error(`policy violations: ${[...v, ...console_].join(' | ')}`);
    return `anchored sand canvas ${rest.cls}: absolute, z-index 3, ${rest.ink} inked pixels, 0 violations`;
  } finally { await stop(srv); }
}

async function app(browser) {
  const child = spawn(python, [join(here, 'fixture_app.py')], { stdio: ['ignore', 'pipe', 'pipe'], env: process.env });
  try {
    const lines = readline.createInterface({ input: child.stdout });
    const [line] = await Promise.race([once(lines, 'line'), new Promise((_, rej) => setTimeout(() => rej(new Error('the fixture server did not start')), 30000))]);
    const { app: url } = JSON.parse(line);
    const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
    const console_ = [];
    page.on('console', (m) => { if (/content security|refused to apply|violates/i.test(m.text())) console_.push(m.text().slice(0, 160)); });
    await page.addInitScript(WATCH);
    await page.goto(url, { waitUntil: 'load' });
    await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 15000 });
    await page.click('#cmpGo');
    const drawn = await untilTrue(page, `(${INK}).filter((c) => c.ink > 0).length >= 2 || null`, 60000);
    if (!drawn) throw new Error('the sand and word canvases never drew');
    const done = await untilTrue(page, `(/[?&]job=/.test(location.search) && !!document.querySelector('.icard') && !document.getElementById('cmpEntryTransition')) || null`, 150000);
    if (!done) throw new Error('the compose did not finish');
    const v = await page.evaluate(() => window.__csp);
    if (v.length || console_.length) throw new Error(`policy violations: ${[...v, ...console_].join(' | ')}`);
    return 'real app: sand and word canvases inked, compose finished, 0 violations';
  } finally { await stop(child); }
}

const results = [];
for (const engine of engines) {
  const browser = await pw[engine].launch();
  for (const [name, run] of [['demo-window', demo], ['app-compose', app]]) {
    try { results.push([engine, name, true, await run(browser)]); } catch (e) { results.push([engine, name, false, String(e.message || e).split('\n')[0].slice(0, 400)]); }
  }
  await browser.close();
}
let failed = 0;
for (const [engine, name, ok, text] of results) { console.log(`${ok ? 'PASS' : 'FAIL'} ${engine} ${name}: ${text}`); if (!ok) failed += 1; }
console.log(failed ? `csp flow: ${failed} failed` : 'csp flow: all passed (0 failed)');
process.exit(failed ? 1 : 0);
