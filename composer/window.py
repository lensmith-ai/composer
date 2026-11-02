"""The animated replay: a phone-width window onto Composer's own screen, playing the recorded brief.

`composer demo --site DIR` writes a small static site:

  DIR/index.html          a page that frames the window and has a Replay button
  DIR/frame.js            the Replay button (reloads the window)
  DIR/site.css            the page around the window: on a laptop the phone stands centred in it
  DIR/brief.html          the same brief as a plain, readable page (composer.page)
  DIR/window/index.html   the window: the compose screen, then the finished edition
  DIR/window/*.js, *.css  the window's own scripts and styles (composer/web/window/)
  DIR/window/standalone.js  sends a wide browser that opens the window on its own to DIR/index.html

The window shows the compose sentence, ticks the sources the brief read, runs the sand and
word animation through each recorded step, weaves the sources into the brief, and settles on
the finished edition. Every card opens its detail: the brief's own words with the cited
phrases marked, each phrase's article link, and the fingerprint of the passage checked. It
holds no article text. Nothing is fetched and nothing is composed; with reduced motion, or
with scripts off, it shows the finished edition.
"""
from __future__ import annotations

import html
import json
import re
import shutil
from datetime import date
from pathlib import Path

from . import page, registry

WINDOW_ASSETS = Path(__file__).with_name("web") / "window"
WINDOW_FILES = ("surface.css", "entry-transition.css", "window.css", "sand-engine.js",
                "composer-entry-transition.js", "window.js")
WINDOW_SCRIPTS = ("sand-engine.js", "composer-entry-transition.js", "window.js")
WINDOW_SIZE = (390, 660)
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; "
       "connect-src 'none'; form-action 'none'; base-uri 'none'")
SITE_CSP = CSP + "; frame-src 'self'"
CARD_STATES = {"supported": "supported", "partial": "partly supported", "unsupported": "not supported",
               "unchecked": "not checked"}
SOURCE_HUES = ("#b98bff", "#ff6b8b", "#6e8bff", "#7fd4ff", "#ff9f6e", "#9ad66b")
NAME_CHAR_W = 4.9  # a spool name's capital at 7 px monospace with .1em letter spacing, in viewBox units
VERDICT_HUES = {"supported": "#48d1a0", "partial": "#ffb84a", "unsupported": "#ff6b6b", "unchecked": "#7a8392"}
GEAR_SVG = ('<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3.2"></circle>'
            '<path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 '
            '1.55V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 '
            '0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 '
            '2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.51 1.7 1.7 0 0 0 '
            '1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9a1.7 1.7 0 0 0 1.55 1H21a2 2 0 1 1 0 4h-.09a1.7 '
            '1.7 0 0 0-1.51 1z"></path></svg>')

e = html.escape


def web_link(url) -> bool:
    """Only an http(s) address becomes a link; anything else (javascript:, data:) is not printed."""
    return isinstance(url, str) and url.lower().startswith(("https://", "http://"))


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def long_date(value: str) -> str:
    d = date.fromisoformat(value)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def card_sources(ed: dict, card: dict) -> list[int]:
    labels = [x["label"] for x in ed["sources"]]
    return sorted({labels.index(c["label"]) for c in card["citations"] if c["label"] in labels})


def steps(ed: dict) -> list[dict]:
    labels = [x["label"] for x in ed["sources"]]
    n = len(ed["cards"])
    tally: dict[str, int] = {}
    for c in ed["cards"]:
        tally[c["state"]] = tally.get(c["state"], 0) + 1
    out = [("run.started", f"compose started · {plural(len(labels), 'source')} · {ed['lens']} lens",
            "composition - sources")]
    out += [("source.started", f"reading {x['label']} · {plural(x['items'], 'item')} "
             f"({'ok' if x.get('status', 'ok') == 'ok' else 'failed'})", "") for x in ed["sources"]]
    out += [("sanitize.passed", "prompt assembled", "composition - screening"),
            ("lens.started", f"synthesizing under the {ed['lens']} lens", "composition - lens"),
            ("lens.applied", f"synthesis ok · {plural(n, 'insight')}", "composition - weaving"),
            ("claim.verifying", "verifying claims against the articles they cite", "composition - verifying"),
            ("claim.verifying", "checked · " + " · ".join(f"{v} {CARD_STATES[k]}" for k, v in tally.items()), "")]
    return [{"type": t, "text": x, "head": h} for t, x, h in out]


