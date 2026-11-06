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

from .. import fetch as _fetch
from ..sanitize import clean_text, clean_url
from .common import DESC_CAP, TIMEOUT_S, TITLE_CAP, new_receipt, strip_html

# Hostile pages are expected here. Nothing below is a backtracking regex: tags and their
# attributes are read in one pass with str.find and a small scanner, so the work grows with the
# page size and no arrangement of tags or attributes can make it quadratic (see the tests).
ATTR_CAP = 2000  # the longest attribute value kept (an address or a description)
_SPACE = " \t\n\r\f"


def _attrs(tag: str) -> dict[str, str]:
    """The attributes of one tag's inside (after its name, before ">"), read in one pass; the
    first of a repeated attribute wins, names are lower-cased, values capped (not unescaped)."""
    out: dict[str, str] = {}
    i, n = 0, len(tag)
    while i < n:
        while i < n and (tag[i] in _SPACE or tag[i] == "/"):
            i += 1
        start = i
        while i < n and tag[i] not in _SPACE and tag[i] not in "=/":
            i += 1
        name = tag[start:i].lower()
        while i < n and tag[i] in _SPACE:
            i += 1
        value = ""
        if i < n and tag[i] == "=":
            i += 1
            while i < n and tag[i] in _SPACE:
                i += 1
            if i < n and tag[i] in "\"'":
                end = tag.find(tag[i], i + 1)
                end = n if end < 0 else end
                value = tag[i + 1:end]
                i = end + 1
            else:
                start = i
                while i < n and tag[i] not in _SPACE:
                    i += 1
                value = tag[start:i]
        elif i == start:
            i += 1  # a stray character: step over it
        if name and name not in out:
            out[name] = value[:ATTR_CAP]
    return out


def _tags(markup: str, lower: str, name: str):
    """The attributes of every <name ...> tag, in order. A tag ends at the next ">" or "<"."""
    opener = "<" + name
    at = lower.find(opener)
    while at >= 0:
        after = at + len(opener)
        if after < len(lower) and (lower[after] in _SPACE or lower[after] in "/>"):
            next_lt = lower.find("<", after)  # the ">" is looked for only up to here, so each
            limit = len(lower) if next_lt < 0 else next_lt  # character is scanned once
            gt = lower.find(">", after, limit)
            end = limit if gt < 0 else gt
            yield _attrs(markup[after:end])
            at = lower.find(opener, end)
        else:
            at = lower.find(opener, after)


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


# Paths a server may read as a different folder than the one that was checked: dot segments (also "..;" and encoded
# dots or slashes, one level of encoding or two, and %u escapes), a ";" path parameter, a backslash, a space or a
# control character. Every alternative is a plain scan: no nested repeats.
_UNSAFE_PATH = re.compile(r"(?:^|/)\.{1,2}(?:[/;]|$)|%(?:2e|2f|5c|00|25|u)|[;\\\x00-\x20\x7f]", re.I)


def canonical(url: str) -> str | None:
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        return None
    netloc = p.netloc.lower()
    if netloc.endswith(":443"):
        netloc = netloc[:-4]  # the same address with and without its default port is one link
    return urlunsplit(("https", netloc, p.path, "", ""))


def eligible(url: str, source) -> str | None:
    """The canonical article address if the source allows it, else None."""
    url = canonical(url)
    if not url:
        return None
    p = urlsplit(url)
    d = source.discovery
    if (p.hostname or "").rstrip(".") not in d["allowed_hosts"]:
        return None
    try:
        port = 443 if p.port is None else p.port
        index_port = 443 if urlsplit(source.url).port is None else urlsplit(source.url).port
    except ValueError:
        return None
    if port != index_port:
        return None  # the same host on another port is another service, not the site that was allowed
    if _UNSAFE_PATH.search(p.path):
        return None  # a path that a server may read as a different folder than the one that was checked
    if not any(p.path.startswith(prefix) for prefix in d["allowed_path_prefixes"]):
        return None
    return url


def _origin(url: str) -> tuple[str, int] | None:
    p = urlsplit(url)
    try:
        port = 443 if p.port is None else p.port
    except ValueError:
        return None
    return (p.hostname or "").lower().rstrip("."), port


