"""Build the one-file brief page: HTML with its stylesheet, script and brief inlined.

The page makes no outside request (its Content-Security-Policy allows only its own inline
style and script, by hash). In live mode (`composer serve`) it may also post to /api/compose
on the same server. Open the file from disk, host it anywhere static, or let the server send it.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
from pathlib import Path

WEB = Path(__file__).with_name("web")
# Shown with every brief, on this page and on the app page (composer/web/app/index.html): the brief is written by a
# model, and so is the check. EU AI Act Article 50(4) asks for this on AI-written text published about matters of
# public interest.
AI_NOTE = "AI-written summary; check the source."

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<meta name="referrer" content="no-referrer">
<title>{title}</title>
<style>{css}</style>
</head><body><div class="col">
<header class="mast"><b>lensmith composer</b><span>{badge}</span></header>
<p class="sentence">Compose from <em id="sentence-sources"></em> through the lens <em id="sentence-lens"></em>.</p>
<form id="compose" autocomplete="off">
<fieldset id="picks"><legend class="meta">Sources</legend></fieldset>
<label>Lens <input type="text" name="lens" maxlength="300" required placeholder="what to look for, e.g. what this means for small teams"></label>
{pass_field}<button type="submit">Compose</button> <span id="err" class="err" role="alert"></span>
</form>
<div class="bar"><button type="button" id="replay">Replay</button><span class="meta">{note}</span></div>
<div class="log" id="log" aria-live="polite"></div>
<p class="meta ai-note" id="ai-note">{ai_note}</p>
<main class="edition" id="edition"></main>
</div>
<script type="application/json" id="edition-data">{data}</script>
<script type="application/json" id="page-config">{config}</script>
<script>{js}</script>
</body></html>
"""


def _json_for_script(value) -> str:
    """JSON safe to place inside <script type="application/json">: no "</" can close the tag."""
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _sha(text: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii") + "'"


def build(edition: dict, *, live: bool = False, sources: list | None = None, needs_pass: bool = False) -> str:
    css = (WEB / "page.css").read_text(encoding="utf-8")
    js = (WEB / "page.js").read_text(encoding="utf-8")
    recorded = bool(edition.get("recorded"))
    if live:
        badge, note = "live · your key", "Pick sources, write a lens, press Compose. Each brief makes about 7 model calls."
    elif recorded:
        badge, note = "a recorded brief, replayed", "Nothing is composed here: this replays a brief written earlier."
    else:
        badge, note = "a brief", "A saved brief, shown as it was written."
    config = {"live": live, "sources": [{"id": s.id, "label": s.label, "available": s.available,
                                             "hidden": s.hidden, "reason": s.reason} for s in (sources or [])]}
    connect = " connect-src 'self';" if live else ""
    csp = (f"default-src 'none'; style-src {_sha(css)}; script-src {_sha(js)};{connect} "
           "img-src 'none'; form-action 'none'; base-uri 'none'")
    pass_field = ('<label>Pass phrase <input type="password" name="pass" maxlength="200"></label>\n'
                  if live and needs_pass else "")
    title = "Composer, replayed" if recorded and not live else "Composer"
    return TEMPLATE.format(csp=html.escape(csp, quote=True), title=title, css=css, badge=badge, note=note,
                           ai_note=html.escape(AI_NOTE),
                           pass_field=pass_field, data=_json_for_script(edition),
                           config=_json_for_script(config), js=js)


def write(path, edition: dict, **kwargs) -> Path:
    p = Path(path)
    p.write_text(build(edition, **kwargs), encoding="utf-8")
    return p