def seal_counts(ed: dict) -> tuple[int, int]:
    chk = ed.get("check") or {}
    rows = int(chk.get("rows") or 0)
    agree = int(chk.get("agree", rows if chk.get("seal_verified") else 0))
    return agree, rows


def shown_relation(relation) -> str:
    """How a cited source bears on the marked words; claim-seal's "undetermined" (it could not tell) reads "cites"."""
    return relation if isinstance(relation, str) and relation and relation != "undetermined" else "cites"


def spool_name_lines(label: str, width: float) -> list[str]:
    """A source's name for a narrow spool: capitals without a trailing "blog", in at most two lines that each fit
    `width`; a word that still does not fit is cut with an ellipsis."""
    words = re.sub(r"\s+blog$", "", label.strip(), flags=re.I).upper().split() or [label.upper()]
    fit = max(1, int(width // NAME_CHAR_W))
    lines: list[str] = []
    for w in words:
        if lines and len(lines[-1]) + 1 + len(w) <= fit:
            lines[-1] += " " + w
        else:
            lines.append(w)
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]
    return [t if len(t) <= fit else t[:fit - 1] + "…" for t in lines]


def loom_svg(ed: dict) -> str:
    """The finished weave: a spool per source, a thread per item read, the SCREEN band, the LENS line, and the
    tray the cited items are woven into. An uncited thread stops at the lens (dashed); a cited one ends in its
    line's label colour."""
    W, H = 340, 262
    src = ed["sources"]
    cited = []
    for x in src:
        seen: dict[str, str] = {}
        for c in ed["cards"]:
            for cit in c["citations"]:
                if cit["label"] == x["label"]:
                    best = seen.get(cit["url"])
                    seen[cit["url"]] = "supported" if c["state"] == "supported" or best == "supported" else c["state"]
        cited.append(list(seen.values()))
    lanes = sum(x["items"] for x in src)
    left, right = 34, W - 34
    step = (right - left) / max(1, lanes - 1)
    gap = (W - 40) / max(1, len(src))
    out = [f'<svg id="loom" class="lw-loom" viewBox="0 0 {W} {H}" role="img" aria-label="The weave: '
           + e(", ".join(plural(x["items"], "item") + " from " + x["label"] for x in src)) + ", through the "
           + e(ed["lens"]) + f' lens; {sum(len(c) for c in cited)} cited items woven into {plural(len(ed["cards"]), "line")}">']
    out.append(f'<text class="lband" x="20" y="88">SCREEN</text><rect class="lscreen" x="20" y="93" width="{W - 40}" '
               'height="9" rx="4.5"></rect>')
    out.append('<text class="lband" x="20" y="138">LENS · ' + e(ed["lens"].upper()) + '</text>'
               f'<line class="llens" x1="20" y1="144" x2="{W - 20}" y2="144"></line>')
    out.append(f'<rect class="ltray" x="20" y="210" width="{W - 40}" height="44" rx="7"></rect>'
               + "".join(f'<line class="ltrayline" x1="26" y1="{y}" x2="{W - 26}" y2="{y}"></line>' for y in (222, 232, 242)))
    lane = 0
    for i, x in enumerate(src):
        hue = SOURCE_HUES[i % len(SOURCE_HUES)]
        cx = 20 + gap * (i + 0.5)
        for j in range(x["items"]):
            lx = left + step * lane
            lane += 1
            verdict = cited[i][j] if j < len(cited[i]) else None
            end = 246 if verdict else 144
            d = f"M{cx:.1f} 47 C{cx:.1f} 66 {lx:.1f} 54 {lx:.1f} 78 L{lx:.1f} {end}"
            if verdict:
                out.append(f'<path class="lthread" d="{d}" stroke="{hue}"></path>')
                out.append(f'<circle class="lmark" cx="{lx:.1f}" cy="246" r="3.2" fill="{VERDICT_HUES[verdict]}"></circle>')
            else:
                out.append(f'<path class="lthread lthread-cut" d="{d}" stroke="{hue}" data-dash="1"></path>')
        if gap >= 112:  # room for the full spool: "5 items" and the name on one line
            out.append(f'<g class="lspool"><rect x="{cx - 54:.1f}" y="8" width="108" height="20" rx="10" stroke="{hue}"></rect>'
                       f'<circle cx="{cx - 42:.1f}" cy="18" r="3" fill="{hue}"></circle><text class="lcount" x="{cx + 4:.1f}" '
                       f'y="21.5">{plural(x["items"], "item")}</text><text class="lname" x="{cx:.1f}" y="41">'
                       + e(x["label"].upper()) + "</text></g>")
        else:  # many sources: a narrower spool with the count only, and the name in at most two short lines
            w = gap - 6
            names = "".join(f'<text class="lname" x="{cx:.1f}" y="{y}">{e(t)}</text>'
                            for y, t in zip((37, 44), spool_name_lines(x["label"], gap - 2)))
            out.append(f'<g class="lspool"><rect x="{cx - w / 2:.1f}" y="8" width="{w:.1f}" height="20" rx="10" '
                       f'stroke="{hue}"></rect><circle cx="{cx - w / 2 + 9:.1f}" cy="18" r="3" fill="{hue}"></circle>'
                       f'<text class="lcount" x="{cx + 4:.1f}" y="21.5">{x["items"]}</text>' + names + "</g>")
    out.append("</svg>")
    return "".join(out)


def marked_html(words: str, spans: list) -> str:
    """One printed line with its cited phrases marked and numbered. Offsets count code points."""
    out, at = "", 0
    for start, end, n in sorted(spans):
        if start < at:
            raise ValueError("two citations overlap in one printed line")
        out += e(words[at:start]) + '<mark class="cmark">' + e(words[start:end]) + f'</mark><sup class="rcpnum">{n}</sup>'
        at = end
    return out + e(words[at:])


def _field_words(card: dict, field: str) -> str:
    if field == "why":
        return card["why"]
    if field == "insight":
        return card["insight"]
    return card["details"][int(field[len("details["):-1])]


def insight_detail_html(ed: dict, i: int, card: dict) -> str:
    fields_in_order = ["why"] + [f"details[{k}]" for k in range(len(card["details"]))]
    cits = [c for c in card["citations"] if "field" in c]
    order = sorted(cits, key=lambda c: (fields_in_order.index(c["field"]) if c["field"] in fields_in_order else -1,
                                        c["start"]))
    number = {id(c): n for n, c in enumerate(order, 1)}

    def line(field, words):
        return marked_html(words, [(c["start"], c["end"], number[id(c)]) for c in cits if c["field"] == field])

    agree, rows = seal_counts(ed)
    each = rows and agree == rows == sum(len(c["citations"]) for c in ed["cards"])
    name = "The insight" if i == 0 else f"Insight {i + 1}"
    k = len(card_sources(ed, card))
    points = ('<li class="lede">' + line("why", card["why"]) + "</li>"
              + "".join("<li>" + line(f"details[{j}]", d) + "</li>" for j, d in enumerate(card["details"])))
    receipts = ""
    for c in order:
        words = _field_words(card, c["field"])
        fp = f'fingerprint {c["window_sha256"][:12]}' if c.get("window_sha256") else "no passage located"
        receipts += (f'<li class="rcp"><b>{number[id(c)]} · ' + e(c["label"]) + " " + e(shown_relation(c.get("relation")))
                     + ' this</b><span class="cmq">' + e(words[c["start"]:c["end"]]) + '</span><span class="rcpmeta">'
                     + ("claim-seal re-check: agrees · " if each else "") + fp + "</span>"
                     + (('<a class="rcplink" href="' + e(c["url"], quote=True) + '" target="_blank" '
                         'rel="noopener noreferrer">Open the ' + e(c["label"]) + " article</a>")
                        if web_link(c.get("url")) else "") + "</li>")
    stamp = (f"claim-seal · run again on the recorded answers · {agree} of {rows} checks agree" if ed.get("recorded")
             else f"claim-seal · {plural(rows, 'sealed row')}")
    return (f'<div class="lw-detail" id="lwDetail{i}" hidden><div class="desk">{name} · {CARD_STATES[card["state"]]} · '
            f'{plural(k, "source")}</div><h3>' + e(card["insight"]) + '</h3><div class="shdate">'
            + e(long_date(ed["composed_on"])) + " · " + e(ed["lens"]) + ' lens</div><ul class="shpoints">' + points
            + '</ul><div class="rk">sources &amp; seals</div><ol class="rcps">' + receipts + '</ol><div class="stamp">'
            + stamp + "</div></div>")


def window_html(ed: dict, picker_rows: list[str]) -> str:
    """The window page: the compose screen and the finished edition, filled from the brief. As served it
    shows the finished edition; window.js turns it back to the compose screen and plays the run."""
    labels = [x["label"] for x in ed["sources"]]
    missing = set(labels) - set(picker_rows)
    if missing:
        raise ValueError("a recorded source is missing from the compose sheet: " + ", ".join(sorted(missing)))
    cards = ed["cards"]
    n = len(cards)
    agree, rows = seal_counts(ed)
    data = {"seconds": ed.get("seconds", 0), "cards": n, "sources": labels, "chosen": plural(len(labels), "source"),
            "steps": steps(ed), "rows": list(picker_rows)}
    sentence = ('Compose from <button type="button" class="cmpslot" data-kind="sources" aria-label="sources: everything">'
                'everything</button> through the <button type="button" class="cmpslot" data-kind="lens" aria-label="lens: '
                + e(ed["lens"]) + '">' + e(ed["lens"]) + '</button> lens<span class="cmpell">.</span>'
                '<span class="cmpell">.</span><span class="cmpell blink">.</span>')
    choose = ('<div class="cmpbody" id="cmpBody" hidden><p class="cmpsent" id="cmpSent">' + sentence + '</p>'
              '<div class="cmphint" id="cmpHint">Tap an amber word to change what goes in or the lens.</div>'
              '<button class="cmpgo" id="cmpGo" type="button">Compose</button>'
              '<div class="cmpnote" id="cmpNote">a recorded run · nothing is composed here</div></div>')
    deck = ""
    for i, c in enumerate(cards):
        k = len(card_sources(ed, c))
        label = "The insight" if i == 0 else f"Insight {i + 1}"
        deck += ('<article class="icw"><div class="icard"><div class="ik"><span>' + label + '</span><br>'
                 f'<span class="prooftag v-{c["state"]}">{CARD_STATES[c["state"]]} · {plural(k, "source")}</span></div>'
                 '<h3>' + e(c["insight"]) + '</h3><div class="gk keep">why it matters</div><div class="gv keep">'
                 + e(c["why"]) + '</div></div><button type="button" class="lw-open" data-detail="lwDetail' + str(i)
                 + '" aria-haspopup="dialog" aria-label="Open ' + e(label.lower() + ": " + c["insight"], quote=True)
                 + '"></button></article>')
    readout = ('<section class="audio acard cmp-assembly-piece is-in"><div class="ahead"><div><div class="aeye">Daily readout'
               '</div><div class="atit">This edition</div><div class="adesc">' + plural(n, "insight") + " composed from "
               + e(", ".join(labels)) + " under the " + e(ed["lens"]) + ' lens.</div></div><span class="abadge">fresh '
               + e(ed["composed_on"]) + '</span></div><div class="aplay lw-aplay" aria-disabled="true"><span class="apbtn" '
               'aria-hidden="true">▶</span><span class="aptxt"><b>No narration in this replay</b><span class="albl">'
               'The edition is below, line by line</span></span></div></section>')
    rail = ('<div class="crail-scroll cmp-assembly-piece is-in"><div class="crail">'
            + "".join(f'<span class="crchip{" on" if i == 0 else ""}">' + ("The insight" if i == 0 else f"Insight {i + 1}")
                      + "</span>" for i in range(n)) + "</div></div>")
    went = ('<section class="ingr cmp-assembly-piece is-in"><div class="ingrlab">What went in · '
            + plural(len(labels), "source") + '</div><div class="ingrstrip">'
            + "".join(f'<div class="ingrow"><span class="idot lw-hue-{i % len(SOURCE_HUES)}"></span><span class="iname">' + e(x["label"])
                      + '</span><span class="ifresh">' + plural(x["items"], "item") + "</span></div>"
                      for i, x in enumerate(ed["sources"])) + "</div></section>")
    if ed.get("recorded"):
        receipt_text = (f"Composed {long_date(ed['composed_on'])} · a recorded run, replayed · claim-seal, run again on "
                        f"the recorded answers: {agree} of {rows} checks agree")
    else:
        receipt_text = f"Composed {long_date(ed['composed_on'])} · checked with claim-seal: {plural(rows, 'sealed row')}"
    receipt = '<p class="lw-receipt cmp-assembly-piece is-in">' + e(receipt_text) + "</p>"
    d = date.fromisoformat(ed["composed_on"])
    settled = ('<div class="cmprun" id="cmpRun"><div class="cmprunhead"><span class="cmpdot" aria-hidden="true"></span>'
               '<span class="cmpstep" id="cmpStep">Composition complete.</span><span id="cmpEntryStatus" class="sr-only" '
               'aria-live="polite" aria-atomic="true"></span><span class="cmpclock" id="cmpClock" aria-hidden="true"></span>'
               '</div><p class="lw-mk cmp-assembly-piece is-in">lensmith · the live edition</p>'
               '<header class="cmp-composed-mast cmp-assembly-piece is-in"><span class="mbtn" aria-hidden="true">☰</span><h2>'
               + e(cards[0]["insight"]) + '</h2><span class="mbtn" aria-hidden="true">ⓘ</span></header>'
               '<div class="daterow cw-daterow"><div class="sub cw-mast-sub cmp-assembly-piece is-in">'
               + e(f"{d.strftime('%A, %B')} {d.day}, {d.year}") + '</div><div class="status cw-mast-status '
               f'cmp-assembly-piece is-in" id="lwStatus">published · {n}/{n}</div></div>'
               '<div class="cmpstage entry-loom-revealed" id="cmpStage"><div class="stage-scroll">' + loom_svg(ed)
               + '</div><div class="loomhead" id="cmpLoomHead">composition - woven</div></div>'
               '<div class="lw-checked cmp-assembly-piece is-in"><span class="lw-checked-dot" aria-hidden="true"></span>checked'
               f'<span class="lw-checked-n"> · {agree}/{rows}</span></div>'
               '<div id="cmpSettledContent"><section class="cmp-completion-assembly" aria-label="Completed brief">' + readout
               + rail + '<div class="cdeck cmp-assembly-piece is-in" aria-label="Completed insight cards">' + deck + "</div>"
               + '<div class="cdeckfoot cmp-assembly-piece is-in"><div class="cdots">'
               + "".join(f'<span class="cdot{" on" if i == 0 else ""}"></span>' for i in range(n))
               + f'</div><div class="ccount">1 of {n}</div></div>' + went + receipt + "</section></div></div>")
    head = ('<div class="cmpmast" aria-hidden="true">lensmith</div><div class="cmphead"><span class="infobtn menubtn" '
            'id="cmpMenu" aria-hidden="true">☰</span><div class="cmpeye" id="cmpEye">New composition</div>'
            '<span class="cmpsetlink" id="cmpSetLink" aria-hidden="true">' + GEAR_SVG + "</span></div>")
    return ('<!doctype html>\n<html lang="en" class="lw lw-settled"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer">'
            '<meta http-equiv="Content-Security-Policy" content="' + e(CSP, quote=True) + '"><title>Composer, replayed</title>'
            '<link rel="stylesheet" href="surface.css"><link rel="stylesheet" href="entry-transition.css" '
            'id="composerEntryTransitionStyles"><link rel="stylesheet" href="window.css">'
            + '<script src="standalone.js"></script>'
            + "".join(f'<script src="{x}" defer></script>' for x in WINDOW_SCRIPTS) + "</head>"
            '<body class="composing done" data-choreo-state="settled"><div id="lwView" aria-hidden="true"></div><div class="col">'
            '<section class="cmp on" id="cmp" data-state="settled" aria-label="Composer, a recorded composition" data-lw="'
            + e(json.dumps(data, ensure_ascii=False), quote=True) + '">' + head + choose + settled + "</section></div>"
            + "".join(insight_detail_html(ed, i, c) for i, c in enumerate(cards))
            + '<div class="scrim" id="lwScrim" hidden></div><div class="sheet" id="sheet" role="dialog" aria-modal="true" '
            'aria-labelledby="shTitle" tabindex="-1" hidden><div class="handle" aria-hidden="true"></div>'
            '<button class="close" id="sheetClose" type="button" aria-label="Close">✕</button><div id="shBody"></div>'
            "</div></body></html>\n")


# The page around the window. On a laptop the phone stands in the middle of the page, with the title
# on its left and a short note on its right; below 1024 px they stack, centred; on a phone the window
# fills the width. The window itself is always 390 px wide (it is a phone screen), so it never
# changes width when the replay ends. Colours and type follow Composer's own screen.
SITE_CSS = (
    ":root{--ground:#0b0e13;--panel:#10141b;--ink:rgba(255,255,255,.92);--ink2:#b4bac4;--ink3:#7a8392;"
    "--line:#485161;--amber:#ffb020;color-scheme:dark}"
    "*{box-sizing:border-box}"
    "html,body{margin:0;background:var(--ground);color:var(--ink)}"
    "body{font:16px/1.6 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;-webkit-font-smoothing:antialiased}"
    ".top,.demo{max-width:80rem;margin:0 auto;padding:0 16px}"
    ".top{padding-top:12px}"
    ".mark{font-weight:700;color:var(--amber)}"
    ".demo{display:grid;grid-template-columns:minmax(0,1fr);justify-items:center;gap:20px;padding-bottom:48px}"
    ".head,.about{width:100%;max-width:40rem;text-align:center}"
    ".tag{display:inline-block;margin:18px 0 0;padding:3px 8px;border-radius:4px;background:var(--amber);color:var(--ground);"
    "font-size:12px;font-weight:700;line-height:16px;letter-spacing:.13em;text-transform:uppercase}"
    "h1{margin:.375rem 0 .25rem;font-size:2rem;line-height:1.25}"
    ".dek{margin:0;font-size:1.1rem;line-height:1.45;color:var(--ink2)}"
    ".stage{width:100%;display:flex;flex-direction:column;align-items:center}"
    ".phone{width:390px;max-width:100%}"
    ".screen{position:relative;height:660px;overflow:hidden;background:var(--ground);isolation:isolate}"
    "iframe{display:block;width:390px;max-width:100%;height:660px;border:0;background:var(--ground)}"
    ".bar{display:flex;justify-content:center;margin:12px 0 0}"
    ".play{min-width:44px;min-height:44px;padding:0 22px;border:0;border-radius:999px;background:var(--amber);color:var(--ground);"
    "font:700 15px/1 system-ui,sans-serif;cursor:pointer}"
    ".play:active{background:#d98f00}"
    ".play:focus-visible,a:focus-visible{outline:2px solid var(--amber);outline-offset:3px}"
    ".about h2{margin:0 0 .5rem;font-size:1.15rem;line-height:1.3}"
    ".about p{margin:0 0 .75rem;color:var(--ink2)}"
    ".links{list-style:none;margin:1rem 0 0;padding:0;display:flex;flex-wrap:wrap;justify-content:center;gap:4px 20px}"
    ".links a{display:inline-flex;align-items:center;min-height:44px;color:var(--amber)}"
    "@media (min-width:600px){.phone{width:414px;padding:11px;border:1px solid var(--line);border-radius:44px;background:var(--panel);"
    "box-shadow:0 18px 48px rgba(0,0,0,.45)}.screen{border-radius:32px}}"
    "@media (max-width:599px){.demo{padding:0}.head,.about{padding:0 16px}.stage{width:100vw;max-width:100%}"
    ".phone,iframe{width:100%}}"
    "@media (min-width:1024px){.demo{grid-template-columns:minmax(0,1fr) 414px minmax(0,1fr);align-items:start;"
    "column-gap:48px;padding-top:4px}"
    ".head{grid-column:1;grid-row:1;text-align:left;justify-self:end;max-width:22rem;padding-top:32px}"
    ".stage{grid-column:2;grid-row:1}"
    ".about{grid-column:3;grid-row:1;text-align:left;justify-self:start;max-width:22rem;padding-top:48px}"
    ".links{flex-direction:column;justify-content:flex-start;gap:0}}"
    "@media (prefers-reduced-motion:reduce){.bar{display:none}}"
    "@media (scripting:none){.bar{display:none}}"
)

FRAME_JS = ("(function(){'use strict';var b=document.getElementById('replay'),f=document.getElementById('cw');"
            "if(!b||!f)return;if(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;"
            "b.hidden=false;b.addEventListener('click',function(){"
            "f.src='window/index.html?r='+Date.now()+'#replay';});})();\n")

# Loaded first by the window. Opened on its own in a wide browser window (not inside the demo page,
# not on a phone), the window would stretch across the screen while it plays; this sends the reader to
# the demo page, where it sits in its phone frame. Add ?standalone to the address to stay.
STANDALONE_JS = ("(function(){'use strict';try{if(window.top===window&&window.matchMedia"
                 "&&window.matchMedia('(min-width: 600px)').matches&&!/[?&]standalone\\b/.test(location.search))"
                 "{location.replace('../index.html');}}catch(e){}})();\n")


NUMBER_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def provenance(ed: dict) -> str:
    """What the landing page says it replays, from the recorded edition itself: its date, its sources and its lens."""
    labels = [x["label"] for x in ed["sources"]]
    n = len(labels)
    count = NUMBER_WORDS[n] if n < len(NUMBER_WORDS) else str(n)
    names = labels[0] if n == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]
    return (f"replaying a brief it wrote on {long_date(ed['composed_on'])} from {count} public "
            f"feed{'' if n == 1 else 's'} ({names}), read through the lens “{ed['lens']}”")


