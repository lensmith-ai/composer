// browser_flow.mjs: the stranger test's browser part. Drives the REAL app page of an installed Composer like a
// person, in Chromium and WebKit, at 390x844 and 1280x900, and writes one JSON line per check.
//
//   node browser_flow.mjs CONFIG.json
//   PLAYWRIGHT_MODULE=<path to playwright's index.mjs> picks a Playwright install that is not in node_modules.
//
// CONFIG: {"base": "http://127.0.0.1:8765", "results": "<jsonl>", "shots": "<folder>", "features": {...},
//          "bundled_labels": [...], "expect_bundled": 6, "recorded_texts": [...], "blogs": [...4 page addresses],
//          "local_feed_labels": [...], "only": ["chromium-390", ...]}
// Each check is a row {"id", "status": "pass"|"fail"|"skip", "reason", "engine", "size", "shot"}. A pass always
// says what was seen. A flow this build does not have is a skip that names what is missing (run.sh --strict turns
// every skip into a failure). A step that cannot run because an earlier one failed is a failure that says so.
import { appendFileSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const cfg = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const pw = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = cfg.base.replace(/\/$/, '');
const engines = ['chromium', 'webkit'];
const sizes = [[390, 844], [1280, 900]];
const has = (name) => Boolean(cfg.features && cfg.features[name]);

function write(row) { appendFileSync(cfg.results, JSON.stringify({ t: new Date().toISOString(), ...row }) + '\n'); }
const short = (e) => {
  const lines = String((e && e.message) || e).split('\n');
  const why = lines.find((l) => /intercepts pointer|not visible|not stable|not enabled|detached/.test(l));
  return (lines[0] + (why ? ` (${why.replace(/^[\s-]+/, '').trim()})` : '')).slice(0, 400);
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function api(path, init) {
  const res = await fetch(base + path, init);
  let doc = null;
  try { doc = await res.json(); } catch { doc = null; }
  return { status: res.status, doc };
}

async function shelfJobs() {
  const { doc } = await api('/shelf');
  return ((doc && doc.items) || []).map((r) => r.job);
}

async function waitTerminal(job, seconds) {
  let st = {};
  for (let i = 0; i < seconds * 2; i += 1) {
    st = (await api(`/status/${encodeURIComponent(job)}`)).doc || {};
    if (['verified', 'verification_failed', 'compose_failed'].includes(st.phase) || st.state === 'failed') break;
    await sleep(500);
  }
  return st;
}

async function sheetGone(page) {
  await page.waitForFunction(() => !document.getElementById('cmpSheet') && !document.getElementById('cmpScrim'), null,
    { timeout: 5000 }).catch(() => {});
}

async function openDrawerAction(page, id) {
  for (const menu of ['#cmpMenu', '#sourcesMenu', '#lensesMenu', '#menuBtn']) {
    if (await page.locator(menu).isVisible().catch(() => false)) { await page.click(menu); break; }
  }
  await page.locator(`#${id}`).waitFor({ state: 'visible', timeout: 10000 });
  await page.click(`#${id}`);
}

// True when `text` is on screen for a person: inside an element that has a size, is not hidden or transparent
// (itself or any parent), and is the topmost thing at its own centre once scrolled into view. Text that is only in the
// DOM (under an overlay, in a hidden layer, or behind another screen) does not count.
const SEEN = (want) => {
  const hidden = (el) => {
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return true;
    }
    return false;
  };
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (!n.textContent.includes(want.slice(0, 24))) continue;
    const el = n.parentElement;
    if (!el || hidden(el)) continue;
    el.scrollIntoView({ block: 'center', inline: 'nearest' });
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const top = document.elementFromPoint(Math.min(r.left + r.width / 2, innerWidth - 1), Math.min(r.top + r.height / 2, innerHeight - 1));
    if (top && (top === el || el.contains(top) || top.contains(el))) return true;
  }
  return false;
};
async function seen(page, text) { return page.evaluate(SEEN, text).catch(() => false); }
async function waitSeen(page, text, seconds) {
  for (let i = 0; i < seconds * 2; i += 1) { if (await seen(page, text)) return true; await sleep(500); }
  return false;
}

// The sheets the page opens over a brief, by id; returns the ids open now.
async function openSheets(page) {
  return page.evaluate(() => {
    const known = ['sheet', 'traceSheet', 'srcSheet', 'spanSheet', 'transcriptSheet'].map((id) => document.getElementById(id));
    const any = [...document.querySelectorAll('[role=dialog], [class*=sheet], [class*=Sheet]')];
    return [...new Set([...known, ...any])].filter((el) => {
      if (!el) return false;
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      const onScreen = r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight && cs.visibility !== 'hidden'
        && cs.display !== 'none' && Number(cs.opacity) > 0;
      return onScreen && (el.classList.contains('on') || el.getAttribute('aria-hidden') === 'false' || !el.id);
    }).map((el) => el.id || el.className.toString().split(' ')[0] || el.tagName);
  });
}

