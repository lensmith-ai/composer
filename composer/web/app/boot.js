(function () {
  'use strict';
  var PASS_KEY = 'composer-pass';
  function loopback() {
    var h = location.hostname;
    return h === '127.0.0.1' || h === 'localhost' || h === '[::1]' || h === '::1';
  }
  window.cwHeaders = function () {
    var pass = '';
    try { pass = sessionStorage.getItem(PASS_KEY) || ''; } catch (e) {}
    if (!pass && !loopback()) {
      pass = window.prompt('Pass phrase for this Composer server') || '';
      try { if (pass) sessionStorage.setItem(PASS_KEY, pass); } catch (e) {}
    }
    return { 'Content-Type': 'application/json', 'X-Composer-Pass': pass || 'local' };
  };
  window.cwNarrationOn = function (o) {
    o = o || {};
    if (o.narration === false || (o.narration && o.narration.enabled === false)) return false;
    return Array.isArray(o.voices) && o.voices.length > 0;
  };
  window.cwApplyNarration = function (o) {
    if (!o) return;
    var on = window.cwNarrationOn(o);
    document.documentElement.classList.toggle('cw-text-only', !on);
    var hint = document.getElementById('cmpHint');
    if (hint) hint.textContent = on ? 'Tap an amber word to change what goes in, the lens, or the voice.'
      : 'Tap an amber word to change what goes in or the lens.';
  };
  var sheets = {};
  window.cwInjectCss = function (id, css) {
    try {
      if (sheets[id]) { sheets[id].replaceSync(css); return; }
      var sheet = new CSSStyleSheet();
      sheet.replaceSync(css);
      document.adoptedStyleSheets = document.adoptedStyleSheets.concat([sheet]);
      sheets[id] = sheet;
    } catch (e) {}
  };
})();
(function(){try{var j=new URLSearchParams(location.search).get("job");if(j&&sessionStorage.getItem("turn-cache:"+j))return; }catch(e){}document.documentElement.classList.add("brief-loading");})();
