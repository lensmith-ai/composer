/* claimseal.js: the checked claims of a brief, marked on the insight cards.
 *
 * Every insight is a claim the checker (claim-seal) traced to the article it cites. This file marks that on the
 * insight cards with the published window's own claim mark (the `cmark` class: one thin amber underline, the same for
 * every checked claim). Pressing a mark, by tap, click, Enter or Space, opens the app's existing sheet (#spanSheet,
 * the one the phrase marks in a brief open) with the claim, the verdict in plain words, the cited article and its
 * link, and the passage the check located (a few words, at most 25, kept in the job's own passages.json and never in
 * the shared edition). Esc, the Close button, the handle or a tap outside shuts it; focus goes back to the mark.
 * The mark itself never says the verdict: only the sheet does.
 *
 * API (window.__claimSeal):
 *   card(el, section)    rewrite the card's headline and first line of text into claim marks
 *   mark(el, text, claim) fill el with text, the located sentences as claim marks
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
    span.className = 'cmark';
    span.setAttribute('role', 'button');
    span.setAttribute('tabindex', '0');
    span.setAttribute('aria-haspopup', 'dialog');
    span.setAttribute('aria-expanded', 'false');
    span.setAttribute('aria-label', label + ' Checked claim. Press to see the verdict and the passage it rests on.');
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
    if (pop && document.contains(pop)) return pop;
    pop = document.getElementById('spanSheet');
    return pop;
  }

  function sheetFill(claim) {
    pop.textContent = '';
    var handle = el('div', 'handle');
    handle.id = 'spanSheetHandle';
    handle.setAttribute('aria-label', 'Close');
    handle.addEventListener('click', function () { close(true); });
    pop.appendChild(handle);
    var x = el('button', 'close', '\u2715');
    x.type = 'button';
    x.setAttribute('aria-label', 'Close');
    x.addEventListener('click', function () { close(true); });
    pop.appendChild(x);
    pop.appendChild(el('div', 'cmtag', 'the brief\u2019s claim'));
    pop.appendChild(el('div', 'cmq', '\u201c' + claim.text + '\u201d'));
    // the verdict, in plain words, only here
    pop.appendChild(el('div', 'cmb', WORD[claim.state] + '. ' + PLAIN[claim.state] + (claim.relation ? ' ' + relationLine(claim.relation) : '')));
    var seen = 0;
    claim.cites.forEach(function (c) {
      seen += 1;
      var row = el('div', 'cmsrc');
      var src = (claim.sources.filter(function (s) { return s && s.ref === c.ref; })[0]) || {};
      var label = (src.label || c.source || 'Source') + (c.resolution === 'unresolved' ? ' \u00b7 not found in what was read' : '');
      var url = safeHref(c.url || src.url);
      var name = el('b', '', String(seen));
      row.appendChild(name);
      if (url) {
        var a = el('a', 'cws-link', label);
        a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer';
        row.appendChild(a);
        row.appendChild(document.createElement('br'));
        row.appendChild(el('span', 'cmart', 'article \u00b7 ' + (c.ref || 'open it') + ' \u00b7 ' + host(url)));
      } else {
        row.appendChild(document.createTextNode(label));
        row.appendChild(document.createElement('br'));
        row.appendChild(el('span', 'cmart', 'article \u00b7 ' + (c.ref || 'untitled')));
      }
      if (c.passage && c.passage.text) {
        row.appendChild(el('div', 'cmsub', 'The passage the check located in this article' + (c.passage.cut ? ' (the first 25 words)' : '') + ':'));
        row.appendChild(el('div', 'cmq', '\u201c' + c.passage.text + '\u201d'));
      } else if (c.window_sha256) {
        row.appendChild(el('div', 'cmsub', 'This recorded brief keeps the passage\u2019s fingerprint (' + c.window_sha256.slice(0, 10) + '\u2026), not the article\u2019s words.'));
      } else if (claim.state === 'unchecked') {
        row.appendChild(el('div', 'cmsub', 'No passage: this claim was not checked against the article.'));
      } else {
        row.appendChild(el('div', 'cmsub', 'No passage was kept for this check. The article is linked above.'));
      }
      pop.appendChild(row);
    });
    if (!seen) pop.appendChild(el('div', 'cmsrc', 'This claim cites no article the checker could read.'));
    pop.appendChild(el('div', 'cmwhy', 'Checked by claim-seal: each claim is traced to the passage it rests on, and the check is sealed' +
      (meta && meta.seal ? ' (seal ' + String(meta.seal).slice(0, 8) + '\u2026' + (meta.verified ? ', verified' : '') + ').' : '.')));
  }

  function open(t, claim) {
    if (!ensurePop()) return;
    if (current && current !== t) current.setAttribute('aria-expanded', 'false');
    current = t;
    sheetFill(claim);
    pop.classList.add('on');
    pop.setAttribute('aria-hidden', 'false');
    pop.setAttribute('tabindex', '-1');
    t.setAttribute('aria-expanded', 'true');
    pop.focus({ preventScroll: true });
    if (!listening) {
      listening = true;
      document.addEventListener('keydown', onKey, true);
      document.addEventListener('pointerdown', onOutside, true);
    }
  }
  function close(refocus) {
    if (!pop || !pop.classList.contains('on')) return;
    pop.classList.remove('on');
    pop.setAttribute('aria-hidden', 'true');
    var t = current;
    current = null;
    if (t) { t.setAttribute('aria-expanded', 'false'); if (refocus && document.contains(t)) t.focus({ preventScroll: true }); }
    if (listening) {
      listening = false;
      document.removeEventListener('keydown', onKey, true);
      document.removeEventListener('pointerdown', onOutside, true);
    }
  }
  function isOpen() { return !!(pop && pop.classList.contains('on')); }
  function onKey(e) {
    if (e.key === 'Escape') { e.stopPropagation(); close(true); }
  }
  function onOutside(e) {
    if (!isOpen() || pop.contains(e.target)) return;
    if (current && current.contains(e.target)) return;
    close(false);
  }

  // one delegated listener for every claim mark on the page
  document.addEventListener('click', function (e) {
    var t = e.target && e.target.closest ? e.target.closest('.cmark') : null;
    if (!t || !t.__claim) return;
    e.preventDefault();
    e.stopPropagation();
    if (current === t && isOpen()) close(true); else open(t, t.__claim);
  }, true);
  document.addEventListener('keydown', function (e) {
    var t = e.target && e.target.classList && e.target.classList.contains('cmark') && e.target.__claim ? e.target : null;
    if (!t || (e.key !== 'Enter' && e.key !== ' ')) return;
    e.preventDefault();
    if (current === t && isOpen()) close(true); else open(t, t.__claim);
  });

  // the strip that says what the underline means; legendNode makes it, legend puts it before a host
  function legendNode(sections, m) {
    meta = m || meta;
    var box = el('section', 'cs-legend');
    box.id = 'csLegend';
    box.setAttribute('aria-label', 'How claims were checked');
    var h = el('div', 'cs-lh');
    h.appendChild(el('span', 'cs-lk', 'claim-seal'));
    h.appendChild(el('span', 'cs-lt', (sections || []).length + ' claims checked'));
    box.appendChild(h);
    box.appendChild(el('p', 'cs-ld', 'Every underlined sentence is a claim traced to the article it cites. Press one to see the verdict, the source passage and the link.'));
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
