/* Lensmith Composer page: plays a brief's steps, then shows the brief.
   It reads the brief from the JSON block in this page (id "edition"); it fetches nothing,
   except in live mode (served by `composer serve`), where the form posts to /api/compose.
   Every piece of text is set with textContent, never as HTML. */
(function () {
  'use strict';
  var STATE = { supported: 'supported', partial: 'partly supported', unsupported: 'not supported', unchecked: 'not checked' };
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var timers = [];

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }
  function json(id) {
    var node = document.getElementById(id);
    return node ? JSON.parse(node.textContent) : null;
  }
  function plural(n, word) { return n + ' ' + word + (n === 1 ? '' : 's'); }
  function labels(ed) { return ed.sources.map(function (s) { return s.label; }); }

  function steps(ed) {
    var n = ed.cards.length, tally = {};
    ed.cards.forEach(function (c) { tally[c.state] = (tally[c.state] || 0) + 1; });
    var out = [['composition - sources', 'compose started · ' + plural(ed.sources.length, 'source') + ' · lens: ' + ed.lens]];
    ed.sources.forEach(function (s) {
      out.push(['', 'reading ' + s.label + ' · ' + plural(s.items, 'item') + (s.status === 'ok' ? ' (ok)' : ' (failed)')]);
    });
    out.push(['composition - screening', 'source text screened, prompt assembled']);
    out.push(['composition - lens', 'writing through the lens']);
    out.push(['', 'brief written · ' + plural(n, 'insight')]);
    out.push(['composition - checking', 'checking each claim against the articles it cites']);
    out.push(['', 'checked · ' + Object.keys(tally).map(function (k) { return tally[k] + ' ' + STATE[k]; }).join(' · ')]);
    return out;
  }

  /* Split `text` (counted in code points, as claim-seal counts) into plain runs and marked spans. */
  function marked(text, spans) {
    var chars = Array.from(text || ''), frag = document.createDocumentFragment(), at = 0;
    spans.slice().sort(function (a, b) { return a.start - b.start; }).forEach(function (s) {
      if (s.start < at || s.end > chars.length || s.start >= s.end) return;
      if (s.start > at) frag.appendChild(document.createTextNode(chars.slice(at, s.start).join('')));
      var m = el('mark', '', chars.slice(s.start, s.end).join(''));
      frag.appendChild(m);
      frag.appendChild(el('sup', '', s.n));
      at = s.end;
    });
    if (at < chars.length) frag.appendChild(document.createTextNode(chars.slice(at).join('')));
    return frag;
  }

  function card(c, i) {
    var box = el('article', 'card');
    var spans = {};
    c.citations.forEach(function (x, k) {
      if (x.field) (spans[x.field] = spans[x.field] || []).push({ start: x.start, end: x.end, n: k + 1 });
    });
    var head = el('div');
    head.appendChild(el('span', 'chip s-' + c.state, STATE[c.state] || c.state));
    head.appendChild(document.createTextNode(' '));
    head.appendChild(el('span', 'meta', (i === 0 ? 'The insight' : 'Insight ' + (i + 1)) + ' · ' + plural(c.citations.length, 'source')));
    box.appendChild(head);
    var h = el('h2');
    h.appendChild(marked(c.insight, spans.insight || []));
    box.appendChild(h);
    var why = el('p', 'why');
    why.appendChild(marked(c.why, spans.why || []));
    box.appendChild(why);
    if (c.details && c.details.length) {
      var ul = el('ul');
      c.details.forEach(function (d, k) {
        var li = el('li');
        li.appendChild(marked(d, spans['details[' + k + ']'] || []));
        ul.appendChild(li);
      });
      box.appendChild(ul);
    }
    var cites = el('div', 'cites');
    cites.appendChild(el('div', '', 'Sources and seals'));
    var ol = el('ol');
    c.citations.forEach(function (x) {
      var li = el('li');
      li.appendChild(el('span', '', x.label + (x.relation && x.relation !== 'undetermined' ? ' ' + x.relation + ' this' : '') + ': '));
      if (x.url && /^https?:\/\//i.test(x.url)) {
        var a = el('a', '', x.title || x.url);
        a.href = x.url;
        a.rel = 'noreferrer noopener';
        li.appendChild(a);
      } else {
        li.appendChild(el('span', '', x.title));
      }
      if (x.window_sha256) li.appendChild(el('div', 'fp', 'passage fingerprint ' + x.window_sha256.slice(0, 12)));
      ol.appendChild(li);
    });
    cites.appendChild(ol);
    box.appendChild(cites);
    return box;
  }

  function render(ed) {
    var root = document.getElementById('edition');
    root.textContent = '';
    if (!ed.cards.length) return;
    root.appendChild(el('h1', '', ed.cards[0].insight));
    root.appendChild(el('p', 'meta', plural(ed.cards.length, 'insight') + ' from ' + labels(ed).join(', ')
      + ' through the lens “' + ed.lens + '” · ' + ed.composed_on));
    if (ed.connection) {
      var cn = el('p', 'conn', 'Connection (' + (ed.connection.confidence || '?') + ', ' + (STATE[ed.connection.state] || 'not checked')
        + '): ' + ed.connection.headline);
      root.appendChild(cn);
    }
    if (ed.honest_note) root.appendChild(el('p', 'conn', 'Note from the writer: ' + ed.honest_note));
    ed.cards.forEach(function (c, i) { root.appendChild(card(c, i)); });
    var foot = el('div', 'foot');
    var chk = ed.check || {};
    foot.appendChild(el('p', '', chk.note || ('Checked with ' + (chk.tool || 'claim-seal') + ': ' + plural(chk.rows || 0, 'sealed row')
      + (chk.seal_verified ? ', seal verified' : ''))));
    var m = ed.model || {};
    var cost = plural(m.calls || 0, 'model call');
    if (typeof m.input_tokens === 'number') cost += ' · ' + m.input_tokens.toLocaleString('en') + ' input and '
      + m.output_tokens.toLocaleString('en') + ' output tokens';
    foot.appendChild(el('p', '', cost + (m.provider ? ' · ' + m.provider : '')));
    root.appendChild(foot);
  }

  function play(ed) {
    timers.forEach(clearTimeout);
    timers = [];
    var log = document.getElementById('log'), root = document.getElementById('edition');
    log.textContent = '';
    root.classList.remove('on');
    document.getElementById('sentence-sources').textContent = labels(ed).join(' and ');
    document.getElementById('sentence-lens').textContent = ed.lens;
    render(ed);
    var lines = steps(ed), beat = reduced ? 0 : 650;
    lines.forEach(function (pair, k) {
      var add = function () {
        if (pair[0]) log.appendChild(el('div', 'head on', pair[0]));
        var d = el('div', '', pair[1]);
        log.appendChild(d);
        if (beat) requestAnimationFrame(function () { d.classList.add('on'); }); else d.classList.add('on');
      };
      if (beat) timers.push(setTimeout(add, k * beat)); else add();
    });
    var show = function () { root.classList.add('on'); };
    if (beat) timers.push(setTimeout(show, lines.length * beat + 200)); else show();
  }

  function live(cfg) {
    var form = document.getElementById('compose');
    var box = document.getElementById('picks');
    cfg.sources.forEach(function (s, k) {
      if (!s.available || s.hidden) return;
      var lab = el('label');
      var cb = el('input');
      cb.type = 'checkbox';
      cb.name = 'source';
      cb.value = s.id;
      cb.checked = k < 2;
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode(' ' + s.label));
      box.appendChild(lab);
    });
    form.classList.add('on');
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var err = document.getElementById('err');
      err.textContent = '';
      var ids = Array.from(form.querySelectorAll('input[name=source]:checked')).map(function (x) { return x.value; });
      var body = { sources: ids, lens: form.elements.lens.value };
      var btn = form.querySelector('button');
      btn.disabled = true;
      document.getElementById('log').textContent = 'composing (this takes a minute or two)...';
      var headers = { 'content-type': 'application/json', 'x-composer-csrf': 'same-origin' };
      if (form.elements.pass && form.elements.pass.value) headers['x-composer-pass'] = form.elements.pass.value;
      fetch('/api/compose', { method: 'POST', headers: headers, body: JSON.stringify(body) })
        .then(function (r) { return r.json().then(function (j) { return [r.ok, j]; }); })
        .then(function (res) {
          btn.disabled = false;
          if (!res[0]) { err.textContent = res[1].error || 'the brief could not be composed'; document.getElementById('log').textContent = ''; return; }
          play(res[1]);
        })
        .catch(function () { btn.disabled = false; err.textContent = 'the server did not answer'; });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var ed = json('edition-data'), cfg = json('page-config') || {};
    document.getElementById('replay').addEventListener('click', function () { play(ed); });
    if (cfg.live) live(cfg);
    play(ed);
  });
})();
