// rc4_parity_flow.mjs: the compose screen and the saved page agree, on the real app page.
//
//   node tests/browser/rc4_parity_flow.mjs [python]      (python: an interpreter with Composer installed; default python3)
//   PLAYWRIGHT_MODULE=<path to playwright's index.mjs> picks a Playwright install that is not in node_modules.
//   PARITY_SHOTS=<folder> saves the screenshots (fresh and reopened, each width and engine).
//
// For each engine (Chromium, WebKit), against tests/browser/fixture_app.py (the real server, a made-up model, no internet):
//   STAGES   a compose whose feeds and model answer a little late (FIXTURE_FEED_DELAY, FIXTURE_MODEL_DELAY) shows every stage
//            of the entry animation in order, driven by the engine's own progress lines: ACCEPTING BRIEF, GATHERING SOURCES,
//            SORTING SIGNALS, APPLYING LENS, WEAVING BRIEF, CHECKING CLAIMS; and no text on the page, at any moment of the
//            run, reads "[object Object]" (an object turned into text).
//   LINES    the page's own reader of a status (window.__jobLines) takes only text lines: a phase record (an object) is never
//            shown or fed to the animation.
//   LAYOUT   at 1440 and at 390 px a brief that was just composed and the same brief reopened from its link ("?job=") are laid
//            out alike: same header, same date row, the loom in the same place and the same width, the same reading column and
//            insight cards. At 1440 px the reading column is on the left and the loom on the right in both, and the loom
//            stays where it is from the moment the run ends (no jump from the narrow centred layout to the wide one).
//   CARDS    no insight card carries a claim mark or any underline, on the screen a compose ends on and on the saved page (owner
//            decision, as in the published app); opening a card shows its claims, marked, in the insight sheet.
// Prints one PASS / FAIL line per engine and part; exits 1 if any failed.
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import readline from 'node:readline';

const here = dirname(fileURLToPath(import.meta.url));
const python = process.argv[2] || 'python3';
const pw = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const shots = process.env.PARITY_SHOTS || '';
const engines = (process.env.PARITY_ENGINES || 'chromium,webkit').split(',');
const STAGES = ['ACCEPTING BRIEF', 'GATHERING SOURCES', 'SORTING SIGNALS', 'APPLYING LENS', 'WEAVING BRIEF', 'CHECKING CLAIMS'];

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

async function step(name, log, fn) {
  try { await fn(); log.push(`ok ${name}`); } catch (e) {
    throw new Error(`${name}: ${String(e.message || e).split('\n')[0].slice(0, 400)}`);
  }
}

