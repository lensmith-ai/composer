(function () {
  'use strict';
  var T = { slot: 300, open: 600, first: 1250, gap: 270, scroll: 460, done: 4350, close: 4550, go: 6050 };
  var LENGTH = 6450;
  function ease(x) {
    x = x < 0 ? 0 : x > 1 ? 1 : x;
    return x < 0.5 ? 2 * x * x : 1 - (2 - 2 * x) * (2 - 2 * x) / 2;
  }
  function touch(el) {
    var r = el.getBoundingClientRect();
    var d = document.createElement('div');
    d.className = 'lw-touch';
    d.setAttribute('aria-hidden', 'true');
    d.style.left = (r.left + r.width / 2) + 'px';
    d.style.top = (r.top + r.height / 2) + 'px';
    d.addEventListener('animationend', function () { d.remove(); });
    document.body.appendChild(d);
  }
  function create(ctx) {
    var ROWS = ctx.rows || [];
    var fired = {};
    var sheet = null;
    var scrim = null;
    var done = null;
    var rows = [];
    var plan = [];
    var stopped = false;
    function once(name, fn) {
      if (fired[name]) return;
      fired[name] = true;
      fn();
    }
    function open() {
      scrim = document.createElement('div');
      scrim.className = 'cmpscrim';
      scrim.setAttribute('aria-hidden', 'true');
      sheet = document.createElement('div');
      sheet.className = 'cmpsheet';
      sheet.setAttribute('aria-hidden', 'true');
      var head = document.createElement('div');
      head.className = 'cmpshead';
      var h = document.createElement('h4');
      h.textContent = 'What goes in';
      done = document.createElement('button');
      done.className = 'cmpdone';
      done.type = 'button';
      done.tabIndex = -1;
      done.textContent = 'Done';
      head.appendChild(h);
      head.appendChild(done);
      sheet.appendChild(head);
      var q = document.createElement('input');
      q.className = 'cmpsearch';
      q.tabIndex = -1;
      q.readOnly = true;
      q.placeholder='search ' + ROWS.length + ' sources';
      sheet.appendChild(q);
      var list = document.createElement('div');
      sheet.appendChild(list);
      ROWS.forEach(function (label) {
        var b = document.createElement('button');
        b.className = 'cmprow2';
        b.type = 'button';
        b.tabIndex = -1;
        var t = document.createElement('span');
        t.className = 'cmptick on';
        t.textContent = '✓';
        var l = document.createElement('span');
        l.className = 'rl';
        l.textContent = label;
        b.appendChild(t);
        b.appendChild(l);
        list.appendChild(b);
        rows.push({ label: label, tick: t, el: b });
      });
      document.body.appendChild(scrim);
      document.body.appendChild(sheet);
    }
    function planUnticks() {
      var at = T.first;
      var top = 0;
      var view = sheet.clientHeight;
      var max = sheet.scrollHeight - view;
      rows.forEach(function (r) {
        if (ctx.sources.indexOf(r.label) >= 0) return;
        if (r.el.offsetTop + r.el.offsetHeight > top + view - 8 && top < max) {
          plan.push({ at: at, from: top, to: max });
          top = max;
          at += T.scroll + 120;
        }
        plan.push({ at: at, row: r });
        at += T.gap;
      });
    }
    // Skip to the end: the sheet, its scrim, the touch ripples and the pressed states go, and the slot reads as it does
    // after the replay has run (what step() leaves at T.close + 900). Nothing here can open again.
    function finish() {
      stopped = true;
      if (scrim) scrim.remove();
      if (sheet) sheet.remove();
      scrim = null;
      sheet = null;
      var ripples = document.querySelectorAll('.lw-touch');
      for (var i = 0; i < ripples.length; i++) ripples[i].remove();
      ctx.slot.textContent = ctx.chosen;
      ctx.slot.setAttribute('aria-label', 'sources: ' + ctx.chosen);
      ctx.slot.classList.remove('lw-tap');
      ctx.go.classList.remove('lw-press');
    }
    function step(t) {
      if (stopped) return;
      if (t >= T.slot) once('slot', function () {
        touch(ctx.slot);
        ctx.slot.classList.add('lw-tap');
      });
      if (t >= T.open) once('open', open);
      if (t >= T.open + 40) once('on', function () {
        scrim.classList.add('on');
        sheet.classList.add('on');
        planUnticks();
      });
      for (var i = 0; i < plan.length; i++) {
        var p = plan[i];
        if (t < p.at) continue;
        if (p.row) once('row' + i, untick(p.row));
        else sheet.scrollTop = p.from + (p.to - p.from) * ease((t - p.at) / T.scroll);
      }
      if (t >= T.done) once('done', function () { touch(done); });
      if (t >= T.close) once('close', function () {
        scrim.classList.remove('on');
        sheet.classList.remove('on');
        ctx.slot.textContent = ctx.chosen;
        ctx.slot.setAttribute('aria-label', 'sources: ' + ctx.chosen);
      });
      if (t >= T.close + 900) once('settle', function () {
        ctx.slot.classList.remove('lw-tap');
        scrim.remove();
        sheet.remove();
      });
      if (t >= T.go) once('go', function () {
        touch(ctx.go);
        ctx.go.classList.add('lw-press');
      });
    }
    function untick(r) {
      return function () {
        touch(r.tick);
        r.tick.classList.remove('on');
        r.tick.textContent = '';
      };
    }
    return { step: step, finish: finish };
  }
  window.__lwComposeStep = { LENGTH: LENGTH, create: create };
}());
(function () {
  'use strict';
  var COMPOSE_STEP = window.__lwComposeStep;
  var BEATS = [['compose', 6450], ['sand', 3500], ['words', 11300], ['weave', 1300], ['brief', 1600]];
  var HOLD_SPEED = 0.6;
  var WORDS_SPEED = 2.4;
  var HOSTED = false;
  try {
    HOSTED = window.parent !== window && window.parent.location.origin === window.location.origin;
  } catch (err) {
    HOSTED = false;
  }
  try {
    var ratio = Math.min(2, window.devicePixelRatio || 1);
    Object.defineProperty(window, 'devicePixelRatio', { configurable: true, get: function () { return ratio; } });
  } catch (err) {
    ratio = 1;
  }
  var held = false;
  var heldAt = 0;
  var waiting = [];
  var dropped = false;
  function later(fn) {
    if (dropped) return;
    if (held) waiting.push(fn);
    else fn();
  }
  var perf = window.performance;
  var realNow = perf.now.bind(perf);
  var realRaf = window.requestAnimationFrame.bind(window);
  var realCancelRaf = window.cancelAnimationFrame.bind(window);
  var realTimeout = window.setTimeout.bind(window);
  var warp = { k: 1, real0: realNow(), warp0: realNow() };
  function warpedNow() {
    return warp.warp0 + ((held ? heldAt : realNow()) - warp.real0) * warp.k;
  }
  function speed(k) {
    var w = warpedNow();
    warp.real0 = realNow();
    warp.warp0 = w;
    warp.k = k;
    rates(k);
  }
  function rates(k) {
    if (held) k = 0;
    if (!document.getAnimations) return;
    var all = document.getAnimations();
    for (var i = 0; i < all.length; i++) if (all[i].playbackRate !== k) all[i].playbackRate = k;
  }
  perf.now = warpedNow;
  window.requestAnimationFrame = function (cb) {
    return realRaf(function () {
      later(function () { cb(warpedNow()); });
    });
  };
  ['setTimeout', 'setInterval'].forEach(function (name) {
    var real = window[name].bind(window);
    window[name] = function (fn, ms) {
      var rest = Array.prototype.slice.call(arguments, 2);
      return real(function () {
        later(function () { fn.apply(null, rest); });
      }, (ms || 0) / warp.k);
    };
  });
  var REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var data = null;
  try {
    data = JSON.parse(document.getElementById('cmp').getAttribute('data-lw'));
  } catch (err) {
    return;
  }
  var root = document.documentElement;
  var body = document.body;
  var cmp = document.getElementById('cmp');
  var cbody = document.getElementById('cmpBody');
  var run = document.getElementById('cmpRun');
  var stage = document.getElementById('cmpStage');
  var go = document.getElementById('cmpGo');
  var slot = document.querySelector('button.cmpslot[data-kind="sources"]');
  var head = document.getElementById('cmpLoomHead');
  var clock = document.getElementById('cmpClock');
  var status = document.getElementById('lwStatus');
  var pieces = document.querySelectorAll('.cmp-assembly-piece');
  var threads = stage ? stage.querySelectorAll('path.lthread') : [];
  var marks = stage ? stage.querySelectorAll('.lmark') : [];
  var spools = stage ? stage.querySelectorAll('.lspool') : [];
  if (!cmp || !cbody || !run || !stage || !go || !slot) return;
  var at = {};
  var total = 0;
  for (var b = 0; b < BEATS.length; b++) {
    at[BEATS[b][0]] = total;
    total += BEATS[b][1];
  }
  function mmss(s) {
    s = Math.max(0, Math.round(s));
    var m = Math.floor(s / 60);
    var r = s % 60;
    return (m < 10 ? '0' : '') + m + String.fromCharCode(58) + (r < 10 ? '0' : '') + r;
  }
  function settledStatus() {
    if (status) status.textContent = mmss(data.seconds) + ' · published · ' + data.cards + '/' + data.cards;
  }
  function state(s) {
    cmp.setAttribute('data-state', s);
    body.setAttribute('data-choreo-state', s === 'choose' ? 'idle' : s);
    cbody.hidden = s !== 'choose';
    run.hidden = !(s === 'running' || s === 'settled');
    if (s === 'choose') body.classList.remove('done');
    if (s === 'settled') body.classList.add('done');
  }
  function show(el, on) {
    if (on) el.classList.add('is-in');
    else el.classList.remove('is-in');
  }
  function announce() {
    try {
      if (window.parent && window.parent !== window) window.parent.postMessage({ lensmithWindow: 'ready' }, window.location.origin);
    } catch (err) {
      return;
    }
  }
  function tell(what) {
    try {
      if (HOSTED) window.parent.postMessage({ lensmithWindow: what }, window.location.origin);
    } catch (err) {
      return;
    }
  }
  var REPLAY = window.location.hash === '#replay';
  function settle() {
    if (picker) picker.finish();
    if (warp.k !== 1) speed(1);
    state('settled');
    root.classList.add('lw-settled');
    stage.classList.remove('entry-loom-withheld', 'entry-frame-only');
    stage.classList.add('entry-loom-revealed');
    if (head) head.textContent = 'composition - woven';
    for (var i = 0; i < pieces.length; i++) show(pieces[i], true);
    for (var j = 0; j < threads.length; j++) {
      threads[j].style.strokeDashoffset = '';
      threads[j].style.opacity = '';
    }
    for (var k = 0; k < marks.length; k++) marks[k].style.opacity = '';
    for (var q = 0; q < spools.length; q++) spools[q].style.opacity = '';
    settledStatus();
    body.setAttribute('data-replay', 'done');
    tell('done');
  }
  root.classList.add('lw-js');
  var sheet = document.getElementById('sheet');
  var scrim = document.getElementById('lwScrim');
  var shBody = document.getElementById('shBody');
  var shClose = document.getElementById('sheetClose');
  var opener = null;
  var col = document.querySelector('.col');
  function focusables() {
    return Array.prototype.slice.call(sheet.querySelectorAll('button, a[href]'));
  }
  function openDetail(btn) {
    var src = document.getElementById(btn.getAttribute('data-detail'));
    if (!src || !sheet || body.getAttribute('data-replay') === 'playing') return;
    opener = btn;
    shBody.textContent = '';
    for (var n = src.firstChild; n; n = n.nextSibling) shBody.appendChild(n.cloneNode(true));
    var h = shBody.querySelector('h3');
    if (h) h.id = 'shTitle';
    scrim.hidden = false;
    sheet.hidden = false;
    if (col) col.setAttribute('aria-hidden', 'true');
    if (col && 'inert' in col) col.inert = true;
    root.classList.add('lw-detail-open');
    sheet.scrollTop = 0;
    void sheet.offsetHeight;
    scrim.classList.add('on');
    sheet.classList.add('on');
    shClose.focus();
  }
  function closeDetail() {
    if (!sheet || sheet.hidden) return;
    scrim.classList.remove('on');
    sheet.classList.remove('on');
    if (col) col.removeAttribute('aria-hidden');
    if (col && 'inert' in col) col.inert = false;
    root.classList.remove('lw-detail-open');
    var done = function () {
      if (sheet.classList.contains('on')) return;
      sheet.hidden = true;
      scrim.hidden = true;
    };
    if (REDUCED) done();
    else realTimeout(done, 400);
    if (opener) opener.focus();
    opener = null;
  }
  if (sheet && scrim && shBody && shClose) {
    document.addEventListener('click', function (ev) {
      var btn = ev.target.closest ? ev.target.closest('button.lw-open') : null;
      if (btn) openDetail(btn);
    });
    shClose.addEventListener('click', closeDetail);
    scrim.addEventListener('click', closeDetail);
    document.addEventListener('keydown', function (ev) {
      if (sheet.hidden) return;
      if (ev.key === 'Escape' || ev.key === 'Esc') {
        ev.preventDefault();
        closeDetail();
      } else if (ev.key === 'Tab') {
        var f = focusables();
        if (!f.length) return;
        var first = f[0];
        var last = f[f.length - 1];
        if (ev.shiftKey && (document.activeElement === first || document.activeElement === sheet)) {
          ev.preventDefault();
          last.focus();
        } else if (!ev.shiftKey && document.activeElement === last) {
          ev.preventDefault();
          first.focus();
        }
      }
    });
    var startY = null;
    sheet.addEventListener('touchstart', function (ev) { startY = sheet.scrollTop <= 0 ? ev.touches[0].clientY : null; }, { passive: true });
    sheet.addEventListener('touchend', function (ev) {
      if (startY !== null && ev.changedTouches[0].clientY - startY > 80) closeDetail();
      startY = null;
    });
  }
  if (HOSTED && !REPLAY) {
    body.setAttribute('data-replay', 'done');
    announce();
    tell('done');
    return;
  }
  if (REDUCED) {
    if (REPLAY || HOSTED) {
      root.classList.remove('lw-settled');
      stage.classList.remove('entry-loom-revealed');
      body.classList.remove('done');
      for (var rp = 0; rp < pieces.length; rp++) show(pieces[rp], false);
      if (status) status.textContent = 'standing by';
      state('choose');
      slot.textContent = data.chosen;
      slot.setAttribute('aria-label', 'sources: ' + data.chosen);
      announce();
      var later = false;
      var finish = function (wait) { if (!later) { later = true; if (wait) realTimeout(settle, wait); else settle(); } };
      if (REPLAY) finish(3000);
      else window.addEventListener('message', function (ev) {
        if (ev.origin !== window.location.origin || ev.source !== window.parent || !ev.data) return;
        if (ev.data.lensmithHost === 'play') finish(3000);
        else if (ev.data.lensmithHost === 'still') finish(0);
      });
      return;
    }
    settle();
    return announce();
  }
  var lines = data.steps;
  var entry = null;
  var driver = window.__composerEntryTransition;
  var t0 = 0;
  var raf = 0;
  var hiddenAt = 0;
  var playing = false;
  var played = false;
  var done = {};
  var beat = '';
  var picker = null;
  function once(name, fn) {
    if (done[name]) return;
    done[name] = true;
    fn();
  }
  function clamp(x) {
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }
  function ease(x) {
    x = clamp(x);
    return x < 0.5 ? 2 * x * x : 1 - (2 - 2 * x) * (2 - 2 * x) / 2;
  }
  var lens = [];
  function measure() {
    lens = [];
    for (var i = 0; i < threads.length; i++) {
      var len = 1;
      try {
        len = threads[i].getTotalLength() || 1;
      } catch (err) {
        len = 1;
      }
      lens.push(len);
      threads[i].style.strokeDasharray = threads[i].getAttribute('data-dash') ? '' : String(len);
    }
  }
  function weave(t) {
    for (var q = 0; q < spools.length; q++) spools[q].style.opacity = String(clamp(t / 500));
    for (var i = 0; i < threads.length; i++) {
      var k = ease((t - 50 - i * 50) / 550);
      var th = threads[i];
      if (th.getAttribute('data-dash')) th.style.opacity = String(k);
      else th.style.strokeDashoffset = String(lens[i] * (1 - k));
    }
    for (var m = 0; m < marks.length; m++) marks[m].style.opacity = String(clamp((t - 850 - m * 30) / 200));
  }
  function frame(now) {
    raf = 0;
    if (!playing) return;
    var t = now - t0;
    var name = BEATS[0][0];
    for (var i = 0; i < BEATS.length; i++) if (t >= at[BEATS[i][0]]) name = BEATS[i][0];
    if (name !== beat) {
      beat = name;
      body.setAttribute('data-beat', name);
    }
    if (clock) clock.textContent = mmss((t - at.sand) / (total - at.sand) * data.seconds);
    if (picker) picker.step(t);
    if (t >= at.sand) once('compose', function () {
      go.classList.remove('lw-press');
      if (driver) {
        entry = driver.begin({ sources: data.sources });
        driver.mount(entry);
      }
      state('running');
      stage.classList.add('entry-loom-withheld');
      if (head) head.textContent = 'composition - sources';
    });
    for (var s = 0; s < lines.length; s++) {
      var when = at.sand + 100 + s * 120;
      if (t >= when) once('line' + s, (function (line) {
        return function () {
          if (driver && entry) {
            if (line.type === 'run.started') driver.bind(entry, 'recorded');
            driver.accept(entry, { type: line.type, raw: line.text });
          }
        };
      }(lines[s])));
    }
    if (t >= at.sand + 100 + lines.length * 120 && entry && entry.words) once('complete', function () {
      driver.complete(entry);
    });
    if (entry && (entry.phase === 'rise' || entry.phase === 'hold')) once('held', function () { speed(HOLD_SPEED); });
    if (entry && entry.words) once('quicken', function () { speed(WORDS_SPEED); });
    if (warp.k !== 1) rates(warp.k);
    if (t >= at.weave) once('reveal', function () {
      speed(1);
      stage.classList.remove('entry-loom-withheld', 'entry-frame-only');
      stage.classList.add('entry-loom-revealed');
      if (head) head.textContent = 'composition - weaving';
      measure();
    });
    if (t >= at.weave) {
      stage.classList.remove('entry-loom-withheld', 'entry-frame-only');
      weave(t - at.weave);
    }
    if (t >= at.brief) once('brief', function () {
      if (head) head.textContent = 'composition - woven';
      state('settled');
      settledStatus();
    });
    if (t >= at.brief) {
      for (var p = 0; p < pieces.length; p++) if (t >= at.brief + 100 + p * 90) show(pieces[p], true);
    }
    if (t >= total) {
      playing = false;
      settle();
      return;
    }
    raf = realRaf(frame);
  }
  function start() {
    if (playing || played) return;
    playing = true;
    played = true;
    body.setAttribute('data-replay', 'playing');
    for (var i = 0; i < threads.length; i++) {
      threads[i].style.opacity = threads[i].getAttribute('data-dash') ? '0' : '';
    }
    measure();
    for (var j = 0; j < threads.length; j++) if (!threads[j].getAttribute('data-dash')) threads[j].style.strokeDashoffset = String(lens[j]);
    for (var k = 0; k < marks.length; k++) marks[k].style.opacity = '0';
    for (var q = 0; q < spools.length; q++) spools[q].style.opacity = '0';
    picker = COMPOSE_STEP.create({ slot: slot, go: go, chosen: data.chosen, sources: data.sources, rows: data.rows });
    t0 = realNow();
    raf = realRaf(frame);
  }
  root.classList.remove('lw-settled');
  stage.classList.remove('entry-loom-revealed');
  body.classList.remove('done');
  body.removeAttribute('data-replay');
  for (var p = 0; p < pieces.length; p++) show(pieces[p], false);
  if (status) status.textContent = 'standing by';
  state('choose');
  go.addEventListener('click', start);
  announce();
  if (REPLAY) start();
  function hold(on) {
    if (on === held) return;
    if (on) {
      heldAt = realNow();
      held = true;
      rates(0);
      if (raf) realCancelRaf(raf);
      raf = 0;
      return;
    }
    var gap = realNow() - heldAt;
    warp.real0 += gap;
    t0 += gap;
    held = false;
    rates(warp.k);
    var calls = waiting;
    waiting = [];
    for (var c = 0; c < calls.length; c++) calls[c]();
    if (playing && !raf) raf = realRaf(frame);
  }
  document.addEventListener('visibilitychange', function () {
    if (!playing) return;
    if (document.hidden) {
      hiddenAt = realNow();
      if (raf) realCancelRaf(raf);
      raf = 0;
    } else {
      if (hiddenAt) t0 += realNow() - hiddenAt;
      hiddenAt = 0;
      if (!raf && !held) raf = realRaf(frame);
    }
  });
  window.addEventListener('message', function (ev) {
    if (!HOSTED || ev.origin !== window.location.origin || ev.source !== window.parent || !ev.data) return;
    var what = ev.data.lensmithHost;
    if (what === 'play') {
      hold(false);
      start();
    } else if (what === 'pause') {
      hold(true);
    } else if (what === 'still' && body.getAttribute('data-replay') !== 'done') {
      hold(false);
      playing = false;
      if (raf) realCancelRaf(raf);
      raf = 0;
      var fin = null;
      if (entry) {
        dropped = true;
        var sand = document.querySelectorAll('canvas');
        for (var c = 0; c < sand.length; c++) sand[c].parentNode.removeChild(sand[c]);
      }
      if (driver && driver.abort) {
        fin = entry || driver.begin({ sources: data.sources });
        driver.abort(fin);
      }
      settle();
      if (driver && driver.finish && fin) driver.finish(fin);   // the ring and the status line a replay that ran out leaves
    }
  });
  function watch() {
    if (HOSTED) return;
    if (!window.IntersectionObserver) return start();
    var seen = new window.IntersectionObserver(function (entries) {
      if (!entries[entries.length - 1].isIntersecting) return;
      seen.disconnect();
      start();
    }, { threshold: 0.6 });
    seen.observe(document.getElementById('lwView') || cmp);
  }
  function arm() {
    realRaf(function () {
      realRaf(function () {
        realTimeout(watch, 300);
      });
    });
  }
  if (REPLAY) return;
  var loaded = document.readyState === 'complete';
  var painted = false;
  var armed = false;
  function ready() {
    if (loaded && painted && !armed) {
      armed = true;
      arm();
    }
  }
  try {
    var paints = new window.PerformanceObserver(function (list) {
      var es = list.getEntries();
      for (var e = 0; e < es.length; e++) {
        if (es[e].name === 'first-contentful-paint') {
          paints.disconnect();
          painted = true;
          ready();
        }
      }
    });
    paints.observe({ type: 'paint', buffered: true });
  } catch (err) {
    painted = true;
  }
  function onLoad() {
    loaded = true;
    realTimeout(function () {
      painted = true;
      ready();
    }, 1000);
    ready();
  }
  if (loaded) onLoad();
  else window.addEventListener('load', onLoad);
})();
