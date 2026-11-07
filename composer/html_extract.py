"""Optional HTML extraction tiers. Native is always available; trafilatura is an optional install.

There is one way to install it: from the hash-locked composer/extraction-requirements.lock, with every package
pinned, every file's SHA-256 checked and wheels only. Say yes to the article parser question in `composer setup` (or
`composer setup --reconfigure parser`), which runs that install in Composer's own environment; by hand it is
`python -m pip install --require-hashes --no-deps --only-binary :all: -r composer/extraction-requirements.lock`.
There is deliberately no pip extra for it: an extra would pin the parser but let pip pick the packages it needs. Without it, an html-index source that asks for trafilatura is
read with the built-in parser (text only), and its receipt says so.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from .adapters import html_index

LOCK = "extraction-requirements.lock"


class ExtractionError(ValueError):
    """The requested extraction tier is unavailable or invalid."""


def trafilatura_installed() -> bool:
    return importlib.util.find_spec("trafilatura") is not None


def lock_path() -> Path:
    return Path(__file__).with_name(LOCK)


def install_trafilatura(*, python: str | None = None, env: dict | None = None, log=print) -> None:
    """Install the parser into Composer's own environment from the hash-locked file: wheels only, every file's
    SHA-256 checked, nothing resolved beyond the file. Raises ExtractionError if anything fails."""
    python = python or sys.executable
    log("  installing the optional article parser (trafilatura and the packages it needs, hash-checked)")
    try:
        subprocess.run([python, "-m", "pip", "install", "--quiet", "--require-hashes", "--no-deps",
                        "--only-binary", ":all:", "-r", str(lock_path())], check=True, env=env)
        subprocess.run([python, "-I", "-c", "import trafilatura"], check=True, env=env, capture_output=True)
    except (subprocess.CalledProcessError, OSError) as exc:
        raise ExtractionError(f"the article parser did not install ({exc})") from None


def available_tiers() -> dict:
    return {"native": "available", "trafilatura": "available" if trafilatura_installed() else "unavailable"}


def extract(markup: str, *, tier: str = "native") -> tuple[str, str]:
    if tier == "native":
        return html_index.extract(markup)
    if tier != "trafilatura":
        raise ExtractionError("extraction tier must be native or trafilatura")
    try:
        import trafilatura
    except ImportError:
        raise ExtractionError("trafilatura extraction is not enabled") from None
    markup = markup[:html_index.MARKUP_CAP]
    text = trafilatura.extract(markup, include_comments=False, include_tables=False) or ""
    title, fallback = html_index.extract(markup)
    text = " ".join(text.split())[:html_index.DESC_CAP]
    return title, text or fallback


_PARA_MIN_WORDS = 6  # a paragraph shorter than this is a caption, a button or a notice, not article text


_TAG_END = (">", " ", "\t", "\n", "\r", "/")


def _next_p(lower: str, start: int) -> int:
    """Where the next <p> tag opens at or after `start` (not <pre>, <param>), or -1."""
    at = lower.find("<p", start)
    while at >= 0 and lower[at + 2:at + 3] not in _TAG_END:
        at = lower.find("<p", at + 2)
    return at


def _paragraphs(markup: str) -> list[str]:
    """The text of every <p>...</p> in the markup, in order, read in one pass: a paragraph ends at its </p>, or where
    the next <p> opens, or at the end, and each stretch of the page is looked at once."""
    lower = html_index.ascii_lower(markup)
    out: list[str] = []
    at = _next_p(lower, 0)
    while at >= 0:
        open_end = lower.find(">", at)
        if open_end < 0:
            break
        following = _next_p(lower, open_end)
        limit = len(lower) if following < 0 else following
        close = lower.find("</p", open_end, limit)
        out.append(html_index.strip_html(markup[open_end + 1:limit if close < 0 else close]))
        at = following
    return out


def article_text(markup: str, *, tier: str = "native") -> tuple[str, str]:
    """(title, the article's own text) from a page that a feed entry links to, for the entry's description.

    Unlike `extract` (a page's meta description, else all its text), this looks for the article body: with the
    optional parser installed and asked for, that parser; otherwise the paragraphs of the page's <article> (or
    <main>, or the whole page), those long enough to be sentences, joined. When the page has no such paragraphs, its
    meta description is used. The text is cut at the description limit; it may be empty."""
    markup = markup[:html_index.MARKUP_CAP]
    if tier == "trafilatura" and trafilatura_installed():
        title, text = extract(markup, tier=tier)
        return title, text
    lower = html_index.ascii_lower(markup)
    title = html_index.extract(markup)[0]
    cleaned = html_index._drop_blocks(markup)
    low = html_index.ascii_lower(cleaned)
    text = ""
    for scope in (html_index._between(cleaned, low, "article"), html_index._between(cleaned, low, "main"), cleaned):
        if scope is None:
            continue
        kept = [p for p in _paragraphs(scope) if len(p.split()) >= _PARA_MIN_WORDS]
        text = " ".join(kept)
        if text:
            break
    if not text:
        meta = next((a.get("content", "") for a in html_index._tags(markup, lower, "meta")
                     if a.get("name", "").strip().lower() in ("description", "twitter:description")
                     or a.get("property", "").strip().lower() == "og:description"), "")
        text = html_index.strip_html(meta)
    return title, text[:html_index.DESC_CAP]