async function stages(browser, engine, log) {
  const server = await startServer({ FIXTURE_FEED_DELAY: '2', FIXTURE_MODEL_DELAY: '10' });
  try {
    await step('every stage is shown in order and nothing reads [object Object]', log, async () => {
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const page = await ctx.newPage();
      const errors = [];
      page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
      await page.goto(server.app, { waitUntil: 'load' });
      await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 15000 });
      await page.click('#cmpGo');
      const seen = [];
      let bad = null;
      const t0 = Date.now();
      while (Date.now() - t0 < 120000) {
        const s = await page.evaluate(() => {
          const text = document.body.innerText + ' ' + document.documentElement.outerHTML;  // the text a person reads and every attribute
          const el = document.getElementById('cwWordRaster') || document.getElementById('cwReducedWords');
          return { word: el ? el.textContent.trim().toUpperCase() : '', bad: text.includes('[object Object]'),
                   done: /[?&]job=/.test(location.search) && !!document.querySelector('.icard') && !document.getElementById('cmpEntryTransition') };
        }).catch(() => ({ word: '', bad: false, done: false }));
        if (s.bad && bad === null) bad = Math.round((Date.now() - t0) / 100) / 10;
        if (STAGES.includes(s.word) && seen[seen.length - 1] !== s.word) seen.push(s.word);
        if (s.done) break;
        await page.waitForTimeout(120);
      }
      if (bad !== null) throw new Error(`"[object Object]" was on the page at ${bad} s`);
      const order = STAGES.filter((w) => seen.includes(w));
      if (order.join() !== STAGES.join()) throw new Error(`stages shown: ${seen.join(' > ') || 'none'}; wanted ${STAGES.join(' > ')}`);
      if (seen.join() !== order.join()) throw new Error(`stages out of order: ${seen.join(' > ')}`);
      if (errors.length) throw new Error(`page error: ${errors[0]}`);
      const final = await page.evaluate(() => (document.body.innerText + ' ' + document.documentElement.outerHTML).includes('[object Object]'));
      if (final) throw new Error('"[object Object]" is on the finished page');
      await ctx.close();
    });
    await step('the status reader takes text lines only', log, async () => {
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const page = await ctx.newPage();
      await page.goto(server.app, { waitUntil: 'load' });
      const got = await page.evaluate(() => ({
        phases: window.__jobLines({ progress: [{ at: 'x', phase: 'queued' }, { at: 'x', phase: 'fetching' }] }),
        lines: window.__jobLines({ progress: [{ phase: 'queued' }], lines: ['compose started', { phase: 'x' }, 'fetching a…'] }),
        published: window.__jobLines({ progress: ['compose started', 'done ✓'] }),
        none: window.__jobLines(null) }));
      if (got.phases.length || got.none.length) throw new Error(`a phase record became a line: ${JSON.stringify(got)}`);
      if (got.lines.join('|') !== 'compose started|fetching a…') throw new Error(`lines: ${JSON.stringify(got.lines)}`);
      if (got.published.join('|') !== 'compose started|done ✓') throw new Error(`published progress: ${JSON.stringify(got.published)}`);
      await ctx.close();
    });
  } finally {
    await stop(server);
  }
}

// the same parts, found in the compose screen (which = 1) and in the saved page (which = 0)
const PARTS = {
  title: ['#mhTitle', '.cmp-composed-mast h2'], menu: ['#menuBtn', '.cmp-composed-mast .mbtn:first-child'],
  info: ['#infoBtn', '.cmp-composed-mast .mbtn:last-child'], date: ['.daterow .sub', '#cwMastSub'], ainote: ['#aiNote', '#cwAiNote'],
  status: ['.daterow .status', '#cwMastStatus'], stage: ['#stageCard', '#cmpStage'], readout: ['#audioCard', '#cmpSettledContent .audio'],
  legend: ['#csLegend', '#csLegend'],
  card1: ['#cDeck .icw:nth-child(1) .icard', '#cmpSettledContent .icw:nth-child(1) .icard'],
  card2: ['#cDeck .icw:nth-child(2) .icard', '#cmpSettledContent .icw:nth-child(2) .icard'],
  card3: ['#cDeck .icw:nth-child(3) .icard', '#cmpSettledContent .icw:nth-child(3) .icard'] };

async function boxes(page, which) {
  return page.evaluate(([parts, w]) => {
    const o = {};
    for (const [k, sels] of Object.entries(parts)) {
      const e = [...document.querySelectorAll(sels[w])].find((n) => { const r = n.getBoundingClientRect(); return r.width > 1 && r.height > 1; });
      if (!e) { o[k] = null; continue; }
      const r = e.getBoundingClientRect();
      o[k] = { x: Math.round(r.x), y: Math.round(r.y + scrollY), w: Math.round(r.width), h: Math.round(r.height) };
    }
    return o;
  }, [PARTS, which]);
}

