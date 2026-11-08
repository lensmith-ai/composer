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
//   CLAIMS   the sentence the checker marked in an insight card's text carries the published window's one claim mark
//            (`.cmark`: a thin amber underline, identical for every claim; the check compares its computed style); the
//            card's headline never does, and pressing the headline or any other part of the card opens the insight sheet. Inside
//            the card a mark is a pointer shortcut (no role, no tab stop: the card is the one button); the keyboard reaches the
//            same claims through the card's sheet, whose marked sentences are controls, on the saved page and on the screen a
//            compose ends on. Pressing
//            one (click, or Enter from the keyboard) opens the app's sheet (#spanSheet) with the verdict in words, the cited
//            article's link and the source passage; Esc, a press elsewhere or Close shuts it and focus goes back to the claim.
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
  await page.locator('#cDeck .cmark').first().waitFor({ state: 'visible', timeout: 30000 });
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

  await step('every checked sentence on a card carries the published window\u2019s one mark, which is a pointer shortcut inside the card button', log, async () => {
    const claims = page.locator('#cDeck .cmark');
    if ((await claims.count()) < 5) throw new Error(`only ${await claims.count()} marked claims`);
    if (await page.locator('#cDeck h4 .cmark').count()) throw new Error('an insight headline is a claim mark: pressing it would not open the insight');
    const first = claims.first();
    // the card is one button; a button inside it would be a nested control, so a card's mark has no role and no tab stop
    if ((await first.getAttribute('role')) !== null || (await first.getAttribute('tabindex')) !== null) throw new Error('a mark inside the card is a second control');
    // the mark is window.css's `.cmark`: padding 0 1px, margin 0 -1px, radius 2px, 1px solid rgba(255,176,32,.6), no text-decoration
    const looks = await claims.evaluateAll((ns) => ns.map((n) => {
      const c = getComputedStyle(n);
      return [c.borderBottomWidth, c.borderBottomStyle, c.borderBottomColor, c.paddingLeft, c.paddingRight, c.marginLeft, c.marginRight,
        c.borderTopLeftRadius, c.backgroundColor, c.textDecorationLine].join('|');
    }));
    const kinds = [...new Set(looks)];
    if (kinds.length !== 1) throw new Error(`claims are drawn in ${kinds.length} styles: ${kinds.join(' / ')}`);
    const want = '1px|solid|rgba(255, 176, 32, 0.6)|1px|1px|-1px|-1px|2px|rgba(0, 0, 0, 0)|none';
    if (kinds[0] !== want) throw new Error(`the mark is ${kinds[0]}, the published window draws ${want}`);
    const legend = await page.locator('#csLegend').count();
    if (!legend) throw new Error('no line says what the underline means');
    const legendText = await page.locator('#csLegend').innerText();
    if (/supported|dashed|wavy|solid|partly/i.test(legendText)) throw new Error(`the legend states a verdict: ${legendText}`);
  });

  const sheet = page.locator('#spanSheet');
  await step('a claim opens its verdict in words, source passage and link in the app\u2019s sheet', log, async () => {
    const first = page.locator('#cDeck .cmark').first();
    await first.click();
    await page.waitForFunction(() => document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
    if ((await sheet.getAttribute('role')) !== 'dialog') throw new Error('the sheet is not a dialog');
    const said = (await sheet.locator('.cmb').textContent()).trim();
    if (!said.startsWith('Supported. The cited article backs this up.')) throw new Error(`verdict in words: "${said}"`);
    const passage = (await sheet.locator('.cmsrc .cmq').first().innerText()).trim();
    if (passage.length < 10) throw new Error(`no source passage: "${passage}"`);
    const href = await sheet.locator('a.cws-link').first().getAttribute('href');
    if (!/^https:\/\/example\.org\//.test(href || '')) throw new Error(`source link ${href}`);
    await page.waitForTimeout(450);
    const b = await sheet.boundingBox();
    if (b.x < -1 || b.x + b.width > width + 1) throw new Error(`the sheet is off screen: ${JSON.stringify(b)}`);
    if (shots) await page.screenshot({ path: `${shots}/${engine}-claim-${width}.png` });
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
    const back = await page.evaluate(() => document.activeElement && document.activeElement.className);
    if (!/icard/.test(back || '')) throw new Error(`focus went to ${back}, not back to the card that holds the claim`);
  });

  await step('a partly supported and a not supported claim look the same and are worded differently', log, async () => {
    const want = [[1, 'Partly supported.', 'implies it without saying it outright'],
                  [2, 'Not supported.', 'Nothing in the cited article backs this up']];
    for (const [card, word, plainPart] of want) {
      const claim = page.locator('#cDeck .icw').nth(card).locator('.cmark').first();
      await claim.click();
      await page.waitForFunction(() => document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
      const said = (await sheet.locator('.cmb').textContent()).trim();
      if (!said.startsWith(word) || !said.includes(plainPart)) throw new Error(`card ${card + 1}: "${said}"`);
      await page.keyboard.press('Escape');
      await page.waitForFunction(() => !document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
    }
    // the sentence the checker marked says how it stands to its source
    const marked = page.locator('#cDeck .icw').nth(2).locator('.gv .cmark').first();
    await marked.click();
    await page.waitForFunction(() => document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
    const rel = (await sheet.locator('.cmb').textContent()).trim();
    if (!/disagrees/.test(rel)) throw new Error(`the marked sentence reads: "${rel}"`);
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
  });

  await step('the header bar stays at the top while you scroll', log, async () => {
    if (width < 768) return;
    await page.evaluate(() => window.scrollTo(0, 700));
    await page.waitForTimeout(250);
    const top = (await box(page, '.hdrow')).y;
    if (Math.abs(top) > 2) throw new Error(`the header scrolled away (top ${top})`);
    await page.evaluate(() => window.scrollTo(0, 0));
  });

  await step('the keyboard reaches a claim through the card; a press elsewhere closes the claim sheet', log, async () => {
    const isOn = () => page.evaluate(() => document.getElementById('spanSheet').classList.contains('on'));
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
    // a pointer press on a mark, then a press elsewhere, then the Close button
    const second = page.locator('#cDeck .cmark').nth(1);
    await second.click();
    await page.waitForFunction(() => document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
    await page.mouse.click(5, 5);
    await page.waitForFunction(() => !document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
    await second.click();
    await page.waitForFunction(() => document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
    await sheet.locator('.close').click();
    if (await isOn()) throw new Error('Close did not shut the sheet');
    // pressing a claim must not also open the card's own sheet
    if (await page.locator('#sheet.on').count()) throw new Error('pressing a claim opened the card sheet');
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
      const brief = await page.evaluate(() => /[?&]job=/.test(location.search) && !!document.querySelector('.cmark'));
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
      await page.locator('.cmark').first().waitFor({ state: 'visible', timeout: 30000 });
      const took = Date.now() - started;
      if (took > 10000) throw new Error(`the brief took ${Math.round(took)} ms to show, the entry animation played every stage in turn`);
      log.push(`brief ${Math.round(took)} ms`);
      // this is the screen the owner sees right after Compose: it must carry the claims too
      await page.locator('#csLegend').waitFor({ state: 'visible', timeout: 10000 });
      await page.waitForTimeout(800);  // the pieces fade in one after the other
      const cards = await page.locator('.cmp-completion-assembly .cdeck .icw').evaluateAll((els) => els.map((e) => {
        const r = e.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y)]; }));
      if (cards.length < 4 || cards[0][1] !== cards[1][1]) throw new Error(`the finished cards are not two in a row: ${JSON.stringify(cards)}`);
      const marked = page.locator('.cmp-completion-assembly .cmark');
      if ((await marked.count()) < 5) throw new Error(`only ${await marked.count()} marked claims on the finished screen`);
      await marked.first().scrollIntoViewIfNeeded();
      await marked.first().click();
      await page.waitForFunction(() => document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
      const said = (await page.locator('#spanSheet .cmb').textContent()).trim();
      if (!said.startsWith('Supported.')) throw new Error(`the first claim reads "${said}"`);
      if ((await page.locator('#spanSheet .cmsrc .cmq').first().innerText()).trim().length < 10) throw new Error('no source passage on the finished screen');
      await page.keyboard.press('Escape');
      await page.waitForFunction(() => !document.getElementById('spanSheet').classList.contains('on'), null, { timeout: 5000 });
      // the card on this screen is its own build: the same presses open the insight sheet, never the claim sheet
      // the cards take presses once the pieces have all faded in (the screen says so on its slot)
      await page.waitForSelector('#cmpSettledContent[data-completion-assembly="settled"]', { timeout: 30000 });
      await page.waitForTimeout(300);
      const screenCard = page.locator('.cmp-completion-assembly .cdeck .icw').first().locator('.icard');
      if ((await screenCard.getAttribute('role')) !== 'button') throw new Error('the card on the finished screen is not a button');
      if (await page.locator('.cmp-completion-assembly h4 .cmark').count()) throw new Error('a headline is a claim mark on the finished screen');
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