def _index_redirects(source):
    """The rule for the index page's own redirects: only to the same host and port (its folder may change)."""
    home = _origin(source.url)

    def rule(target: str) -> None:
        if _origin(target) != home:
            raise _fetch.FetchError("the index page leads to another site; not followed")
    return rule


def _article_redirects(source):
    """The rule for an article's redirects: every hop must itself be an address this source allows (host, port,
    folder, safe path), checked before it is requested, so an escape and a return are refused at the escape."""
    def rule(target: str) -> None:
        try:
            ok = eligible(target, source)
        except ValueError:
            ok = None
        if not ok:
            raise _fetch.FetchError("the article leads outside what this source allows; not followed")
    return rule


def links(markup: str, page_url: str, source) -> list[str]:
    found: list[str] = []
    markup = markup[:MARKUP_CAP * 4]
    for attrs in _tags(markup, markup.lower(), "a"):
        href = attrs.get("href", "").strip()
        if not href:
            continue
        try:
            url = eligible(urljoin(page_url, html.unescape(href)), source)
        except ValueError:
            continue  # a link that cannot be read as an address (such as an unclosed IPv6 bracket) is skipped
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
    meta = next((a.get("content", "") for a in _tags(markup, lower, "meta")
                 if a.get("name", "").strip().lower() == "description" and a.get("content", "").strip()), "")
    if meta:
        desc = strip_html(meta)
    else:
        desc = strip_html(_drop_blocks(markup))
    return title[:TITLE_CAP], desc[:DESC_CAP]


FALLBACK_NOTE = ("the optional article parser (trafilatura) is not installed; articles were read with the built-in "
                 "parser (text only)")


def extract_with_tier(markup: str, source) -> tuple[str, str, str]:
    """(title, text, the tier that read it). A source that asks for trafilatura is read with it when it is installed;
    when it is not, the built-in parser reads the same bytes, and the tier says so."""
    if source.extraction_tier == "native":
        return (*extract(markup), "native")
    from .. import html_extract
    if not html_extract.trafilatura_installed():
        return (*extract(markup), "native")
    return (*html_extract.extract(markup, tier=source.extraction_tier), source.extraction_tier)


def fetch(source, get):
    receipt = new_receipt(source)
    receipt["fetch_tier"] = "native"
    receipt["fetch_tiers"] = {"native": 0, "trafilatura": 0}
    items: list[dict] = []
    try:
        with _fetch.redirect_rules(_index_redirects(source)):
            page = get(source.url, TIMEOUT_S)
        receipt["bytes"] += len(page.body)
        if page.status != 200:
            raise ValueError(f"index page answered HTTP {page.status}")
        candidates = links(page.body.decode("utf-8", "replace"), getattr(page, "url", "") or source.url, source)
        receipt["candidates"] = len(candidates)
        errors = 0
        for url in candidates:
            if len(items) >= source.max_items:
                break
            try:
                with _fetch.redirect_rules(_article_redirects(source)):
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
            final = getattr(resp, "url", "") or url
            if final != url and not eligible(final, source):
                errors += 1  # an article that leads to another host, port or folder is not read
                continue
            title, desc, tier = extract_with_tier(resp.body.decode("utf-8", "replace"), source)
            if not title:
                errors += 1
                continue
            receipt["fetch_tiers"][tier] += 1
            t, dsc, link = clean_text(title), clean_text(desc), clean_url(url)
            receipt["cleaned"] += t.changes + dsc.changes + link.changes
            items.append({"title": t.text, "description": dsc.text, "url": link.text, "published": ""})
        if errors:
            receipt["item_errors"] = errors
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"[:300]
    receipt["items"] = len(items)
    if receipt["fetch_tiers"]["trafilatura"]:
        receipt["fetch_tier"] = "trafilatura"  # the most capable tier any article needed
    if source.extraction_tier != "native" and receipt["fetch_tiers"]["native"]:
        receipt["note"] = "; ".join(x for x in (receipt.get("note"), FALLBACK_NOTE) if x)
    if items:
        receipt["status"] = "ok"
    elif "error" not in receipt:
        receipt["error"] = "no article on the index page could be read"
    return items, receipt
