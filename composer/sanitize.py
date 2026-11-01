"""Neutralize untrusted feed text before it reaches a model prompt.

Feed titles and descriptions are written by other people. A feed can carry text such as
"ignore your previous instructions". This module does not judge content and never drops an
item. It removes invisible control characters and breaks known directive phrases with a
zero-width space, so the words stay readable as source text but no longer read as a live
instruction. Every change is counted, and the count is reported per source.

This lowers the odds of a feed steering the model. It does not rule it out: the prompt also
tells the model that source text is data, and the checking step treats sources as data too.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_ALLOWED_CONTROLS = {"\n", "\r", "\t"}
_ZERO_WIDTH_BREAK = "​"

_THREAT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bignore\s+(?:all\s+)?previous\b", re.IGNORECASE),
    re.compile(r"\bdisregard\s+(?:the\s+)?(?:above|instructions)\b", re.IGNORECASE),
    re.compile(r"(?im)^\s*(system|assistant|user)\s*:\s*"),
    re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"\bexfiltrat\w*\b", re.IGNORECASE),
    re.compile(r"\bprint\s+your\s+(?:system\s+)?prompt\b", re.IGNORECASE),
    re.compile(r"```[\s\S]*?```", re.IGNORECASE),
    re.compile(r"(?im)^\s*<{2,}\s*(?:system|assistant|user|prompt|instructions)[^>\n]*>{2,}\s*$"),
    re.compile(r"\bignore\s+(?:all\s+)?(?:your\s+)?(?:previous|prior|earlier)\b", re.IGNORECASE),
    re.compile(r"\bforget\s+(?:everything|all|your)\s+(?:above|instructions|you\s+(?:were\s+told|know))\b",
               re.IGNORECASE),
    re.compile(r"\bnew\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"\boverride\s+(?:your|the)\s+(?:instructions|rules|guardrails|safety|filters)\b", re.IGNORECASE),
    re.compile(r"\b(?:reveal|show|print|display|output)\s+your\s+(?:system\s+)?"
               r"(?:prompts?|instructions|keys?|credentials|secrets|api\s+keys?)\b", re.IGNORECASE),
    re.compile(r"\b(?:do\s+not|don'?t)\s+tell\s+(?:the\s+)?(?:user|human|operator|anyone)\b", re.IGNORECASE),
    re.compile(r"\byou'?re\s+now\b", re.IGNORECASE),
    re.compile(r"<!--\s*(?:system|assistant|user)\s*[:：]", re.IGNORECASE),
    re.compile(r"(?im)^\s*(system|assistant|user)\s*：\s*"),
    # The prompt's own source markers: a feed must not be able to write one and seem to end its section.
    re.compile(r"\[\s*(?:END\s+)?SOURCE\b", re.IGNORECASE),
)

URL_CAP = 400
_URL_SCHEME_RE = re.compile(r"^https?://", re.IGNORECASE)


@dataclass(frozen=True)
class Clean:
    text: str
    changes: int


def _strip_controls(value: str) -> Clean:
    out: list[str] = []
    count = 0
    for ch in value:
        if ch in _ALLOWED_CONTROLS:
            out.append(ch)
        elif unicodedata.category(ch) in {"Cc", "Cf"}:
            count += 1
        else:
            out.append(ch)
    return Clean("".join(out), count)


def _neutralize(match: re.Match[str]) -> str:
    span = match.group(0)
    stripped = span.lstrip()
    leading = span[: len(span) - len(stripped)]
    lowered = stripped.lower()
    if lowered.startswith(("system", "assistant", "user")):
        for colon in (":", "："):
            if colon in stripped:
                return leading + stripped.replace(colon, f"{_ZERO_WIDTH_BREAK}{colon}", 1)
        return leading + stripped[:1] + _ZERO_WIDTH_BREAK + stripped[1:]
    if stripped.startswith("```"):
        inner = stripped.strip("`").strip()
        return f"[neutralized fenced source text: {inner[:120]}]"
    words = re.split(r"(\s+)", span, maxsplit=1)
    if len(words) >= 3:
        return words[0] + _ZERO_WIDTH_BREAK + words[1] + words[2]
    return span[:1] + _ZERO_WIDTH_BREAK + span[1:]


def clean_text(value) -> Clean:
    """Text with control characters removed and directive phrases broken, plus the change count."""
    text = "" if value is None else str(value)
    stripped = _strip_controls(text)
    text, count = stripped.text, stripped.changes
    for pattern in _THREAT_PATTERNS:
        text, n = pattern.subn(_neutralize, text)
        count += n
    return Clean(text, count)


def clean_url(raw) -> Clean:
    """A link is a locator, not prose: strip control characters, keep only http(s), cap the length.

    A link with any other scheme (javascript:, data:, file:) or a relative link becomes "".
    """
    text = "" if raw is None else str(raw).strip()
    if not text:
        return Clean("", 0)
    kept = []
    count = 0
    for ch in text:
        if unicodedata.category(ch) in ("Cc", "Cf"):
            count += 1
            continue
        kept.append(ch)
    text = "".join(kept).strip()
    if not _URL_SCHEME_RE.match(text):
        return Clean("", count + 1)
    return Clean(text[:URL_CAP], count)
