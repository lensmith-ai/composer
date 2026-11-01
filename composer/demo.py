"""The no-key demo: replay the recorded brief in the terminal, or write it as a page.

The recorded brief (composer/data/recorded-run.json) was composed on 2026-10-25 from the two
bundled feeds. It holds our own words, the cited titles and links, the verdicts and SHA-256
digests of the checked passages, and none of the articles' text. The demo makes no network
request and no model call.
"""
from __future__ import annotations

import json
import re
import textwrap
import time
from pathlib import Path

RECORDED = Path(__file__).parent / "data" / "recorded-run.json"
STATE = {"supported": "supported", "partial": "partly supported", "unsupported": "not supported",
         "unchecked": "not checked"}
FIELD_RE = re.compile(r"^(insight|why|details\[(\d+)\])$")


def load(path=RECORDED) -> dict:
    ed = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = validate(ed)
    if problems:
        raise ValueError("the recorded brief is malformed: " + "; ".join(problems))
    return ed


def field_text(card: dict, field: str) -> str | None:
    m = FIELD_RE.match(field or "")
    if not m:
        return None
    if m.group(1) == "insight":
        return card["insight"]
    if m.group(1) == "why":
        return card["why"]
    k = int(m.group(2))
    return card["details"][k] if k < len(card["details"]) else None


def validate(ed: dict) -> list[str]:
    """Shape problems in an edition; every citation offset must fall inside the words it marks."""
    errs = []
    if ed.get("schema") != "composer-edition/v1":
        errs.append("unknown schema")
    labels = {s.get("label") for s in ed.get("sources") or []}
    cards = ed.get("cards")
    if not isinstance(cards, list) or not cards:
        return errs + ["no cards"]
    for i, c in enumerate(cards):
        if c.get("state") not in STATE:
            errs.append(f"card {i}: unknown state")
        for x in c.get("citations") or []:
            if x.get("label") not in labels:
                errs.append(f"card {i}: a citation names a source the brief did not read")
            if not str(x.get("url", "")).startswith("https://"):
                errs.append(f"card {i}: a citation link is not https")
            if "field" in x:
                words = field_text(c, x["field"])
                if words is None or not (0 <= x["start"] < x["end"] <= len(words)):
                    errs.append(f"card {i}: citation offsets fall outside the words")
            sha = x.get("window_sha256")
            if sha is not None and not re.fullmatch(r"[0-9a-f]{64}", str(sha)):
                errs.append(f"card {i}: a passage fingerprint is not a sha256")
    return errs


def steps(ed: dict) -> list[str]:
    n = len(ed["cards"])
    tally: dict[str, int] = {}
    for c in ed["cards"]:
        tally[c["state"]] = tally.get(c["state"], 0) + 1
    out = [f"compose started · {len(ed['sources'])} sources · lens: {ed['lens']}"]
    out += [f"reading {s['label']} · {s['items']} items ({'ok' if s.get('status') == 'ok' else 'failed'})"
            for s in ed["sources"]]
    out += ["source text screened, prompt assembled", "writing through the lens",
            f"brief written · {n} insights", "checking each claim against the articles it cites",
            "checked · " + " · ".join(f"{v} {STATE[k]}" for k, v in tally.items())]
    return out


def text_report(ed: dict, width: int = 88) -> str:
    wrap = lambda s, indent="": textwrap.fill(s, width=width, initial_indent=indent,  # noqa: E731
                                              subsequent_indent=indent)
    lines = [f"{len(ed['cards'])} insights from {', '.join(s['label'] for s in ed['sources'])}, "
             f"lens: {ed['lens']} · {ed['composed_on']}", ""]
    for i, c in enumerate(ed["cards"], 1):
        lines.append(wrap(f"{i}. {c['insight']}  [{STATE[c['state']]}]"))
        lines.append(wrap(c["why"], "   "))
        for d in c.get("details") or []:
            lines.append(textwrap.fill(d, width=width, initial_indent="   - ", subsequent_indent="     "))
        for n, x in enumerate(c.get("citations") or [], 1):
            rel = f" ({x['relation']})" if x.get("relation") else ""
            fp = f" · passage {x['window_sha256'][:12]}" if x.get("window_sha256") else ""
            lines.append(wrap(f"[{n}] {x['label']}{rel}: {x.get('title', '')}", "   "))
            lines.append(f"       {x['url']}{fp}")
        lines.append("")
    chk = ed.get("check") or {}
    if chk.get("note"):
        lines.append(wrap(chk["note"]))
    m = ed.get("model") or {}
    if m.get("calls") is not None:
        tok = (f", {m['input_tokens']:,} input and {m['output_tokens']:,} output tokens"
               if isinstance(m.get("input_tokens"), int) else "")
        who = f" Written and checked by {m['name']}." if m.get("name") else ""
        lines.append(wrap(f"{m['calls']} model calls{tok}.{who}"))
    return "\n".join(lines)


def replay(ed: dict, out, *, beat_s: float = 0.6, sleep=time.sleep) -> None:
    out.write("Replaying a recorded brief. No key, no network, no model call.\n\n")
    for line in steps(ed):
        out.write(f"  {line}\n")
        out.flush()
        if beat_s:
            sleep(beat_s)
    out.write("\n" + text_report(ed) + "\n")
