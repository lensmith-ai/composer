// parity_flow.mjs: the app page, driven like a person, against the real server with no internet and no key.
//
//   node tests/browser/parity_flow.mjs [python]      (python: an interpreter with Composer installed; default python3)
//   PLAYWRIGHT_MODULE=<path to playwright's index.mjs> picks a Playwright install that is not in node_modules.
//
// For each engine (Chromium, WebKit) and width (390, 1280) it starts tests/browser/fixture_app.py (a fresh server, a
// local HTTPS blog, a made-up model), then on the page:
//   1. Sources > Add a source: pastes the blog's page address, checks it, sees the candidate feeds (the comments
//      feed marked), picks the blog's feed, names it and adds it; the new source is in the library.
//   2. Lenses > Make a lens: name, what it looks for, register, reading level; saves it; opens it again and edits
//      it, which makes revision 2 of the same lens.
//   3. Compose: the package chip is offered; picks the new source and one more, picks the new lens, composes, and
//      waits for the brief, which must cite the new source's items.
// Fails on any page error, any request that leaves this machine, or any step that does not happen.
// Prints one PASS / FAIL line per engine and width; exits 1 if any failed.
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import readline from 'node:readline';

const here = dirname(fileURLToPath(import.meta.url));
const python = process.argv[2] || 'python3';
const pw = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const only = (process.env.PARITY_ONLY || '').split(',').filter(Boolean);  // e.g. chromium-390, for debugging
const engines = ['chromium', 'webkit'];
const widths = [[390, 844], [1280, 800]];
const shots = process.env.PARITY_SHOTS || '';

async function startServer() {
  const child = spawn(python, [join(here, 'fixture_app.py')], { stdio: ['ignore', 'pipe', 'pipe'] });
  child.stderrText = '';
  child.stderr.on('data', (d) => { child.stderrText = (child.stderrText + d).slice(-4000); });
  const lines = readline.createInterface({ input: child.stdout });
  const [line] = await Promise.race([once(lines, 'line'),
    new Promise((_, reject) => setTimeout(() => reject(new Error('the fixture server did not start')), 30000))]);
  return { child, ...JSON.parse(line) };
}

async function step(page, name, fn, log) {
  try {
    await fn();
    log.push(`ok ${name}`);
  } catch (e) {
    if (shots) await page.screenshot({ path: `${shots}/fail-${name.replace(/\W+/g, '-')}.png` }).catch(() => {});
    throw new Error(`${name}: ${String(e.message || e).split('\n')[0].slice(0, 300)}`);
  }
}

async function openDrawerAction(page, id) {
  // the compose screen has its own menu button over the brief's; a library page has a third
  const menus = ['#cmpMenu', '#sourcesMenu', '#lensesMenu', '#menuBtn'];
  for (const menu of menus) {
    if (await page.locator(menu).isVisible()) { await page.click(menu); break; }
  }
  await page.locator(`#${id}`).waitFor({ state: 'visible', timeout: 10000 });
  await page.click(`#${id}`);
}

// A picker sheet is taken out of the page 300 ms after it closes; a person does not tap the next word that fast.
async function sheetGone(page) {
  await page.waitForFunction(() => !document.getElementById('cmpSheet') && !document.getElementById('cmpScrim'), null,
    { timeout: 5000 });
}

// The lens form puts the cursor in its name field 50 ms after it opens; typing before that can land in the name.
async function nameFocused(page) {
  await page.waitForFunction(() => document.activeElement && document.activeElement.id === 'lensName', null,
    { timeout: 5000 });
}

