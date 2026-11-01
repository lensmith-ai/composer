"""Shared limits and the receipt shape for the adapters."""
from __future__ import annotations

import html
import re

TITLE_CAP = 300
DESC_CAP = 800
PUB_CAP = 64
TIMEOUT_S = 20
# Raw text kept before markup is stripped: far more than any title or description needs, and a
# bound on the work a hostile feed can cause.
RAW_CAP = 64 * 1024

# Every pattern here runs in time linear in its input: a tag ends at the next "<" or ">", so a
# page made of thousands of unclosed "<" cannot make the scan quadratic.
_TAG_RE = re.compile(r"<[^<>]+>")
_SPACE_RE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.,;:!?)])")


def new_receipt(source) -> dict:
    return {"source": source.id, "label": source.label, "status": "failed", "items": 0, "bytes": 0,
            "cleaned": 0}


def strip_html(text: str) -> str:
    """Markup removed, entities decoded, whitespace collapsed (on at most RAW_CAP characters)."""
    text = _SPACE_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", (text or "")[:RAW_CAP]))).strip()
    return _SPACE_BEFORE_PUNCT.sub(r"\1", text)
