"""The progress lines the app page reads while a brief is made.

The pipeline reports what it is doing as (kind, text) events. The app page's entry animation and its loom read plain
lines in a fixed wording, one per stage: "compose started", "fetching <source id>", "scanning <source id> - N items (ok)",
"prompt assembled", "synthesizing", "synthesis ok - N items", "verifying", "verified", "done". This turns an event into
the line for its stage (or None when the event is only a note), so each stage the animation names (Accepting brief,
Gathering sources, Sorting signals, Applying lens, Weaving brief, Checking claims) is driven by a real event.
"""
from __future__ import annotations

import re

_ITEMS = re.compile(r"(\d+) items? \(ok\)")
_COUNT = re.compile(r"(\d+)")


def make_line_maker(sources: list, lens_name: str = ""):
    """A function (kind, text) -> line or None, for a run over `sources` (objects with .id and .label) under the lens
    called `lens_name`."""
    by_label: dict = {}
    for s in sources:
        by_label.setdefault(s.label, []).append(s.id)
    started: dict = {}  # label -> how many sources of that label have been started (two sources may share a label)

    def source_of(text: str, lead: str = ""):
        """(id, label) of the source a pipeline text starts with (the longest label that fits), else (None, None)."""
        body = text[len(lead):] if lead and text.startswith(lead) else text
        for label in sorted(by_label, key=len, reverse=True):
            if body == label or body.startswith(label + " \u00b7"):
                ids = by_label[label]
                if lead:  # a source is starting: the next one with this label
                    n = started.get(label, 0)
                    started[label] = n + 1
                else:  # a source is done: the last one started with this label
                    n = max(0, started.get(label, 1) - 1)
                return ids[min(n, len(ids) - 1)], label
        return None, None

    def line(kind: str, text: str) -> str | None:
        text = str(text or "")
        if kind == "run.started":
            if lens_name:
                return f"compose started \u00b7 {len(sources)} source{'' if len(sources) == 1 else 's'} \u00b7 lens: {lens_name}"
            return text if text.startswith("compose started") else "compose started \u00b7 " + text
        if kind == "source.started":
            sid, _ = source_of(text, "reading ")
            return f"fetching {sid}\u2026" if sid else None
        if kind == "source.done":
            sid, label = source_of(text)
            if not sid:
                return None
            ok = _ITEMS.search(text)
            if ok:
                return f"scanning {sid} — {ok.group(1)} items (ok)"
            return f"{sid} could not be read \u2014 " + text[len(label):].lstrip(" \u00b7").strip()
        if kind == "sanitize.passed":
            return "prompt assembled — " + text
        if kind == "lens.started":
            return "synthesizing under the lens…"
        if kind == "lens.applied":
            n = _COUNT.search(text)
            return f"synthesis ok — {n.group(1)} items" if n else "synthesis ok — items"
        if kind == "claim.verifying":
            return "verifying claims against the articles they cite…"
        if kind == "claim.verified":
            return "verified — " + re.sub(r"^checked · ", "", text)
        return text or None

    return line