// no claim mark and no underline anywhere in a card's headline or text; `where` is the card's container
async function noCardMarks(page, where, what) {
  const r = await page.evaluate((w) => {
    const cards = [...document.querySelectorAll(w + ' .icard')];
    const marks = document.querySelectorAll(w + ' .cmark, ' + w + ' .icard mark, ' + w + ' .icard u').length;
    const lines = [];
    for (const c of cards) for (const n of c.querySelectorAll('h4, h4 *, .gv, .gv *')) {
      const st = getComputedStyle(n);
      if (parseFloat(st.borderBottomWidth) > 0 && st.borderBottomStyle !== 'none') lines.push('border-bottom on ' + n.tagName);
      if (/underline/.test(st.textDecorationLine)) lines.push('text-decoration on ' + n.tagName);
    }
    return { cards: cards.length, marks, lines };
  }, where);
  if (r.cards < 4) throw new Error(`${what}: only ${r.cards} insight cards`);
  if (r.marks) throw new Error(`${what}: ${r.marks} claim marks on the insight cards`);
  if (r.lines.length) throw new Error(`${what}: underlines on the cards: ${r.lines.slice(0, 3).join(', ')}`);
}

async function layout(browser, engine, width, log) {
  const server = await startServer();
  try {
    await step(`a fresh compose and the reopened brief are laid out alike at ${width} px`, log, async () => {
      const ctx = await browser.newContext({ viewport: { width, height: width < 600 ? 844 : 900 } });
      const page = await ctx.newPage();
      const errors = [];
      page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
      await page.goto(server.app, { waitUntil: 'load' });
      await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 15000 });
      await page.click('#cmpGo');
      // the loom's box from the first moment it shows to the end of the run: on a wide screen it is in its slot throughout
      let shownAt = null;
      const t0 = Date.now();
      for (;;) {
        const r = await page.evaluate(() => {
          const el = document.getElementById('cmpStage');
          if (!el || Number(getComputedStyle(el).opacity) < 0.9) return { shown: false };
          const b = el.getBoundingClientRect();
          return { shown: true, x: Math.round(b.x), y: Math.round(b.y + scrollY), w: Math.round(b.width), h: Math.round(b.height) };
        });
        if (r.shown && !shownAt) shownAt = r;
        const over = await page.evaluate(() => /[?&]job=/.test(location.search) && !!document.querySelector('#cmpSettledContent .icard')
          && !document.getElementById('cmpEntryTransition'));
        if (over) break;
        if (Date.now() - t0 > 120000) throw new Error('the run did not end');
        await page.waitForTimeout(100);
      }
      await page.waitForTimeout(7000);  // the pieces fade in one after the other, then the loom is adopted
      const job = new URL(page.url()).searchParams.get('job');
      // the loom keeps its slot from the end of the run on: two looks a moment apart are the same box
      const early = await boxes(page, 1);
      await page.waitForTimeout(1500);
      const fresh = await boxes(page, 1);
      for (const k of ['stage', 'title', 'readout']) {
        if (!fresh[k] || !early[k] || ['x', 'y', 'w', 'h'].some((d) => Math.abs(fresh[k][d] - early[k][d]) > 1)) {
          throw new Error(`${k} moved after the run ended: ${JSON.stringify(early[k])} then ${JSON.stringify(fresh[k])}`);
        }
      }
      if (width >= 768) {
        if (!shownAt) throw new Error('the loom never showed');
        const here = fresh.stage;
        if (['x', 'y', 'w', 'h'].some((d) => Math.abs(shownAt[d] - here[d]) > 2)) {
          throw new Error(`the loom jumped: ${JSON.stringify(shownAt)} when it first showed, ${JSON.stringify(here)} at the end`);
        }
      }
      await noCardMarks(page, '#cmpSettledContent', 'the screen a compose ends on');
      if (shots) await page.screenshot({ path: `${shots}/${engine}-fresh-${width}.png` });
      await page.goto(new URL(`/app/?job=${job}`, server.app).href, { waitUntil: 'load' });
      await page.locator('#cDeck .icard').first().waitFor({ state: 'visible', timeout: 30000 });
      await page.waitForTimeout(2500);
      const saved = await boxes(page, 0);
      await noCardMarks(page, '#cDeck', 'the saved page');
      await page.locator('#cDeck .icw').first().locator('.icard').click();
      await page.locator('#sheet.on').waitFor({ timeout: 5000 });
      if (!(await page.locator('#sheet #shPoints .cmark').count())) throw new Error('the opened insight sheet shows no claims');
      await page.keyboard.press('Escape');
      await page.waitForFunction(() => !document.getElementById('sheet').classList.contains('on'), null, { timeout: 5000 });
      if (shots) await page.screenshot({ path: `${shots}/${engine}-saved-${width}.png` });
      const problems = [];
      for (const k of Object.keys(PARTS)) {
        const f = fresh[k], s = saved[k];
        if (!f || !s) { problems.push(`${k} missing (${f ? 'saved' : 'fresh'})`); continue; }
        // across: every part sits in the same columns, to 2 px
        if (Math.abs(f.x - s.x) > 2 || Math.abs(f.w - s.w) > 2) problems.push(`${k} across: fresh x${f.x} w${f.w}, saved x${s.x} w${s.w}`);
      }
      // down: the header, the date row and the loom's top edge are where the saved page puts them (3 px); on a wide screen so is
      // the reading column's first piece, beside the loom; the loom's height may differ a little (the picture is drawn at its
      // own size) but not by more than 40 px
      for (const k of ['title', 'menu', 'info', 'date', 'ainote', 'status', 'stage']) {
        if (fresh[k] && saved[k] && Math.abs(fresh[k].y - saved[k].y) > 3) problems.push(`${k} down: fresh y${fresh[k].y}, saved y${saved[k].y}`);
      }
      if (Math.abs(fresh.stage.h - saved.stage.h) > 40) problems.push(`stage height: fresh ${fresh.stage.h}, saved ${saved.stage.h}`);
      if (width >= 768) {
        if (!(fresh.stage.x > fresh.readout.x + fresh.readout.w - 2)) problems.push('fresh: the loom is not beside the reading column');
        if (Math.abs(fresh.readout.y - saved.readout.y) > 3) problems.push(`readout down: fresh y${fresh.readout.y}, saved y${saved.readout.y}`);
      } else {
        if (!(fresh.readout.y >= fresh.stage.y + fresh.stage.h)) problems.push('fresh: the brief does not follow the loom on a phone');
      }
      // the spaces between the reading column's pieces
      const gap = (b, a, c) => b[c].y - (b[a].y + b[a].h);
      for (const [a, c] of [['readout', 'legend'], ['legend', 'card1']]) {
        if (Math.abs(gap(fresh, a, c) - gap(saved, a, c)) > 6) problems.push(`space between ${a} and ${c}: fresh ${gap(fresh, a, c)}, saved ${gap(saved, a, c)}`);
      }
      if (problems.length) throw new Error(problems.join('; '));
      if (errors.length) throw new Error(`page error: ${errors[0]}`);
      await ctx.close();
    });
  } finally {
    await stop(server);
  }
}

const results = [];
for (const engine of engines) {
  const browser = await pw[engine].launch();
  const parts = [['stages', (log) => stages(browser, engine, log)],
    ['layout-1440', (log) => layout(browser, engine, 1440, log)], ['layout-390', (log) => layout(browser, engine, 390, log)]];
  for (const [name, run] of parts) {
    const log = [];
    try { await run(log); results.push([engine, name, true, log.join('; ')]); } catch (e) {
      results.push([engine, name, false, `${log.join('; ')} | ${e.message}`]);
    }
  }
  await browser.close();
}
let failed = 0;
for (const [engine, name, ok, text] of results) {
  console.log(`${ok ? 'PASS' : 'FAIL'} ${engine} ${name}: ${text}`);
  if (!ok) failed += 1;
}
console.log(failed ? `rc4 parity flow: ${failed} failed` : 'rc4 parity flow: all passed (0 failed)');
process.exit(failed ? 1 : 0);