// Tick exactly the wanted rows in the open source sheet: wanted ones first, then the rest off (the page keeps at least
// one source ticked, so the other order can leave one on). Reads back what is ticked.
async function pickSources(page, want) {
  await page.locator('#cmpSent .cmpslot[data-kind=sources]').click();
  await page.locator('#cmpSheet .cmprow2').first().waitFor({ timeout: 10000 });
  const rows = page.locator('#cmpSheet .cmprow2');
  const isOn = async (row) => (await row.locator('.cmptick.on').count()) > 0;
  const texts = (await rows.allTextContents()).map((t) => t.trim());
  const wanted = texts.map((t) => want.some((w) => w && t.includes(w)));
  if (!wanted.some(Boolean)) {
    await page.locator('#cmpSheet .cmpdone').click();
    await sheetGone(page);
    return { ok: false, why: `none of ${JSON.stringify(want)} is in the source picker (rows: ${texts.join(' | ')})` };
  }
  for (const pass of [true, false]) {
    for (let i = 0; i < texts.length; i += 1) {
      if (wanted[i] !== pass) continue;
      const row = rows.nth(i);
      if ((await isOn(row)) !== pass && !(await row.isDisabled())) await row.click();
    }
  }
  const on = [];
  for (let i = 0; i < texts.length; i += 1) if (await isOn(rows.nth(i))) on.push(texts[i]);
  await page.locator('#cmpSheet .cmpdone').click();
  await sheetGone(page);
  const extra = on.filter((t) => !want.some((w) => w && t.includes(w)));
  if (extra.length) return { ok: false, why: `could not untick ${extra.join(', ')} in the source picker` };
  return { ok: true, on };
}

// With NO model configured: what does a stranger see when they press Compose? Today an error; the planned fix is a
// plain "add a model key" message. The error is recorded as "known" (expected to change), never as a pass.
async function noModel(browser, engine, width, height) {
  const ctx = await browser.newContext({ viewport: { width, height } });
  const page = await ctx.newPage();
  const file = join(cfg.shots, `${engine}-${width}-no-model.png`);
  const out = (status, reason) => {
    write({ id: 'browser.no_model', status, reason, engine, size: `${width}x${height}`, shot: file });
    console.log(`${status.toUpperCase()} ${engine}-${width} no_model: ${reason}`);
  };
  try {
    await page.goto(base + '/app/', { waitUntil: 'load', timeout: 30000 });
    await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 30000 });
    const picked = await pickSources(page, cfg.local_feed_labels);
    if (!picked.ok) throw new Error(picked.why);
    const [res] = await Promise.all([
      page.waitForResponse((r) => new URL(r.url()).pathname === '/compose' && r.request().method() === 'POST', { timeout: 30000 }),
      page.click('#cmpGo')]);
    let pageDoc = {};
    try { pageDoc = await res.json(); } catch { pageDoc = {}; }
    let job = pageDoc.job || '';
    // what the person sees on the page (visible text only), up to 30 s after pressing Compose
    const MSG = /ProviderError|model key|API key|no key|stopped|did not finish|refused|error|send \{/i;
    let text = '';
    for (let i = 0; i < 60; i += 1) {
      text = await page.evaluate(() => document.body.innerText);
      if (MSG.test(text)) break;
      await sleep(500);
    }
    await page.screenshot({ path: file }).catch(() => {});
    const shown = (text.match(/[^\n]*(ProviderError|model key|API key|no key|stopped|did not finish|refused|error|send \{)[^\n]*/i) || [''])[0].trim().slice(0, 200);
    let engineNote = '';
    if (!job && res.status() === 400) {
      // the page's own request is refused before any model is needed (a separate failure); ask the engine directly
      // what happens with no model, without leaving the page
      const made = await page.evaluate(async (sources) => {
        const r = await fetch('/compose', { method: 'POST', headers: window.cwHeaders(),
          body: JSON.stringify({ sources, lens: 'what changed on the river this week', insights: 3 }) });
        return { status: r.status, doc: await r.json().catch(() => ({})) };
      }, Object.entries((await api('/data/options.json')).doc.source_meta || {})
        .filter(([, m]) => cfg.local_feed_labels.some((l) => (m.label || '').includes(l))).map(([id]) => id));
      job = made.doc.job || '';
      engineNote = `a direct compose answered HTTP ${made.status}`;
    }
    const st = job ? await waitTerminal(job, 60) : {};
    const jobErr = String(st.error || '').slice(0, 160);
    const how = `the page's Compose answered HTTP ${res.status()}${engineNote ? `; ${engineNote}` : ''}${job ? `; the job ended ${st.phase || st.state || '?'}${jobErr ? `: ${jobErr}` : ''}` : ''}`;
    if (/(add|needs?) a model key/i.test(text) && !/ProviderError/.test(text)) {
      out('pass', `the page says, in plain words: "${shown}" (${how})`);
    } else if (/ProviderError/.test(text) || /ProviderError|no API key/i.test(jobErr)) {
      out('known', `expected to change: with no model the page shows "${shown || '(nothing about it)'}" (${how})`);
    } else {
      out('fail', `with no model the page shows "${shown || text.slice(0, 120)}" and no plain "add a model key" message (${how})`);
    }
  } catch (e) {
    await page.screenshot({ path: file }).catch(() => {});
    out('fail', short(e));
  }
  await ctx.close();
}

