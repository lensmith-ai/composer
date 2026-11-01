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

_HREF = re.compile(r"<a\b[^>]*\bhref\s*=\s*[\"']([^\"']+)[\"']", re.I)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>|<h1[^>]*>(.*?)</h1>", re.I | re.S)
_META_DESC = re.compile(r"<meta\b[^>]*\bname\s*=\s*[\"']description[\"'][^>]*\bcontent\s*=\s*[\"']([^\"']*)", re.I)
_DROP = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.I | re.S)


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
    for href in _HREF.findall(markup):
        url = eligible(urljoin(page_url, html.unescape(href)), source)
        if url and url not in found and url != canonical(page_url):
            found.append(url)
        if len(found) >= source.discovery["max_candidates"]:
            break
    return found


def extract(markup: str) -> tuple[str, str]:
    m = _TITLE.search(markup)
    title = strip_html(next((g for g in m.groups() if g), "")) if m else ""
    d = _META_DESC.search(markup)
    if d and d.group(1).strip():
        desc = strip_html(d.group(1))
    else:
        desc = strip_html(_DROP.sub(" ", markup))
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
