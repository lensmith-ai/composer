// claim_intro_flow.mjs: the wide layout, the claim marks and the entry animation, on the real app page.
//
//   node tests/browser/claim_intro_flow.mjs [python]      (python: an interpreter with Composer installed; default python3)
//   PLAYWRIGHT_MODULE=<path to playwright's index.mjs> picks a Playwright install that is not in node_modules.
//   CLAIM_SHOTS=<folder> saves a screenshot of the brief and of an open claim at every width.
//
// For each engine (Chromium, WebKit), against tests/browser/fixture_app.py (the real server, a made-up model, no internet):
//   LAYOUT   at 390, 834, 1280 and 1440 px a composed brief opens with no sideways scroll; the phone keeps its single
//            column (the page is no wider than the screen), a tablet and a laptop use the width (page wider than 430 px, the
//            loom beside the reading column, two columns of insight cards from 960 px).
//   CLAIMS   insight cards carry NO claim marks and no underlines (owner decision, as in the published app); pressing the
//            headline or any other part of the card opens the insight sheet, whose marked claims are controls (a keyboard
//            reaches them through the card). Pressing a claim there opens the app's claim sheet (#spanSheet); Esc shuts it.
//   INTRO    with the feeds answering 8 s late (a slow connection), the sand has formed the first words within 3 s of
//            pressing Compose, before any feed has answered; Esc, a click, or the Skip button ends the animation at once and
//            shows the composition; with reduced motion nothing is drawn on a canvas and there is no Skip button.
// Prints one PASS / FAIL line per engine and part; exits 1 if any failed.
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import readline from 'node:readline';

const here = dirname(fileURLToPath(import.meta.url));
const python = process.argv[2] || 'python3';
const pw = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const shots = process.env.CLAIM_SHOTS || '';
const engines = (process.env.CLAIM_ENGINES || 'chromium,webkit').split(',');
const INTRO_BUDGET_MS = 3000;

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

// compose a brief the way the page does (same-origin POST) and wait for its check to finish
async function composeBrief(app) {
  const origin = new URL(app).origin;
  const res = await fetch(new URL('/compose', app), { method: 'POST', headers: {
    'Content-Type': 'application/json', 'X-Composer-CSRF': 'same-origin', 'X-Composer-Pass': 'local', Origin: origin },
  body: JSON.stringify({ sources: ['google-ai', 'deepmind', 'huggingface'], lens: 'system-improvements', voice: null,
    insights: 5, reading_level: 'standard' }) });
  const job = (await res.json()).job;
  if (!job) throw new Error('the engine gave no job');
  let phase = '';
  for (let i = 0; i < 240 && !['verified', 'verification_failed', 'failed'].includes(phase); i += 1) {
    phase = (await (await fetch(new URL(`/status/${job}`, app))).json()).phase || '';
    if (phase !== 'verified') await new Promise((r) => setTimeout(r, 250));
  }
  if (phase !== 'verified') throw new Error(`the brief ended as ${phase || 'unknown'}`);
  return job;
}

async function step(name, log, fn) {
  try { await fn(); log.push(`ok ${name}`); } catch (e) {
    throw new Error(`${name}: ${String(e.message || e).split('\n')[0].slice(0, 300)}`);
  }
}

const box = async (page, sel) => page.locator(sel).first().boundingBox();