async function combo(browser, engine, width, height, n) {
  const tag = `${engine}-${width}`;
  const ctx = await browser.newContext({ viewport: { width, height }, reducedMotion: 'no-preference' });
  const page = await ctx.newPage();
  const errors = [];
  const outside = [];
  const consoleErrors = [];
  const badResponses = [];
  page.on('response', (r) => {
    if (r.status() >= 400) badResponses.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
  });
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
  // WebKit logs one CSP refusal of an inline stylesheet for each Playwright screenshot (the style Playwright injects
  // while it takes the picture; measured: 0 with no screenshot, 1 per screenshot, none in Chromium). They are kept
  // apart and at most one per screenshot is excused in page_health; any beyond that count as the page's own.
  const SHOT_STYLE = /^Refused to apply a stylesheet because its hash, its nonce, or 'unsafe-inline' does not appear in the style-src directive/;
  const shotStyleRefusals = [];
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    if (engine === 'webkit' && SHOT_STYLE.test(m.text())) shotStyleRefusals.push(m.text().slice(0, 200));
    else consoleErrors.push(m.text().slice(0, 200));
  });
  page.on('request', (r) => {
    const u = r.url();
    if (!/^(data|blob|about):/.test(u) && new URL(u).origin !== new URL(base).origin) outside.push(u.slice(0, 160));
  });
  let shotNo = 0;
  const shot = async (name) => {
    shotNo += 1;
    const file = join(cfg.shots, `${tag}-${String(shotNo).padStart(2, '0')}-${name}.png`);
    await page.screenshot({ path: file }).catch(() => {});
    return file;
  };
  const rec = async (id, status, reason, name) => {
    const file = await shot(name || id);
    write({ id: `browser.${id}`, status, reason, engine, size: `${width}x${height}`, shot: file });
    console.log(`${status.toUpperCase()} ${tag} ${id}: ${reason}`);
  };
  const check = async (id, fn) => {
    try {
      const out = await fn();
      if (out && out.status) await rec(id, out.status, out.reason);
      else await rec(id, 'pass', String(out || 'ok'));
      return true;
    } catch (e) {
      await rec(id, 'fail', short(e));
      return false;
    }
  };
  const blocked = async (ids, why) => { for (const id of ids) await rec(id, 'fail', `blocked: ${why}`); };

  // 1. the address a stranger types
  const opened = await check('open_root', async () => {
    const res = await page.goto(base + '/', { waitUntil: 'load', timeout: 30000 });
    if (!res || res.status() !== 200) throw new Error(`HTTP ${res && res.status()}`);
    if (!/\/app\/?$/.test(new URL(page.url()).pathname)) throw new Error(`landed on ${page.url()}, not the app page`);
    return `/ opened ${new URL(page.url()).pathname} with HTTP 200`;
  });
  if (!opened) {
    await blocked(['replay_plays', 'narration_off', 'source_picker', 'compose', 'brief_opens'], 'the app page did not open');
    await ctx.close();
    return;
  }

  // 2. the replay: the recorded brief plays on first open
  await check('replay_plays', async () => {
    const t0 = Date.now();
    await page.evaluate(() => {
      window.__strangerMutations = 0;
      new MutationObserver((list) => { window.__strangerMutations += list.length; })
        .observe(document.body, { subtree: true, childList: true, attributes: true, characterData: true });
    });
    const look = async (tries) => {
      for (let i = 0; i < tries; i += 1) {
          for (const t of cfg.recorded_texts || []) if (t && await seen(page, t.slice(0, 28))) return t;
        await sleep(500);
      }
      return '';
    };
    // on first open the page may show the compose sentence over the replay; a person closes it to watch
    let found = await look(6);
    let how = 'on first open';
    if (!found && await page.locator('#cmpGo').isVisible().catch(() => false)) {
      await page.keyboard.press('Escape');
      how = 'after closing the compose screen (Escape)';
      found = await look(40);
    }
    const before = await page.evaluate(() => window.__strangerMutations);
    await sleep(3000);
    const moved = await page.evaluate(() => window.__strangerMutations) - before;
    if (!found) throw new Error(`no text from the recorded brief appeared in ${Math.round((Date.now() - t0) / 1000)} s, ${how}`);
    if (moved < 20) throw new Error(`the recorded brief is on the page but nothing moved in 3 s (${moved} DOM changes)`);
    return `the recorded brief plays ${how}: "${found.slice(0, 40)}" shown, ${moved} DOM changes in 3 s`;
  });

  // 3. narration off: no player, no voice picker
  const opts = (await api('/data/options.json')).doc || {};
  await check('narration_off', async () => {
    const narr = opts.narration || {};
    if (narr.enabled !== false) throw new Error(`options say narration.enabled=${JSON.stringify(narr.enabled)}`);
    const seen = await page.evaluate(() => {
      const vis = (el) => el && el.getBoundingClientRect().height > 0 && getComputedStyle(el).visibility !== 'hidden';
      return {
        audio: [...document.querySelectorAll('audio')].filter((a) => a.getAttribute('src')).length,
        // the "Daily readout" card may stay as a text summary; a player is a play control or a "Listen" offer
        player: [...document.querySelectorAll('#aPlay, .apbtn, .aplay, button')]
          .filter((el) => vis(el) && (el.matches('#aPlay, .apbtn, .aplay') || /^\s*(listen|play)\b/i.test(el.textContent)))
          .map((el) => el.id || el.className || el.textContent.trim().slice(0, 20)),
        listen: [...document.querySelectorAll('.atit, #audioCard *')].filter((el) => vis(el)
          && /listen to this edition/i.test(el.textContent) && !el.children.length).length,
        voice: document.querySelectorAll('#cmpSent .cmpslot[data-kind=voice]').length,
      };
    });
    if (seen.audio || seen.player.length || seen.voice || seen.listen) throw new Error(`player shown: ${JSON.stringify(seen)}`);
    return `options narration.enabled=false, voices=${JSON.stringify(opts.voices || [])}; no audio element, no player, no voice word`;
  });

  // 4. the source picker: the public default sources
  const goCompose = async () => {
    await page.goto(base + '/app/', { waitUntil: 'load', timeout: 30000 });
    await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 30000 });
  };
  await check('source_picker', async () => {
    await goCompose();
    await page.locator('#cmpSent .cmpslot[data-kind=sources]').click();
    await page.locator('#cmpSheet .cmprow2').first().waitFor({ timeout: 10000 });
    const rows = (await page.locator('#cmpSheet .cmprow2').allTextContents()).map((s) => s.trim());
    await shot('source-picker-open');
    const missing = cfg.bundled_labels.filter((l) => !rows.some((r) => r.includes(l)));
    const shown = cfg.bundled_labels.length - missing.length;
    await page.locator('#cmpSheet .cmpdone').click();
    await sheetGone(page);
    if (missing.length) throw new Error(`bundled sources missing from the picker: ${missing.join(', ')} (rows: ${rows.join(' | ')})`);
    if (shown !== cfg.expect_bundled) {
      throw new Error(`the picker shows ${shown} bundled sources (${cfg.bundled_labels.join(', ')}), expected the public default ${cfg.expect_bundled}`);
    }
    return `the picker shows the ${shown} bundled sources: ${cfg.bundled_labels.join(', ')}`;
  });

  // 4b. source packages: a chip that ticks its sources
  if (has('source_packages')) {
    await check('source_packages', async () => {
      await page.locator('#cmpSent .cmpslot[data-kind=sources]').click();
      const chips = page.locator('#cmpSheet .pkgchip');
      await chips.first().waitFor({ timeout: 10000 });
      const nChips = await chips.count();
      const label = ((await chips.first().textContent()) || '').trim();
      await chips.first().click();
      const ticked = await page.locator('#cmpSheet .cmprow2 .cmptick.on').count();
      const now = ((await chips.first().textContent()) || '').trim();
      await shot('package-chip');
      await page.locator('#cmpSheet .cmpdone').click();
      await sheetGone(page);
      if (!ticked) throw new Error(`the package chip "${label}" ticked no sources`);
      return `${nChips} package chip(s); "${label}" ticks ${ticked} sources and then reads "${now}"`;
    });
  } else {
    await rec('source_packages', 'skip', 'this build has no source packages');
  }

  // 5. add a source from a pasted address (local fixture site)
  let newSource = '';
  if (has('add_source')) {
    await check('add_source', async () => {
      const label = `Tidewater notes ${n}`;
      await openDrawerAction(page, 'dSourcesAction');
      await page.locator('#sourcesPage .source-new').click();
      const modal = page.locator('#sourceModal');
      await modal.locator('input[type=url]').fill(cfg.blogs[n - 1]);
      await modal.locator('button.source-test').click();
      await modal.locator('.probe-cand').first().waitFor({ timeout: 60000 });
      const cands = await modal.locator('.probe-cand').allTextContents();
      if (cands.length < 1) throw new Error('no candidate feeds for the pasted page');
      await modal.locator('.probe-cand').first().click();
      await modal.locator('input[type=text]').fill(label);
      await modal.locator('button.source-add').click();
      await page.waitForFunction(() => /Added\./.test(document.querySelector('#sourceModal .source-result').textContent),
        null, { timeout: 30000 });
      await page.click('#sourceClose');
      await page.locator('#sourcesGrid .source-tile', { hasText: label }).waitFor({ timeout: 10000 });
      newSource = label;
      return `pasted ${cfg.blogs[n - 1]}, saw ${cands.length} candidate feeds, added "${label}"; it is in the source library`;
    });
  } else {
    await rec('add_source', 'skip', 'this build has no "add a source from a pasted address" (no /source/probe route in its engine)');
  }

  // 6. make a lens (then compose with it below)
  let newLens = '';
  if (has('make_lens')) {
    await check('make_lens', async () => {
      const name = `River desk ${n}`;
      await openDrawerAction(page, 'dLensesAction');
      await page.locator('#lensesGrid .lens-new').click();
      await page.fill('#lensName', name);
      await page.fill('#lensLookFor', 'Look for open data about rivers and who can use it.');
      if (has('reading_level')) await page.selectOption('#lensReading', { index: 0 });
      await page.click('#lensSubmit');
      await page.waitForFunction(() => /Saved\./.test(document.getElementById('lensSession').textContent), null,
        { timeout: 15000 });
      await page.click('#lensClose');
      await page.locator('#lensesGrid .lens-tile', { hasText: name }).waitFor({ timeout: 10000 });
      newLens = name;
      return `made lens "${name}"; it is in the lens library`;
    });
  } else {
    await rec('make_lens', 'skip', 'this build has no lens making (no /lens/save route in its engine)');
  }

  // 7. compose from the page
  let job = '';
  let via = '';
  let posted = null;
  const composedOk = await check('compose', async () => {
    await goCompose();
    const want = [...cfg.local_feed_labels, newSource].filter(Boolean);
    const picked = await pickSources(page, want);
    if (!picked.ok) throw new Error(picked.why);
    if (newLens) {
      await page.locator('#cmpSent .cmpslot[data-kind=lens]').click();
      await page.locator('#cmpSheet .cmprow2', { hasText: newLens }).click();
      await sheetGone(page);
      const sentence = await page.locator('#cmpSent').textContent();
      if (!sentence.toLowerCase().includes(newLens.toLowerCase())) throw new Error(`the sentence does not name the new lens: ${sentence}`);
    }
    const [res] = await Promise.all([
      page.waitForResponse((r) => new URL(r.url()).pathname === '/compose' && r.request().method() === 'POST',
        { timeout: 30000 }),
      page.click('#cmpGo')]);
    posted = JSON.parse(res.request().postData() || '{}');
    let doc = {};
    try { doc = await res.json(); } catch { doc = {}; }
    if (res.status() !== 202) {
      throw new Error(`Compose was refused: HTTP ${res.status()} ${JSON.stringify(doc).slice(0, 160)}; the page sent ${JSON.stringify(posted).slice(0, 200)}`);
    }
    job = doc.job || '';
    via = 'page';
    await page.waitForURL(/[?&]job=/, { timeout: 30000 }).catch(() => {});
    job = job || new URL(page.url()).searchParams.get('job') || '';
    if (!job) throw new Error('the engine took the compose but the page never named the job');
    return `Compose from the page: HTTP 202, job accepted, sources ${JSON.stringify(posted.sources)}${newLens ? `, lens "${newLens}"` : ''}`;
  });
  if (!composedOk) {
    // the rest of the page is still tested, on a brief made the way the page should have asked for it
    const ids = Object.entries(opts.source_meta || {}).filter(([, m]) => cfg.local_feed_labels.some((l) => (m.label || '').includes(l)))
      .map(([id]) => id);
    const made = await page.evaluate(async ([sources]) => {
      const headers = window.cwHeaders ? window.cwHeaders()
        : { 'Content-Type': 'application/json', 'X-Composer-CSRF': 'same-origin' };
      const r = await fetch('/compose', { method: 'POST', headers,
        body: JSON.stringify({ sources, lens: 'what changed on the river this week', insights: 3 }) });
      return { status: r.status, doc: await r.json().catch(() => ({})) };
    }, [ids]).catch((e) => ({ status: 0, doc: { error: short(e) } }));
    if (made.status === 202 && made.doc.job) {
      job = made.doc.job;
      via = 'the engine\'s own route, because the page\'s Compose failed';
    } else {
      await blocked(['brief_opens', 'insight_cards', 'transcript', 'save', 'shelf', 'trash', 'brief_link'],
        `no brief: the page's Compose failed and so did a direct compose (HTTP ${made.status} ${JSON.stringify(made.doc).slice(0, 120)})`);
    }
  }
  if (has('reading_level')) {
    if (posted && Object.hasOwn(posted, 'reading_level')) await rec('reading_level', 'pass', `the page sent reading_level=${JSON.stringify(posted.reading_level)}`);
    else await rec('reading_level', 'fail', `the compose request carried no reading level: ${JSON.stringify(posted)}`);
  } else {
    await rec('reading_level', 'skip', 'this build has no reading level');
  }
  if (newLens) {
    if (posted && /^custom-/.test(String(posted.lens || ''))) await rec('compose_with_lens', 'pass', `composed with lens ${posted.lens}`);
    else await rec('compose_with_lens', 'fail', `the compose request did not use the new lens: ${JSON.stringify(posted)}`);
  } else {
    await rec('compose_with_lens', has('make_lens') ? 'fail' : 'skip',
      has('make_lens') ? 'blocked: the lens was not made' : 'this build has no lens making');
  }
  if (!job) {
    await finish();
    return;
  }

  // 8. the brief opens: where the person is (the page lands on it after Compose), then from its own link
  const st = await waitTerminal(job, 180);
  const composed = (await api(`/data/live/${encodeURIComponent(job)}/composed.json`)).doc || {};
  const items = composed.items || [];
  const first = String((items[0] && (items[0].insight || items[0].title)) || '');
  const showsBrief = async (seconds) => waitSeen(page, first.slice(0, 40), seconds);
  const pageHead = async () => (await page.evaluate(() => document.body.innerText)).split('\n').map((l) => l.trim())
    .filter(Boolean).slice(0, 4).join(' | ').slice(0, 160);
  const openLink = async () => {
    const asked = [];
    const watch = (r) => { if (r.url().includes(job)) asked.push(new URL(r.url()).pathname); };
    page.on('request', watch);
    await page.goto(`${base}/app/?job=${encodeURIComponent(job)}`, { waitUntil: 'load', timeout: 30000 });
    // the page may play the composition before it lands on the brief; give it the length of a replay
    const shown = await showsBrief(90);
    page.off('request', watch);
    return { shown, asked: [...new Set(asked)] };
  };
  const opensOk = await check('brief_opens', async () => {
    if (st.phase !== 'verified') throw new Error(`the brief ended as ${st.phase || st.state || 'unknown'}${st.error ? `: ${st.error}` : ''}`);
    if (!first) throw new Error('the finished brief has no items');
    if (via === 'page') {
      if (await showsBrief(120)) return `after Compose the page lands on the verified brief: ${items.length} items, first "${first.slice(0, 50)}"`;
      const inDom = await page.evaluate((t) => document.body.innerText.includes(t), first.slice(0, 40));
      throw new Error(`120 s after Compose the finished brief is not on screen (first item "${first.slice(0, 40)}"${inDom ? ', which is in the page text but hidden or covered' : ''}); the screen shows: ${await pageHead()}`);
    }
    const link = await openLink();
    if (link.shown) return `brief (made via ${via}) open at its link: ${items.length} items, first "${first.slice(0, 50)}"`;
    throw new Error(`after 90 s at ?job= the page does not show the brief (first item "${first.slice(0, 40)}"); it shows: ${await pageHead()}; requests naming the job: ${link.asked.length ? link.asked.join(', ') : 'none (the page never asked the engine for it)'}`);
  });
  if (!opensOk) {
    await blocked(['insight_cards', 'transcript', 'save', 'shelf', 'trash', 'brief_link'], 'the brief did not open');
    await finish();
    return;
  }
  // 9. insight cards open
  await check('insight_cards', async () => {
    const cards = page.locator('.cdeck .icw');
    await cards.first().waitFor({ state: 'attached', timeout: 20000 });
    const nCards = await cards.count();
    if (nCards !== items.length) throw new Error(`${nCards} insight cards for ${items.length} items`);
    await cards.first().scrollIntoViewIfNeeded();
    const before = await openSheets(page);
    let open = '';
    let taps = 0;
    while (!open && taps < 2) {  // a second tap only if the first landed while the page was still settling
      taps += 1;
      await cards.first().click();
      for (let i = 0; i < 24 && !open; i += 1) {
        const now = (await openSheets(page)).filter((id) => !before.includes(id));
        if (now.length && await page.evaluate(([ids, t]) => ids.some((id) => {
          const el = document.getElementById(id) || document.querySelector(`.${id}`);
          return el && el.innerText.includes(t);
        }), [now, first.slice(0, 30)])) open = now[0];
        else await sleep(250);
      }
    }
    if (!open) throw new Error(`tapping the first card (${taps} taps) opened no new sheet with its claim (open before: ${before.join(',') || 'none'}; after: ${(await openSheets(page)).join(',') || 'none'})`);
    await shot('card-open');
    // close it the way a person does (its close button, else the dimmed backdrop); Escape would also close the brief
    const closer = page.locator(`#${open} .close, #${open} [aria-label=Close]`).first();
    if (await closer.isVisible().catch(() => false)) await closer.click();
    else await page.evaluate(() => { const s = document.getElementById('scrim'); if (s) s.click(); });
    for (let i = 0; i < 12 && (await openSheets(page)).includes(open); i += 1) await sleep(250);
    if ((await openSheets(page)).includes(open)) throw new Error(`the card's sheet "${open}" opened but does not close`);
    return `${nCards} cards; tapping the first opens "${open}" with its claim${taps > 1 ? ' (on the second tap)' : ''}, and it closes`;
  });

  // 10. transcript sheet
  await check('transcript', async () => {
    const btn = page.locator('.transcriptbtn').first();
    await btn.waitFor({ state: 'attached', timeout: 10000 });
    if (await btn.isDisabled()) throw new Error(`the transcript button is disabled: ${await btn.textContent()}`);
    await btn.scrollIntoViewIfNeeded();
    await btn.click();
    await page.waitForFunction(() => document.getElementById('transcriptSheet').classList.contains('on'), null, { timeout: 5000 });
    const body = (await page.locator('#transcriptBody').textContent()) || '';
    const want = String(composed.transcript || '').trim().slice(0, 40);
    if (!want || !body.includes(want)) throw new Error(`the transcript sheet does not show the brief's script (${body.slice(0, 60)})`);
    await sleep(800);  // the sheet slides up
    const onScreen = await page.evaluate(() => {
      const el = document.getElementById('transcriptSheet');
      const r = el.getBoundingClientRect();
      const top = Math.max(r.top, 0);
      const bottom = Math.min(r.bottom, innerHeight);
      if (bottom - top < 80) return false;
      const hit = document.elementFromPoint(Math.min(r.left + r.width / 2, innerWidth - 1), (top + bottom) / 2);
      return Boolean(hit && el.contains(hit));
    });
    if (!onScreen) throw new Error('the transcript sheet is marked open but is not on screen');
    await shot('transcript-open');
    await page.locator('#transcriptClose').click({ timeout: 5000 });
    await page.waitForFunction(() => !document.getElementById('transcriptSheet').classList.contains('on'), null,
      { timeout: 5000 }).catch(() => {});
    if (await page.evaluate(() => document.getElementById('transcriptSheet').classList.contains('on'))) {
      throw new Error('the transcript sheet opens but its close button does not close it');
    }
    return `the transcript sheet opens on screen with the brief's script (${body.split(/\s+/).length} words) and closes`;
  });

  // 11. save, and it holds after a reload
  const savedOk = await check('save', async () => {
    const btn = page.locator('.cw-save').first();
    await btn.waitFor({ state: 'visible', timeout: 15000 });
    await btn.scrollIntoViewIfNeeded();
    await btn.click();
    let onShelf = false;
    for (let i = 0; i < 30 && !onShelf; i += 1) { onShelf = (await shelfJobs()).includes(job); if (!onShelf) await sleep(500); }
    const note = (await page.locator('.cw-save-note').first().textContent().catch(() => '')) || '';
    if (!onShelf) throw new Error(`Save did not put the brief on the shelf; the page says: ${note.slice(0, 160)}`);
    await page.reload({ waitUntil: 'load' });
    if (!(await waitSeen(page, first.slice(0, 40), 90))) throw new Error('after a reload the saved brief is not on screen');
    const label = (await page.locator('.cw-save').first().textContent().catch(() => '')) || '';
    if (!(await shelfJobs()).includes(job)) throw new Error('the brief left the shelf after a reload');
    if (/^\s*SAVE THIS BRIEF\s*$/i.test(label)) throw new Error('after a reload the page offers Save again, as if the brief were not saved');
    return `saved; still on the shelf after a reload; the page shows "${label.trim().slice(0, 40)}"`;
  });

  // 12. the brief's own link, on a fresh load: before the shelf and trash steps, because trash moves this brief (the
  // only saved one) off the shelf, and a trashed brief is not expected to open from its link
  if (via === 'page') {
    await check('brief_link', async () => {
      const link = await openLink();
      if (link.shown) return `the brief's own link (?job=) opens it on a fresh load`;
      throw new Error(`after 90 s at ?job= the page does not show the brief; it shows: ${await pageHead()}; requests naming the job: ${link.asked.length ? link.asked.join(', ') : 'none (the page never asked the engine for it)'}`);
    });
  } else {
    await rec('brief_link', opensOk ? 'pass' : 'fail', opensOk ? 'the brief opened from its link (see brief_opens)'
      : 'the brief does not open from its link (see brief_opens)');
  }

  // 13. shelf: the saved brief is listed and opens; 14. trash: delete moves it off the shelf. When the page's own
  // Save failed, the brief is saved through the engine's route (what Save should have asked for), so the shelf and
  // trash are still tested, and their rows say so.
  let shelfVia = '';
  if (!savedOk) {
    const r = await page.evaluate(async (j) => {
      const res = await fetch(`/save/${encodeURIComponent(j)}`, { method: 'POST', headers: window.cwHeaders(), body: '{}' });
      return res.status;
    }, job).catch(() => 0);
    if (r === 200 && (await shelfJobs()).includes(job)) shelfVia = ' (the brief was saved through the engine route, because the page\'s Save failed)';
  }
  if (savedOk || shelfVia) {
    const listed = await check('shelf', async () => {
      await page.goto(`${base}/app/`, { waitUntil: 'load' });
      await page.locator('#cmpGo').waitFor({ state: 'visible', timeout: 30000 }).catch(() => {});
      for (const menu of ['#cmpMenu', '#menuBtn']) {
        if (await page.locator(menu).isVisible().catch(() => false)) { await page.click(menu); break; }
      }
      const rows = page.locator('#dBriefs li.lvrowlink');
      if (!(await rows.first().waitFor({ state: 'visible', timeout: 10000 }).then(() => true, () => false))) {
        const says = ((await page.locator('#dBriefs').textContent().catch(() => '')) || '').trim().slice(0, 160);
        throw new Error(`the menu's shelf lists no saved brief although the engine has ${(await shelfJobs()).length} saved; it says: "${says}"`);
      }
      const nRows = await rows.count();
      await shot('shelf-open');
      await rows.first().click();
      await page.waitForURL(/[?&]job=/, { timeout: 15000 });
      const opened = new URL(page.url()).searchParams.get('job');
      if (!(await shelfJobs()).includes(opened)) throw new Error(`the shelf row opened ${opened}, which is not on the shelf`);
      return `the shelf lists ${nRows} saved brief(s); tapping one opens it${shelfVia}`;
    });
    if (listed) {
      await check('trash', async () => {
        await page.goto(`${base}/app/`, { waitUntil: 'load' });
        for (const menu of ['#cmpMenu', '#menuBtn']) {
          if (await page.locator(menu).isVisible().catch(() => false)) { await page.click(menu); break; }
        }
        const before = await shelfJobs();
        const row = page.locator('#dBriefs li.lvrowlink').first();
        await row.locator('.lvdelete').click();
        await page.locator('.lvconfirm-delete').click();
        let after = before;
        for (let i = 0; i < 20 && after.length === before.length; i += 1) { await sleep(500); after = await shelfJobs(); }
        const msg = (await page.locator('#dBriefs').textContent().catch(() => '')) || '';
        if (after.length !== before.length - 1) throw new Error(`Move to trash left the shelf at ${after.length} (was ${before.length}); the page says: ${msg.slice(0, 160)}`);
        return `Move to trash took one brief off the shelf (${before.length} -> ${after.length})${shelfVia}`;
      });
    } else {
      await rec('trash', 'fail', 'blocked: the shelf did not list the saved brief');
    }
  } else {
    await blocked(['shelf', 'trash'], 'Save did not work, and saving through the engine route failed too');
  }
  await finish();

  async function finish() {
    const problems = [];
    const excused = Math.min(shotStyleRefusals.length, shotNo);
    consoleErrors.push(...shotStyleRefusals.slice(excused));
    if (errors.length) problems.push(`${errors.length} page errors: ${errors.slice(0, 3).join(' | ')}`);
    if (outside.length) problems.push(`${outside.length} requests left this machine: ${outside.slice(0, 3).join(' | ')}`);
    if (badResponses.length) problems.push(`${badResponses.length} failed requests: ${[...new Set(badResponses)].slice(0, 6).join(' | ')}`);
    if (consoleErrors.length) problems.push(`${consoleErrors.length} console errors: ${consoleErrors.slice(0, 3).join(' | ')}`);
    await rec('page_health', problems.length ? 'fail' : 'pass',
      problems.length ? problems.join('; ') : '0 page errors, 0 console errors, 0 requests that left this machine'
        + (excused ? ` (${excused} WebKit stylesheet refusals from this test's own ${shotNo} screenshots set aside)` : ''));
    await ctx.close();
  }
}

let n = 0;
for (const engine of engines) {
  let browser;
  try {
    browser = await pw[engine].launch();
  } catch (e) {
    write({ id: 'browser.launch', status: 'fail', reason: `${engine} did not start: ${short(e)}`, engine });
    continue;
  }
  if (cfg.mode === 'no_model') {
    await noModel(browser, engine, 390, 844);
    await browser.close();
    continue;
  }
  for (const [w, h] of sizes) {
    n += 1;
    if (cfg.only && cfg.only.length && !cfg.only.includes(`${engine}-${w}`)) continue;
    try {
      await combo(browser, engine, w, h, n);
    } catch (e) {
      write({ id: 'browser.flow', status: 'fail', reason: `the flow stopped: ${short(e)}`, engine, size: `${w}x${h}` });
    }
  }
  await browser.close();
}
