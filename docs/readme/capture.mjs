// capture.mjs: take the README screenshots from the static demo in docs/demo (the recorded brief, replayed).
// Serve docs/demo on this machine first, for example: python3 -m http.server 8000 --bind 127.0.0.1 --directory docs/demo
//   PLAYWRIGHT_MODULE=<path to playwright's index.mjs> node docs/readme/capture.mjs http://127.0.0.1:8000 <out dir>
// Writes brief.png, cards.png and card-open.png to <out dir>: a 390-pixel-wide phone screen at pixel ratio 2, dark
// theme. Every word in them comes from the recorded brief. The files in docs/readme were then reduced to a
// 256-colour palette (ffmpeg palettegen and paletteuse) to keep each one small.
const mod = process.env.PLAYWRIGHT_MODULE;
const [base, out] = process.argv.slice(2);
if (!mod || !base || !out) {
  console.error('usage: PLAYWRIGHT_MODULE=<playwright index.mjs> node capture.mjs <demo url> <out dir>');
  process.exit(2);
}
const { chromium } = await import(mod);
const browser = await chromium.launch();

async function settled(height) {
  const ctx = await browser.newContext({
    viewport: { width: 390, height },
    deviceScaleFactor: 2,
    colorScheme: 'dark',
    isMobile: true,
    hasTouch: true,
  });
  const page = await ctx.newPage();
  await page.goto(base + '/window/index.html#replay');
  await page.waitForSelector('body[data-replay="done"]', { timeout: 120000 });
  await page.waitForTimeout(1500);
  return page;
}

// 1. The finished brief, as the replay leaves it.
let page = await settled(844);
await page.screenshot({ path: out + '/brief.png' });

// 2. Further down the same screen: the row of insight cards.
await page.evaluate(() => {
  const cmp = document.getElementById('cmp');
  cmp.scrollTop = cmp.scrollHeight;
});
await page.waitForTimeout(600);
await page.screenshot({ path: out + '/cards.png' });
await page.context().close();

// 3. The first card, opened. The phone is made tall enough for the whole card to fit, then the picture is cut to it.
page = await settled(1400);
await page.locator('button.lw-open').first().click();
await page.waitForTimeout(1200);
const box = await page.locator('#sheet').boundingBox();
await page.screenshot({ path: out + '/card-open.png', clip: box });
await browser.close();
console.log('wrote brief.png, cards.png, card-open.png to ' + out);
