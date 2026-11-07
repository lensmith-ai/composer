/* claimseal.js: the checked claims of a brief, shown as underlined sentences.
 *
 * Every insight is a claim the checker (claim-seal) traced to the article it cites. This file draws that on the
 * insight cards: a claim is an underlined sentence (the underline's style, not only its colour, says how far the
 * article backs it); pressing it, by tap, click, Enter or Space, opens a popover with the verdict in plain words,
 * the cited article and its link, and the passage the check located (a few words, at most 25, kept in the job's own
 * passages.json and never in the shared edition). Esc, a tap outside or the Close button shuts it; focus goes back
 * to the sentence.
 *
 * API (window.__claimSeal):
 *   card(el, section)    rewrite the card's headline and first line of text into claim sentences
 *   mark(el, text, claim) fill el with text, the located sentences as claim sentences
 *   legend(host, sections, meta)  put the one-line "what the underline means" strip before host
 *   open(trigger, claim) / close()
 * Every string from a brief or a feed goes in through textContent, never as HTML.
 */
(function () {
  'use strict';
  var WORD = { supported: 'Supported', partial: 'Partly supported', unsupported: 'Not supported', unchecked: 'Not checked' };
  var PLAIN = {
    supported: 'The cited article backs this up.',
    partial: 'The cited article backs part of this, or implies it without saying it outright.',
    unsupported: 'Nothing in the cited article backs this up. Read the source before you rely on it.',
    unchecked: 'The checker could not read this source, so this claim was not checked.'
  };
  var RELATION = {
    says: 'The source says this directly.',
    contradicts: 'The source disagrees with this.',
    undetermined: 'The checker could not rate this sentence on its own.'
  };
  var STEP = 'The source does not say this outright; the sentence takes a step beyond it ({v}).';
  var KEY = { 'partly_supported': 'partial', 'partially_supported': 'partial', unresolved: 'unchecked' };
  var pop = null, current = null, meta = null, listening = false;

  function state(v) {
    v = KEY[v] || v;
    return WORD[v] ? v : 'unchecked';
  }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function safeHref(u) { return typeof u === 'string' && /^https?:\/\//i.test(u) ? u : ''; }
  function host(u) { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return ''; } }

  // The claim a card or a located sentence stands for: its text, its verdict and the citations it rests on.
  function claimFor(section, text, only) {
    var v = section.verification || {};
    var cites = (v.citations || []).filter(function (c) { return c && typeof c === 'object'; });
    if (only) cites = cites.filter(function (c, i) { return only.indexOf(c) !== -1; });
    return { text: text, state: state(v.verdict), cites: cites, sources: section.sources || [] };
  }

  function relationLine(rel) {
    if (!rel) return '';
    if (RELATION[rel]) return RELATION[rel];
    return STEP.replace('{v}', rel);
  }

  function trigger(span, claim, label) {
    span.className = 'cs-claim cs-' + claim.state;
    span.setAttribute('role', 'button');
    span.setAttribute('tabindex', '0');
    span.setAttribute('aria-haspopup', 'dialog');
    span.setAttribute('aria-expanded', 'false');
    span.setAttribute('aria-label', label + ' Checked: ' + WORD[claim.state].toLowerCase() + '. Press to see the passage it rests on.');
    span.__claim = claim;
    return span;
  }

  // Wrap each located sentence (the checker's offsets into `text`) as a claim sentence; the rest stays plain.
  function mark(node, text, claim, spans) {
    node.textContent = '';
    var at = 0;
    (spans || []).forEach(function (sp) {
      if (!sp || sp.start < at || sp.end <= sp.start || sp.end > text.length) return;
      if (sp.start > at) node.appendChild(document.createTextNode(text.slice(at, sp.start)));
      var s = trigger(el('span', '', text.slice(sp.start, sp.end)), claim.sentence ? claim.sentence(sp) : claim, text.slice(sp.start, sp.end));
      node.appendChild(s);
      at = sp.end;
    });
    if (at < text.length) node.appendChild(document.createTextNode(text.slice(at)));
  }

  function card(ic, s) {
    if (!ic || !s) return;
    var head = ic.querySelector('h4');
    var title = s.title || '';
    if (head && title) {
      head.textContent = '';
      var whole = trigger(el('span', '', title), claimFor(s, title), title);
      head.appendChild(whole);
    }
    var body = ic.querySelector('.gv.keep');
    // the line the card shows: the one the checker marked a sentence in, else the first detail (as before)
    var firstMarked = (s.claimSpans || []).filter(function (x) { return s.kp && s.kp[x.kp] != null; })[0];
    var kpIndex = firstMarked ? firstMarked.kp : (s.kp && s.kp[1] ? 1 : 0);
    var line = (s.kp && s.kp[kpIndex]) || '';
    if (body && firstMarked) body.textContent = line;
    var located = (s.claimSpans || []).filter(function (x) { return x.kp === kpIndex && x.end <= line.length; });
    if (body && located.length) {
      // one sentence cited by several sources is one claim that lists every source it rests on
      var groups = [];
      located.forEach(function (x) {
        var g = groups.filter(function (y) { return y.start === x.start && y.end === x.end; })[0];
        if (!g) { g = { start: x.start, end: x.end, cites: [], relation: x.sentenceRelation || null }; groups.push(g); }
        var c = ((s.verification || {}).citations || [])[x.citation];
        if (c && g.cites.indexOf(c) === -1) g.cites.push(c);
      });
      mark(body, line, { sentence: function (g) {
        var one = claimFor(s, line.slice(g.start, g.end), g.cites);
        one.relation = g.relation;
        return one;
      } }, groups);
    }
    // the info dot is a real button: the card is no longer one big button, so its claims can be pressed
    var dot = ic.querySelector('.infodot');
    if (dot) {
      var b = el('button', 'infodot', 'i');
      b.type = 'button';
      b.setAttribute('aria-haspopup', 'dialog');
      b.setAttribute('aria-label', 'Open the full claim and its sources: ' + title);
      dot.parentNode.replaceChild(b, dot);
    }
    ic.removeAttribute('role');
    ic.removeAttribute('tabindex');
    ic.removeAttribute('aria-haspopup');
    ic.classList.add('cs-card');
  }

  function ensurePop() {
    if (pop) return pop;
    pop = el('div', 'cs-pop');
    pop.id = 'csPop';
    pop.setAttribute('role', 'dialog');
    pop.setAttribute('aria-label', 'What this claim rests on');
    pop.setAttribute('tabindex', '-1');
    pop.hidden = true;
    document.body.appendChild(pop);
    return pop;
  }

  function fill(claim) {
    pop.textContent = '';
    var top = el('div', 'cs-top');
    top.appendChild(el('span', 'cs-chip cs-' + claim.state, WORD[claim.state]));
    var x = el('button', 'cs-x', 'Close');
    x.type = 'button';
    x.addEventListener('click', function () { close(true); });
    top.appendChild(x);
    pop.appendChild(top);
    pop.appendChild(el('p', 'cs-text', claim.text));
    pop.appendChild(el('p', 'cs-plain', PLAIN[claim.state]));
    if (claim.relation) pop.appendChild(el('p', 'cs-rel', relationLine(claim.relation)));
    var seen = 0;
    claim.cites.forEach(function (c) {
      seen += 1;
      var row = el('div', 'cs-src');
      var src = (claim.sources.filter(function (s) { return s && s.ref === c.ref; })[0]) || {};
      row.appendChild(el('div', 'cs-lab', (src.label || c.source || 'Source') + (c.resolution === 'unresolved' ? ' · not found in what was read' : '')));
      var url = safeHref(c.url || src.url);
      if (url) {
        var a = el('a', 'cs-link', (c.ref || 'Open the article') + ' ↗');
        a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer';
        row.appendChild(a);
        row.appendChild(el('div', 'cs-host', host(url)));
      } else {
        row.appendChild(el('div', 'cs-title', c.ref || 'Untitled article'));
      }
      if (c.passage && c.passage.text) {
        var q = el('blockquote', 'cs-pass');
        q.appendChild(el('p', '', '“' + c.passage.text + '”'));
        q.appendChild(el('footer', '', 'The passage the check located in this article' + (c.passage.cut ? ' (the first 25 words)' : '')));
        row.appendChild(q);
      } else if (c.window_sha256) {
        row.appendChild(el('p', 'cs-none', 'This recorded brief keeps the passage’s fingerprint (' + c.window_sha256.slice(0, 10) + '…), not the article’s words.'));
      } else if (state(claim.state) === 'unchecked') {
        row.appendChild(el('p', 'cs-none', 'No passage: this claim was not checked against the article.'));
      } else {
        row.appendChild(el('p', 'cs-none', 'No passage was kept for this check. The article is linked above.'));
      }
      pop.appendChild(row);
    });
    if (!seen) pop.appendChild(el('p', 'cs-none', 'This claim cites no article the checker could read.'));
    var foot = el('p', 'cs-foot');
    foot.textContent = 'Checked by claim-seal: each claim is traced to the passage it rests on, and the check is sealed' +
      (meta && meta.seal ? ' (seal ' + String(meta.seal).slice(0, 8) + '…' + (meta.verified ? ', verified' : '') + ').' : '.');
    pop.appendChild(foot);
  }

  function place(t) {
    var r = t.getBoundingClientRect(), w = window.innerWidth, h = window.innerHeight;
    if (w < 768) { pop.style.left = pop.style.top = pop.style.maxHeight = pop.style.width = ''; pop.classList.add('cs-sheet'); return; }
    pop.classList.remove('cs-sheet');
    var pw = Math.min(420, w - 24);
    pop.style.width = pw + 'px';
    var left = Math.max(12, Math.min(r.left, w - pw - 12));
    var below = h - r.bottom, above = r.top;
    var ph = pop.offsetHeight;
    var top = (below >= ph + 12 || below >= above) ? r.bottom + 8 : Math.max(12, r.top - ph - 8);
    pop.style.left = left + 'px';
    pop.style.top = top + 'px';
    pop.style.maxHeight = Math.max(160, h - top - 12) + 'px';
  }

  function open(t, claim) {
    ensurePop();
    if (current && current !== t) current.setAttribute('aria-expanded', 'false');
    current = t;
    fill(claim);
    pop.hidden = false;
    t.setAttribute('aria-expanded', 'true');
    place(t);
    pop.focus({ preventScroll: true });
    if (!listening) {
      listening = true;
      document.addEventListener('keydown', onKey, true);
      document.addEventListener('pointerdown', onOutside, true);
      window.addEventListener('resize', onMove, { passive: true });
      window.addEventListener('scroll', onMove, { passive: true, capture: true });
    }
  }
  function close(refocus) {
    if (!pop || pop.hidden) return;
    pop.hidden = true;
    var t = current;
    current = null;
    if (t) { t.setAttribute('aria-expanded', 'false'); if (refocus && document.contains(t)) t.focus({ preventScroll: true }); }
    if (listening) {
      listening = false;
      document.removeEventListener('keydown', onKey, true);
      document.removeEventListener('pointerdown', onOutside, true);
      window.removeEventListener('resize', onMove);
      window.removeEventListener('scroll', onMove, true);
    }
  }
  function onKey(e) {
    if (e.key === 'Escape') { e.stopPropagation(); close(true); }
  }
  function onOutside(e) {
    if (!pop || pop.hidden || pop.contains(e.target)) return;
    if (current && current.contains(e.target)) return;
    close(false);
  }
  function onMove() {
    if (!current || !pop || pop.hidden) return;
    if (!document.contains(current)) { close(false); return; }  // its card was drawn again: nothing to point at
    place(current);
  }

  // one delegated listener for every claim sentence on the page, cards and the legend alike
  document.addEventListener('click', function (e) {
    var t = e.target && e.target.closest ? e.target.closest('.cs-claim') : null;
    if (!t || !t.__claim) return;
    e.preventDefault();
    e.stopPropagation();
    if (current === t && pop && !pop.hidden) close(true); else open(t, t.__claim);
  }, true);
  document.addEventListener('keydown', function (e) {
    var t = e.target && e.target.classList && e.target.classList.contains('cs-claim') ? e.target : null;
    if (!t || (e.key !== 'Enter' && e.key !== ' ')) return;
    e.preventDefault();
    if (current === t && pop && !pop.hidden) close(true); else open(t, t.__claim);
  });

  // the strip that says what the underline means; legendNode makes it, legend puts it before a host
  function legendNode(sections, m) {
    meta = m || meta;
    var tally = { supported: 0, partial: 0, unsupported: 0, unchecked: 0 };
    (sections || []).forEach(function (s) { tally[state((s.verification || {}).verdict)] += 1; });
    var box = el('section', 'cs-legend');
    box.id = 'csLegend';
    box.setAttribute('aria-label', 'How claims were checked');
    var h = el('div', 'cs-lh');
    h.appendChild(el('span', 'cs-lk', 'claim-seal'));
    var parts = [];
    ['supported', 'partial', 'unsupported', 'unchecked'].forEach(function (k) {
      if (tally[k]) parts.push(tally[k] + ' ' + WORD[k].toLowerCase());
    });
    h.appendChild(el('span', 'cs-lt', (sections || []).length + ' claims checked' + (parts.length ? ': ' + parts.join(', ') : '')));
    box.appendChild(h);
    var p = el('p', 'cs-ld');
    p.appendChild(document.createTextNode('Every underlined sentence is a claim traced to the article it cites. '));
    var sample = el('span', 'cs-key');
    [['supported', 'solid: supported'], ['partial', 'dashed: partly'], ['unsupported', 'wavy: not supported']].forEach(function (k) {
      sample.appendChild(el('span', 'cs-k cs-' + k[0], k[1]));
    });
    p.appendChild(sample);
    p.appendChild(document.createTextNode(' Press one to see the source passage, the link and the verdict.'));
    box.appendChild(p);
    return box;
  }
  function legend(hostEl, sections, m) {
    if (!hostEl || !hostEl.parentNode) return;
    var old = document.getElementById('csLegend');
    if (old) old.remove();
    hostEl.parentNode.insertBefore(legendNode(sections, m), hostEl);
  }

  window.__claimSeal = { card: card, mark: mark, legend: legend, legendNode: legendNode, open: open, close: close, state: state };
})();