async function flow(page, server, log) {
  const app = new URL(server.app);
  await step(page, 'open the app page', async () => {
    const res = await page.goto(server.app, { waitUntil: 'load', timeout: 30000 });
    if (!res || res.status() !== 200) throw new Error(`HTTP ${res && res.status()}`);
    await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 15000 });
  }, log);

  await step(page, 'add a source from a pasted address', async () => {
    await openDrawerAction(page, 'dSourcesAction');
    await page.locator('#sourcesPage .source-new').click();
    const modal = page.locator('#sourceModal');
    await modal.locator('input[type=url]').fill(server.blog);
    await modal.locator('button.source-test').click();
    await modal.locator('.probe-cand').first().waitFor({ timeout: 60000 });
    const rows = await modal.locator('.probe-cand').allTextContents();
    if (rows.length !== 2) throw new Error(`expected 2 candidate feeds, saw ${rows.length}: ${rows.join(' | ')}`);
    if (!rows[0].includes('Tidewater opens its river gauge readings')) throw new Error(`first row: ${rows[0]}`);
    if (!rows[1].includes('looks like reader comments')) throw new Error(`comments row not marked: ${rows[1]}`);
    await modal.locator('.probe-cand').first().click();
    const name = modal.locator('input[type=text]');
    if ((await name.inputValue()) !== 'Tidewater Field Notes') throw new Error(`suggested name ${await name.inputValue()}`);
    await name.fill('Tidewater notes');
    await modal.locator('button.source-add').click();
    await page.waitForFunction(() => /Added\./.test(document.querySelector('#sourceModal .source-result').textContent),
      null, { timeout: 30000 });
    await page.click('#sourceClose');
    await page.locator('#sourcesGrid .source-tile', { hasText: 'Tidewater notes' }).waitFor({ timeout: 10000 });
  }, log);

  await step(page, 'make a lens, then edit it', async () => {
    await openDrawerAction(page, 'dLensesAction');
    await page.locator('#lensesGrid .lens-new').click();
    await nameFocused(page);
    await page.fill('#lensName', 'River desk');
    await page.fill('#lensLookFor', 'Look for open data about rivers and who can use it.');
    await page.selectOption('#lensRegister', { label: 'Sceptical' });
    await page.selectOption('#lensReading', { label: 'Plain' });
    await page.click('#lensSubmit');
    await page.waitForFunction(() => /Saved\..*revision 1/.test(document.getElementById('lensSession').textContent),
      null, { timeout: 15000 });
    await page.click('#lensClose');
    await page.locator('#lensesGrid .lens-tile', { hasText: 'River desk' }).click();
    await page.waitForFunction(() => document.getElementById('lensModalTitle').textContent === 'Edit lens', null,
      { timeout: 10000 });
    await nameFocused(page);
    if ((await page.inputValue('#lensLookFor')) !== 'Look for open data about rivers and who can use it.') {
      throw new Error('the edit form did not show the saved words');
    }
    const register = await page.$eval('#lensRegister', (s) => s.options[s.selectedIndex].text);
    if (register !== 'Sceptical') throw new Error(`the edit form shows register ${register}`);
    await page.fill('#lensLookFor', 'Look for open river data, who can use it, and what it leaves out.');
    await page.click('#lensSubmit');
    await page.waitForFunction(() => /Saved\..*revision 2/.test(document.getElementById('lensSession').textContent),
      null, { timeout: 15000 });
    await page.click('#lensClose');
    const tiles = await page.locator('#lensesGrid .lens-tile', { hasText: 'River desk' }).count();
    if (tiles !== 1) throw new Error(`expected one River desk lens, saw ${tiles}`);
  }, log);

  await step(page, 'compose with them and see the brief', async () => {
    await page.goto(server.app, { waitUntil: 'load' });
    await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('#cmpSent .cmpslot[data-kind=sources]').click();
    const sheet = page.locator('#cmpSheet');
    // the package chip applies its two sources; then the new source is ticked and one package source unticked
    const chip = sheet.locator('.pkgchip[data-pkg=ai-labs]');
    await chip.click();
    const ticked = async (label) => (await sheet.locator('.cmprow2', { hasText: label }).locator('.cmptick.on').count()) > 0;
    if (!(await ticked('Lab A notes')) || !(await ticked('Lab B notes')) || (await ticked('Tidewater notes'))) {
      throw new Error('the package chip did not apply its sources');
    }
    if (!/\u2713 AI labs/.test(await sheet.locator('.pkgchip[data-pkg=ai-labs]').textContent())) {
      throw new Error('the package chip is not marked as applied');
    }
    await sheet.locator('.cmprow2', { hasText: 'Tidewater notes' }).click();
    await sheet.locator('.cmprow2', { hasText: 'Lab B notes' }).click();
    if (!(await ticked('Tidewater notes')) || (await ticked('Lab B notes'))) throw new Error('the source rows did not toggle');
    if (!/modified/.test(await sheet.locator('.pkgchip[data-pkg=ai-labs]').textContent())) {
      throw new Error('the package chip does not say it was changed');
    }
    await sheet.locator('.cmpdone').click();
    await sheetGone(page);
    await page.locator('#cmpSent .cmpslot[data-kind=lens]').click();
    await page.locator('#cmpSheet .cmprow2', { hasText: 'River desk' }).click();
    await page.waitForFunction(() => /River desk/i.test(document.getElementById('cmpSent').textContent), null,
      { timeout: 10000 });
    await sheetGone(page);
    const [posted] = await Promise.all([
      page.waitForRequest((r) => r.url() === new URL('/compose', app).href && r.method() === 'POST', { timeout: 30000 }),
      page.click('#cmpGo')]);
    const body = JSON.parse(posted.postData());
    if (body.sources.join() !== 'google-ai,tidewater-notes' && body.sources.join() !== 'tidewater-notes,google-ai'
        || !/^custom-/.test(body.lens) || body.reading_level === undefined) {
      throw new Error(`compose body ${JSON.stringify(body)}`);
    }
    await page.waitForURL(/[?&]job=/, { timeout: 30000 });
    await page.waitForFunction(() => /Tidewater opens its river gauge readings|Volunteers mapped forty culverts/
      .test(document.body.innerText), null, { timeout: 120000 });
    // the engine finishes the check and seal; the page then shows the checked brief under the lens's name
    const job = new URL(page.url()).searchParams.get('job');
    let phase = '';
    for (let i = 0; i < 240 && !['verified', 'verification_failed', 'failed'].includes(phase); i += 1) {
      const res = await fetch(new URL(`/status/${job}`, app));
      phase = (await res.json()).phase || '';
      if (!['verified', 'verification_failed', 'failed'].includes(phase)) await new Promise((r) => setTimeout(r, 500));
    }
    if (phase !== 'verified') throw new Error(`the brief ended as ${phase || 'unknown'}, not verified`);
    await page.waitForFunction(() => /River desk/.test(document.body.innerText)
      && !/checks running/i.test(document.body.innerText), null, { timeout: 60000 });
  }, log);
}

