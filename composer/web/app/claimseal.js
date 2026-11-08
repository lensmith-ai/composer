/* claimseal.js: the strip above the insight cards that says where a brief's checked claims are.
 *
 * Every insight is a claim the checker (claim-seal) traced to the article it cites. The insight cards themselves carry
 * no claim marks and no underlines, as in the published app: the whole card opens its insight sheet, and the checked
 * claims are marked inside that sheet (by app.js), where pressing one shows the sources it rests on. This file makes the
 * one-line strip that tells a reader so. The strip names no verdict.
 *
 * API (window.__claimSeal):
 *   legendNode(sections, meta)    the strip, as a node
 *   legend(host, sections, meta)  put the strip before host (replacing an earlier one)
 * Every string from a brief or a feed goes in through textContent, never as HTML.
 */
(function () {
  'use strict';
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function legendNode(sections) {
    var box = el('section', 'cs-legend');
    box.id = 'csLegend';
    box.setAttribute('aria-label', 'How claims were checked');
    var h = el('div', 'cs-lh');
    h.appendChild(el('span', 'cs-lk', 'claim-seal'));
    h.appendChild(el('span', 'cs-lt', (sections || []).length + ' claims checked'));
    box.appendChild(h);
    box.appendChild(el('p', 'cs-ld', 'Open an insight to see its claims. Every underlined sentence there is traced to the article it cites. Press one to see the sources it rests on.'));
    return box;
  }
  function legend(hostEl, sections, m) {
    if (!hostEl || !hostEl.parentNode) return;
    var old = document.getElementById('csLegend');
    if (old) old.remove();
    hostEl.parentNode.insertBefore(legendNode(sections, m), hostEl);
  }

  window.__claimSeal = { legend: legend, legendNode: legendNode };
})();
