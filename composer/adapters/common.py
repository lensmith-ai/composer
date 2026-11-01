"""Shared limits and the receipt shape for the adapters."""
from __future__ import annotations

import html
import re

TITLE_CAP = 300
DESC_CAP = 800
PUB_CAP = 64
TIMEOUT_S = 20

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.,;:!?)])")


def new_receipt(source) -> dict:
    return {"source": source.id, "label": source.label, "status": "failed", "items": 0, "bytes": 0,
            "cleaned": 0}


def strip_html(text: str) -> str:
    """Markup removed, entities decoded, whitespace collapsed."""
    text = _SPACE_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", text or ""))).strip()
    return _SPACE_BEFORE_PUNCT.sub(r"\1", text)
