// browser_smoke.mjs: the first slice of the stranger test's browser part (test-plan section 4), runnable today.
// Opens each page in Chromium and WebKit at 390, 1280 and 1600 pixels wide and fails on any console error, any
// page error, any failed request, or any request that leaves this machine (the pages promise 0 outside requests).
// The full flow (compose, cards, save, shelf, narration) is pending phases P2/P3, which bring the ported page.
//
//   node tests/stranger/browser_smoke.mjs <url> [<url> ...]     (serve the pages on 127.0.0.1 first)
//   PLAYWRIGHT_MODULE=<path to playwright's index.mjs> picks a Playwright install that is not in node_modules.
// Prints one PASS / FAIL line per page, engine and width; exits 1 if any failed.
const mod = process.env.PLAYWRIGHT_MODULE || 'playwright';
const urls = process.argv.slice(2);
if (!urls.length) {
  console.error('usage: node tests/stranger/browser_smoke.mjs <url> [<url> ...]');
  process.exit(2);
}
const pw = await import(mod);
const engines = ['chromium', 'webkit'];
const widths = [[390, 844], [1280, 800], [1600, 1000]];
let failed = 0;
for (const name of engines) {
  const browser = await pw[name].launch();
  for (const url of urls) {
    const local = new URL(url).origin;
    for (const [width, height] of widths) {
      const ctx = await browser.newContext({ viewport: { width, height }, reducedMotion: 'reduce' });
      const page = await ctx.newPage();
      const problems = [];
      page.on('console', (m) => { if (m.type() === 'error') problems.push(`console: ${m.text().slice(0, 160)}`); });
      page.on('pageerror', (e) => problems.push(`page error: ${String(e).slice(0, 160)}`));
      page.on('requestfailed', (r) => problems.push(`failed request: ${r.url().slice(0, 160)}`));
      page.on('request', (r) => {
        const u = r.url();
        if (!u.startsWith('data:') && !u.startsWith('blob:') && !u.startsWith('about:') && new URL(u).origin !== local) {
          problems.push(`outside request: ${u.slice(0, 160)}`);
        }
      });
      let status = 0;
      try {
        const res = await page.goto(url, { waitUntil: 'load', timeout: 30000 });
        status = res ? res.status() : 0;
        await page.waitForTimeout(1500);
        const text = (await page.textContent('body')) || '';
        if (status !== 200) problems.push(`HTTP ${status}`);
        if (text.trim().length < 20) problems.push('the page shows no text');
      } catch (e) {
        problems.push(`load: ${String(e).slice(0, 160)}`);
      }
      const label = `${name} ${width}px ${url}`;
      if (problems.length) {
        failed += 1;
        console.log(`FAIL ${label}: ${problems.join(' | ')}`);
      } else {
        console.log(`PASS ${label}: HTTP ${status}, 0 console errors, 0 outside requests`);
      }
      await ctx.close();
    }
  }
  await browser.close();
}
console.log(`browser smoke: ${engines.length * urls.length * widths.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
