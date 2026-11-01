"""html-index: a news page that links to articles, for sites with no feed.

1. One GET of the index page (the source's url).
2. Every link on it is checked BEFORE anything else is fetched: https only, no user:password,
   host in `allowed_hosts`, path under one of `allowed_path_prefixes`, duplicates dropped, at
   most `max_candidates` kept.
3. One GET per article, up to `max_items`. The title comes from <title> or the first <h1>; the
   description from <meta name="description">, else the first 800 characters of the page text.
   The first article that times out stops the run (the site is not asked again).

The page text is only sent to the model for this brief. It is never written to disk.
"""
from __future__ import annotations

import html
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from ..sanitize import clean_text, clean_url
from .common import DESC_CAP, TIMEOUT_S, TITLE_CAP, new_receipt, strip_html

# Hostile pages are expected here. Every scan below is linear in the page size: a tag's
# attributes stop at the next "<" or ">", and the title and the dropped blocks are found with
# str.find, so thousands of unclosed tags cannot make it quadratic (see the tests).
_HREF = re.compile(r"<a\b[^<>]*?\bhref\s*=\s*[\"']([^\"'<>]{1,2000})[\"']", re.I)
_META_DESC = re.compile(r"<meta\b[^<>]*?\bname\s*=\s*[\"']description[\"'][^<>]*?\bcontent\s*=\s*[\"']([^\"']{0,2000})",
                        re.I)
_DROPPED = ("script", "style", "noscript")
MARKUP_CAP = 512 * 1024  # an article page is read for its title and first lines, not in full


def _between(markup: str, lower: str, tag: str) -> str | None:
    """The text inside the first <tag ...>...</tag>, or None."""
    start = lower.find("<" + tag)
    while start >= 0:
        after = lower[start + 1 + len(tag):start + 2 + len(tag)]
        if after in (">", " ", "\t", "\n", "\r", "/"):
            break
        start = lower.find("<" + tag, start + 1)
    if start < 0:
        return None
    open_end = lower.find(">", start)
    if open_end < 0:
        return None
    close = lower.find("</" + tag, open_end)
    if close < 0:
        return None
    return markup[open_end + 1:close]


def _drop_blocks(markup: str) -> str:
    """The markup without <script>, <style> and <noscript> blocks; an unclosed one runs to the end."""
    lower = markup.lower()
    out: list[str] = []
    at = 0
    nxt = {t: lower.find("<" + t) for t in _DROPPED}  # each tag's next opening; -1 once there is none
    while True:
        for t in _DROPPED:
            if 0 <= nxt[t] < at:
                nxt[t] = lower.find("<" + t, at)
        hits = [(i, t) for t, i in nxt.items() if i >= 0]
        if not hits:
            out.append(markup[at:])
            break
        start, tag = min(hits)
        out.append(markup[at:start])
        close = lower.find("</" + tag, start)
        if close < 0:
            break
        end = lower.find(">", close)
        at = len(markup) if end < 0 else end + 1
        out.append(" ")
    return "".join(out)


def canonical(url: str) -> str | None:
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        return None
    return urlunsplit(("https", p.netloc.lower(), p.path, "", ""))


def eligible(url: str, source) -> str | None:
    """The canonical article address if the source allows it, else None."""
    url = canonical(url)
    if not url:
        return None
    p = urlsplit(url)
    d = source.discovery
    if p.hostname not in d["allowed_hosts"]:
        return None
    if not any(p.path.startswith(prefix) for prefix in d["allowed_path_prefixes"]):
        return None
    return url


def links(markup: str, page_url: str, source) -> list[str]:
    found: list[str] = []
    for href in _HREF.findall(markup[:MARKUP_CAP * 4]):
        url = eligible(urljoin(page_url, html.unescape(href)), source)
        if url and url not in found and url != canonical(page_url):
            found.append(url)
        if len(found) >= source.discovery["max_candidates"]:
            break
    return found


def extract(markup: str) -> tuple[str, str]:
    markup = markup[:MARKUP_CAP]
    lower = markup.lower()
    raw_title = _between(markup, lower, "title")
    if not (raw_title or "").strip():
        raw_title = _between(markup, lower, "h1")
    title = strip_html(raw_title or "")
    d = _META_DESC.search(markup)
    if d and d.group(1).strip():
        desc = strip_html(d.group(1))
    else:
        desc = strip_html(_drop_blocks(markup))
    return title[:TITLE_CAP], desc[:DESC_CAP]


def fetch(source, get):
    receipt = new_receipt(source)
    items: list[dict] = []
    try:
        page = get(source.url, TIMEOUT_S)
        receipt["bytes"] += len(page.body)
        if page.status != 200:
            raise ValueError(f"index page answered HTTP {page.status}")
        candidates = links(page.body.decode("utf-8", "replace"), source.url, source)
        receipt["candidates"] = len(candidates)
        errors = 0
        for url in candidates:
            if len(items) >= source.max_items:
                break
            try:
                resp = get(url, TIMEOUT_S)
            except TimeoutError:
                receipt["note"] = "an article timed out; stopped asking this site"
                break
            except Exception:
                errors += 1
                continue
            receipt["bytes"] += len(resp.body)
            if resp.status != 200:
                errors += 1
                continue
            title, desc = extract(resp.body.decode("utf-8", "replace"))
            if not title:
                errors += 1
                continue
            t, dsc, link = clean_text(title), clean_text(desc), clean_url(url)
            receipt["cleaned"] += t.changes + dsc.changes + link.changes
            items.append({"title": t.text, "description": dsc.text, "url": link.text, "published": ""})
        if errors:
            receipt["item_errors"] = errors
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"[:300]
    receipt["items"] = len(items)
    if items:
        receipt["status"] = "ok"
    elif "error" not in receipt:
        receipt["error"] = "no article on the index page could be read"
    return items, receipt