let failed = 0;
for (const engine of engines) {
  const browser = await pw[engine].launch();
  for (const [width, height] of widths) {
    if (only.length && !only.includes(`${engine}-${width}`)) continue;
    const server = await startServer();
    const ctx = await browser.newContext({ viewport: { width, height }, reducedMotion: 'reduce' });
    const page = await ctx.newPage();
    const problems = [];
    const log = [];
    const local = new URL(server.app).origin;
    page.on('pageerror', (e) => problems.push(`page error: ${String(e).slice(0, 200)}`));
    if (process.env.PARITY_DEBUG) {
      page.on('request', (r) => console.error(`> ${r.method()} ${r.url().slice(0, 120)}`));
      page.on('console', (m) => console.error(`console ${m.type()}: ${m.text().slice(0, 200)}`));
    }
    page.on('request', (r) => {
      const u = r.url();
      if (!/^(data|blob|about):/.test(u) && new URL(u).origin !== local) problems.push(`outside request: ${u.slice(0, 160)}`);
    });
    try {
      await flow(page, server, log);
    } catch (e) {
      problems.unshift(String(e.message || e));
      if (server.child.stderrText.trim()) problems.push(`server said: ${server.child.stderrText.trim().slice(-600)}`);
    }
    if (shots) await page.screenshot({ path: `${shots}/${engine}-${width}.png` }).catch(() => {});
    const label = `${engine} ${width}px`;
    if (problems.length) {
      failed += 1;
      console.log(`FAIL ${label}: ${problems.join(' | ')}  [${log.join('; ')}]`);
    } else {
      console.log(`PASS ${label}: ${log.join('; ')}`);
    }
    await ctx.close();
    if (server.child.exitCode === null) {
      const exited = once(server.child, 'exit');
      server.child.kill('SIGTERM');
      await Promise.race([exited, new Promise((r) => setTimeout(r, 5000))]);
      if (server.child.exitCode === null) server.child.kill('SIGKILL');
    }
  }
  await browser.close();
}
const ran = only.length ? only.length : engines.length * widths.length;
console.log(`parity flow: ${ran - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