def site_index_html(ed: dict) -> str:
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer">'
            '<meta http-equiv="Content-Security-Policy" content="' + e(SITE_CSP, quote=True) + '">'
            '<title>Composer, replayed</title><link rel="stylesheet" href="site.css">'
            '<script src="frame.js" defer></script></head><body>'
            '<header class="top"><span class="mark">lensmith</span></header>'
            '<main class="demo">'
            '<div class="head"><p class="tag">Recorded demo</p><h1>Composer</h1>'
            '<p class="dek">Composer reads a few feeds, writes a short brief through a lens you choose, and checks every '
            'claim against the article it cites before you read it.</p></div>'
            '<section class="stage" aria-label="Composer, replaying one recorded brief"><div class="phone"><div class="screen">'
            f'<iframe id="cw" src="window/index.html#replay" title="Composer replaying one recorded brief" '
            f'width="{WINDOW_SIZE[0]}" height="{WINDOW_SIZE[1]}"></iframe></div>'
            '<div class="bar"><button type="button" class="play" id="replay" hidden>Replay</button></div></div></section>'
            '<section class="about" aria-labelledby="about-h"><h2 id="about-h">What you are looking at</h2>'
            '<p>Composer\'s own phone screen, ' + e(provenance(ed)) + '.</p>'
            '<p>Nothing is composed here: no model is called and the page makes no outside request. When the replay '
            'ends, open a card to see which of its words each article backs, and the checker\'s verdict.</p>'
            '<ul class="links"><li><a href="brief.html">The same brief as a plain page</a></li>'
            '<li><a href="https://github.com/lensmith-ai/composer" rel="noreferrer">Run it yourself</a></li>'
            '<li><a href="https://github.com/lensmith-ai/claim-seal" rel="noreferrer">claim-seal, the checker</a></li>'
            '</ul></section></main></body></html>\n')


def write_site(directory, ed: dict, picker_rows: list[str] | None = None) -> list[Path]:
    """Write the static demo site; returns the files written."""
    out = Path(directory)
    win = out / "window"
    win.mkdir(parents=True, exist_ok=True)
    if picker_rows is None:
        picker_rows = [s.label for s in registry.read_file(registry.BUNDLED)]
    written = []
    for name in WINDOW_FILES:
        shutil.copyfile(WINDOW_ASSETS / name, win / name)
        written.append(win / name)
    files = {win / "index.html": window_html(ed, picker_rows), out / "index.html": site_index_html(ed),
             out / "site.css": SITE_CSS, out / "frame.js": FRAME_JS, out / "brief.html": page.build(ed),
             win / "standalone.js": STANDALONE_JS}
    for path, text in files.items():
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written