async function layoutAndClaims(browser, engine, server, width, log) {
  const ctx = await browser.newContext({ viewport: { width, height: width < 500 ? 844 : 1000 }, reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
  const job = await composeBrief(server.app);
  await page.goto(new URL(`/app/?job=${job}`, server.app).href, { waitUntil: 'load' });
  await page.locator('#cDeck .icard').first().waitFor({ state: 'visible', timeout: 30000 });
  await page.waitForTimeout(600);

  await step('no sideways scroll', log, async () => {
    const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (over > 0) throw new Error(`the page is ${over}px wider than the screen`);
  });
  await step('the page uses the width it has', log, async () => {
    const col = await box(page, '.col');
    if (width < 768) {
      if (col.width > 431) throw new Error(`the phone column is ${col.width}px`);
    } else {
      if (col.width < Math.min(width - 80, 700)) throw new Error(`the column is only ${Math.round(col.width)}px wide at ${width}px`);
      const loom = await box(page, '#stageCard');
      const cards = await box(page, '#cDeck');
      if (!(loom.x >= cards.x + cards.width - 2)) throw new Error('the loom does not stand beside the reading column');
    }
    const cardBoxes = [];
    for (const c of await page.locator('#cDeck .icw').all()) cardBoxes.push(await c.boundingBox());
    if (cardBoxes.length < 4) throw new Error(`only ${cardBoxes.length} insight cards`);
    const across = cardBoxes.filter((b) => Math.abs(b.y - cardBoxes[0].y) < 4).length;
    const want = width >= 960 ? 2 : 1;
    if (width >= 768 && across !== want) throw new Error(`${across} cards in a row at ${width}px, wanted ${want}`);
    // on a phone the cards are a row you swipe, so only the first must fit; from 768 px every card sits inside the page
    for (const b of width < 768 ? cardBoxes.slice(0, 1) : cardBoxes) if (b.x + b.width > width + 1) throw new Error('a card runs off the screen');
  });
  if (shots) await page.screenshot({ path: `${shots}/${engine}-brief-${width}.png` });

  await step('insight cards carry no claim marks and no underlines; the strip above them names no verdict', log, async () => {
    const r = await page.evaluate(() => {
      const lines = [];
      const cards = [...document.querySelectorAll('#cDeck .icard')];
      for (const c of cards) for (const n of c.querySelectorAll('h4, h4 *, .gv, .gv *')) {
        const st = getComputedStyle(n);
        if (parseFloat(st.borderBottomWidth) > 0 && st.borderBottomStyle !== 'none') lines.push('border-bottom on ' + n.tagName);
        if (/underline/.test(st.textDecorationLine)) lines.push('text-decoration on ' + n.tagName);
      }
      return { cards: cards.length, marks: document.querySelectorAll('#cDeck .cmark, #cDeck .icard mark').length, lines };
    });
    if (r.cards < 4) throw new Error(`only ${r.cards} insight cards`);
    if (r.marks) throw new Error(`${r.marks} claim marks on the insight cards`);
    if (r.lines.length) throw new Error(`underlines on the cards: ${r.lines.join(', ')}`);
    if (!(await page.locator('#csLegend').count())) throw new Error('no line says where the claims are');
    const legendText = await page.locator('#csLegend').innerText();
    if (/supported|dashed|wavy|solid|partly/i.test(legendText)) throw new Error(`the legend states a verdict: ${legendText}`);
  });

  const sheet = page.locator('#spanSheet');
  await step('an opened insight shows its claims; a claim opens its source in the app\u2019s sheet', log, async () => {
    const card = page.locator('#cDeck .icw').first().locator('.icard');
    await card.click();
    await page.locator('#sheet.on').waitFor({ timeout: 5000 });
    const claims = page.locator('#sheet #shPoints .cmark');
    if (!(await claims.count())) throw new Error('the opened insight shows no marked claims');
    await claims.first().click();
    await page.waitForFunction(() => document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
    if ((await sheet.getAttribute('role')) !== 'dialog') throw new Error('the claim sheet is not a dialog');
    if ((await sheet.locator('.cmq').first().innerText()).trim().length < 5) throw new Error('the claim sheet does not quote the phrase');
    await page.waitForTimeout(450);
    const b = await sheet.boundingBox();
    if (b.x < -1 || b.x + b.width > width + 1) throw new Error(`the sheet is off screen: ${JSON.stringify(b)}`);
    if (shots) await page.screenshot({ path: `${shots}/${engine}-claim-${width}.png` });
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.getElementById('sheet').classList.contains('on'), null, { timeout: 5000 });
  });

  await step('the header bar stays at the top while you scroll', log, async () => {
    if (width < 768) return;
    await page.evaluate(() => window.scrollTo(0, 700));
    await page.waitForTimeout(250);
    const top = (await box(page, '.hdrow')).y;
    if (Math.abs(top) > 2) throw new Error(`the header scrolled away (top ${top})`);
    await page.evaluate(() => window.scrollTo(0, 0));
  });

  await step('the keyboard reaches a claim through the card', log, async () => {
    // Enter on the card opens the insight sheet, whose marked sentences are controls a keyboard reaches
    const card = page.locator('#cDeck .icw').nth(1).locator('.icard');
    await card.focus();
    await page.keyboard.press('Enter');
    await page.locator('#sheet.on').waitFor({ timeout: 5000 });
    const inSheet = page.locator('#sheet #shPoints .cmark').first();
    if ((await inSheet.getAttribute('role')) !== 'button' || (await inSheet.getAttribute('tabindex')) !== '0') throw new Error('a claim in the insight sheet is not a keyboard control');
    await inSheet.focus();
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.getElementById('sheet').classList.contains('on'), null, { timeout: 5000 });
  });

  await step('the card opens its insight sheet from its headline, its text, its info dot and the keyboard', log, async () => {
    const closeSheet = async () => {
      await page.keyboard.press('Escape');
      await page.waitForFunction(() => !document.getElementById('sheet').classList.contains('on'), null, { timeout: 5000 });
    };
    const card = page.locator('#cDeck .icw').first().locator('.icard');
    if ((await card.getAttribute('role')) !== 'button' || (await card.getAttribute('tabindex')) !== '0') throw new Error('the card is not a keyboard control');
    for (const [name, where] of [['headline', 'h4'], ['info dot', '.infodot'], ['the card\u2019s own corner', null]]) {
      if (where) await card.locator(where).first().click(); else await card.click({ position: { x: 10, y: 10 } });
      await page.locator('#sheet.on').waitFor({ timeout: 5000 });
      const said = (await page.locator('#sheet').innerText()).trim();
      if (!/Finding 1/.test(said)) throw new Error(`pressing the ${name} opened a sheet that does not hold the insight: "${said.slice(0, 80)}"`);
      if (await page.locator('#spanSheet.on').count()) throw new Error(`pressing the ${name} opened the claim sheet`);
      await closeSheet();
    }
    for (const key of ['Enter', ' ']) {
      await card.focus();
      await page.keyboard.press(key);
      await page.locator('#sheet.on').waitFor({ timeout: 5000 });
      await closeSheet();
    }
  });
  if (errors.length) throw new Error(`page error: ${errors[0]}`);
  await ctx.close();
}

async function intro(browser, engine, log) {
  // each step gets its own server: the engine composes two briefs at a time and the slow feeds keep them busy
  let server = await startServer({ FIXTURE_FEED_DELAY: '8' });
  const fresh = async () => { await stop(server); server = await startServer({ FIXTURE_FEED_DELAY: '8' }); };
  try {
    await step('the first words are formed within 3 s, before any feed answers', log, async () => {
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const page = await ctx.newPage();
      await page.goto(server.app, { waitUntil: 'load' });
      await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 15000 });
      const started = await page.evaluate(() => performance.now());
      await page.click('#cmpGo');
      const handle = await page.waitForFunction(() => window.__sandSentenceState && window.__sandSentenceState.mode === 'settled'
        && window.__sandSentenceState.label, null, { timeout: 12000, polling: 'raf' });
      const ms = (await page.evaluate(() => performance.now())) - started;
      const label = await handle.jsonValue();
      if (ms > INTRO_BUDGET_MS) throw new Error(`the first words (${label}) took ${Math.round(ms)} ms, more than ${INTRO_BUDGET_MS} ms`);
      const brief = await page.evaluate(() => /[?&]job=/.test(location.search) && !!document.querySelector('.icard'));
      if (brief) throw new Error('the brief was already there: the test did not wait on a slow feed');
      log.push(`intro ${Math.round(ms)} ms`);
      await ctx.close();
    });
    await fresh();
    await step('Esc ends the animation and shows the composition', log, async () => {
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const page = await ctx.newPage();
      await page.goto(server.app, { waitUntil: 'load' });
      await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 15000 });
      await page.click('#cmpGo');
      await page.locator('#cwEntrySkip').waitFor({ state: 'visible', timeout: 5000 });
      await page.waitForTimeout(700);
      await page.keyboard.press('Escape');
      await page.waitForFunction(() => !document.querySelector('canvas.cmp-entry-sand, canvas.sand-word-canvas')
        && !document.getElementById('cwEntrySkip'), null, { timeout: 2000 });
      await page.waitForFunction(() => {
        const s = document.getElementById('cmpStage');
        return s && !s.classList.contains('entry-loom-withheld') && getComputedStyle(s).opacity === '1';
      }, null, { timeout: 2000 }).catch(() => { throw new Error('the composition is not shown after Esc'); });
      await ctx.close();
    });
    await fresh();
    await step('a click and the Skip button end it too', log, async () => {
      for (const how of ['click', 'button']) {
        const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
        const page = await ctx.newPage();
        await page.goto(server.app, { waitUntil: 'load' });
        await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 15000 });
        await page.click('#cmpGo');
        await page.locator('#cwEntrySkip').waitFor({ state: 'visible', timeout: 5000 });
        await page.waitForTimeout(500);
        if (how === 'click') await page.mouse.click(300, 300); else await page.click('#cwEntrySkip');
        await page.waitForFunction(() => !document.querySelector('canvas.cmp-entry-sand, canvas.sand-word-canvas'), null, { timeout: 2000 })
          .catch(() => { throw new Error(`the animation did not end after a ${how}`); });
        await ctx.close();
      }
    });
    await stop(server);
    server = await startServer();  // feeds answer at once: the stages arrive all together and must not be played one by one
    await step('a quick run lands on its checked brief within 10 s', log, async () => {
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const page = await ctx.newPage();
      await page.goto(server.app, { waitUntil: 'load' });
      await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 15000 });
      const started = Date.now();  // the page turns to a new document when the brief is ready: use this side's clock
      await page.click('#cmpGo');
      await page.locator('.icard').first().waitFor({ state: 'visible', timeout: 30000 });
      const took = Date.now() - started;
      if (took > 10000) throw new Error(`the brief took ${Math.round(took)} ms to show, the entry animation played every stage in turn`);
      log.push(`brief ${Math.round(took)} ms`);
      // this is the screen the owner sees right after Compose: it must carry the claims too
      await page.locator('#csLegend').waitFor({ state: 'visible', timeout: 10000 });
      await page.waitForTimeout(800);  // the pieces fade in one after the other
      const cards = await page.locator('.cmp-completion-assembly .cdeck .icw').evaluateAll((els) => els.map((e) => {
        const r = e.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y)]; }));
      if (cards.length < 4 || cards[0][1] !== cards[1][1]) throw new Error(`the finished cards are not two in a row: ${JSON.stringify(cards)}`);
      if (await page.locator('.cmp-completion-assembly .cmark').count()) throw new Error('a claim mark is on the finished screen\u2019s cards');
      await page.locator('.cmp-completion-assembly .cdeck .icw').first().locator('.icard').scrollIntoViewIfNeeded();
      // the card on this screen is its own build: the same presses open the insight sheet, never the claim sheet
      // the cards take presses once the pieces have all faded in (the screen says so on its slot)
      await page.waitForSelector('#cmpSettledContent[data-completion-assembly="settled"]', { timeout: 30000 });
      await page.waitForTimeout(300);
      const screenCard = page.locator('.cmp-completion-assembly .cdeck .icw').first().locator('.icard');
      if ((await screenCard.getAttribute('role')) !== 'button') throw new Error('the card on the finished screen is not a button');
      const insightOpen = () => page.evaluate(() => [...document.querySelectorAll('.sheet.on')].map((n) => n.id));
      for (const how of ['headline', 'corner', 'Enter', 'Space']) {
        await screenCard.scrollIntoViewIfNeeded();
        if (how === 'headline') await screenCard.locator('h4').click();
        else if (how === 'corner') await screenCard.click({ position: { x: 10, y: 10 } });
        else { await screenCard.focus(); await page.keyboard.press(how === 'Enter' ? 'Enter' : ' '); }
        await page.waitForTimeout(700);
        const open = await insightOpen();
        if (open.includes('spanSheet') || !open.length) throw new Error(`${how} on the finished screen's card opened ${JSON.stringify(open)}, not the insight sheet`);
        await page.evaluate(() => { document.querySelectorAll('.sheet.on').forEach((n) => n.classList.remove('on')); const sc = document.getElementById('scrim'); if (sc) sc.classList.remove('on'); });
      }
      const tag = (await page.locator('.cmp-completion-assembly .cdeck .icw').nth(1).locator('.prooftag').textContent()).trim();
      if (!/^partly supported/.test(tag)) throw new Error(`a partly supported card is tagged "${tag}"`);
      await ctx.close();
    });
    await fresh();
    await step('a failed compose keeps its Retry button, and pressing it works', log, async () => {
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const page = await ctx.newPage();
      // the engine answers the compose request 3 s late, then refuses: the failure arrives with the words on screen
      await page.route('**/compose', async (route) => {
        await new Promise((r) => setTimeout(r, 3000));
        await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'the test engine refused' }) });
      });
      await page.goto(server.app, { waitUntil: 'load' });
      await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 15000 });
      await page.click('#cmpGo');
      await page.locator('#cwRetry.show').waitFor({ state: 'visible', timeout: 15000 });
      if (await page.locator('#cwEntrySkip').count()) throw new Error('the Skip button stayed after the failure');
      await page.click('#cwRetry');
      await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 5000 });
      await ctx.close();
    });
    await fresh();
    await step('with reduced motion nothing is drawn and there is no Skip button', log, async () => {
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' });
      const page = await ctx.newPage();
      await page.goto(server.app, { waitUntil: 'load' });
      await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 15000 });
      await page.click('#cmpGo');
      for (let i = 0; i < 12; i += 1) {
        await page.waitForTimeout(250);
        const drawn = await page.evaluate(() => document.querySelectorAll('canvas.cmp-entry-sand, canvas.sand-word-canvas').length
          + (document.getElementById('cwEntrySkip') ? 1 : 0));
        if (drawn) throw new Error(`reduced motion still drew ${drawn} animation element(s)`);
      }
      const words = await page.evaluate(() => (document.getElementById('cwReducedWords') || {}).textContent || '');
      if (!words.trim()) throw new Error('reduced motion shows no status words');
      await ctx.close();
    });
  } finally {
    await stop(server);
  }
}

let failed = 0;
for (const engine of engines) {
  const browser = await pw[engine].launch();
  for (const width of [390, 834, 1280, 1440]) {
    const server = await startServer();
    const log = [];
    let problem = '';
    try { await layoutAndClaims(browser, engine, server, width, log); } catch (e) {
      problem = String(e.message || e);
      if (server.child.stderrText.trim()) problem += ` | server said: ${server.child.stderrText.trim().slice(-400)}`;
    }
    await stop(server);
    if (problem) { failed += 1; console.log(`FAIL ${engine} ${width}px layout+claims: ${problem}  [${log.join('; ')}]`); }
    else console.log(`PASS ${engine} ${width}px layout+claims: ${log.length} steps`);
  }
  const log = [];
  let problem = '';
  try { await intro(browser, engine, log); } catch (e) { problem = String(e.message || e); }
  if (problem) { failed += 1; console.log(`FAIL ${engine} intro: ${problem}  [${log.join('; ')}]`); }
  else console.log(`PASS ${engine} intro: ${log.join('; ')}`);
  await browser.close();
}
console.log(`claim and intro flow: ${failed ? 'FAILED' : 'all passed'} (${failed} failed)`);
process.exit(failed ? 1 : 0);
