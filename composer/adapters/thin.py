"""Thin feed items: an entry with no real text is read from its own page, or left out. Never narrated as news.

Some feeds publish entries before they are written: the description is empty, or says "TBD", "coming soon" or
Lorem ipsum, or only repeats the title. A brief written from that text ends up reporting the filler ("its
description reads TBD") as if it were the story. So before the writer sees a feed's items, each one is classed:

  ok           real text (at least MIN_WORDS meaningful words, not filler, not the title again)
  short        FLOOR_WORDS to MIN_WORDS words: real, but little
  fragment     fewer than FLOOR_WORDS words ("Four.", "Coming this fall."): it cannot stand alone
  title-only   the description repeats the title's words and adds nothing
  filler       TBD, TBA, coming soon, read more, Lorem ipsum and the like
  empty        nothing but markup, punctuation or an ellipsis

An item that is not `ok` is read from its own page (the address in the feed), the way an html-index source reads an
article, and the page's article text replaces the description. If the page cannot be read, or has no article text
either, the item is DROPPED and the receipt records why. The one exception is a `short` description: it is real text,
so it is kept when the page cannot be read (dropping it would lose a true, if brief, report).

What the page read may do (it is a request a feed asked for, so it is held tighter than a person's own click):
  - https only, public addresses only (the guarded fetch in composer.fetch), no proxy, at most 2 MB, one time limit;
  - the page must be on the SAME SITE as the feed (same host and port, "www." ignored); a link to anywhere else is
    not followed, and neither is a redirect hop to anywhere else, each hop checked before it is requested;
  - at most MAX_REQUESTS requests (redirect hops included) and TOTAL_S seconds for one source, and the first
    timeout stops the site being asked again; the rest of its thin items are dropped with that reason.
"""
from __future__ import annotations

import re
import time
import unicodedata
import urllib.parse

from .. import fetch as _fetch
from ..sanitize import clean_text
from .common import DESC_CAP, TIMEOUT_S

MIN_WORDS = 10  # fewer meaningful words than this is "thin"
FLOOR_WORDS = 5  # fewer than this cannot stand alone
EXTRA_ENTRIES = 5  # entries read past max_items, to replace the ones that are dropped
MAX_REQUESTS = 10  # page requests (redirect hops included) for one source
TOTAL_S = 45  # one source's page reads, in all
DROPPED_LISTED = 20  # dropped items named in a receipt

_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]")
_UNSPACED = re.compile("[\u0e00-\u0eff\u1000-\u109f\u1780-\u17ff]")  # Thai, Lao, Myanmar, Khmer: no spaces
_NOT_ALNUM = re.compile(r"[^\w]+")
_LOREM = re.compile(r"\blorem ipsum\b|\bdolor sit amet\b", re.I)
# A feed generator's tail on an excerpt ("The post X appeared first on Y", "[...]", "Read more »"). The "read more"
# kinds are removed only as the last words of a sentence or of the whole text, never from the middle of prose
# ("people who read more books live longer" is left alone).
_BOILERPLATE = re.compile(
    r"the post .{0,300}? appeared first on .{0,120}|\[(?:\u2026|\.{2,3}|&#8230;)\]|"
    r"(?:^|(?<=[.!?\u2026\]\u00bb)]))\s*(?:(?:read|continue reading|learn) more|continue reading|click here)"
    r"\b[^.]{0,40}$",
    re.I | re.S)
_FILLER = re.compile(
    r"(?:tbd|tba|tbc|tbs|n a|na|none|null|nil|undefined|nan|empty|blank|test|testing|todo|to do|xxx+|x|"
    r"placeholder(?: text)?|"  # vnf-allow: the word a feed uses, detection vocabulary
    r"(?:no|default|sample|short|summary|enter|add|insert|your|article|post|item|feed)? ?"
    r"(?:description|summary|excerpt|text|content|blurb)(?: goes here| here| available| tbd| tba| coming soon)?|"
    r"coming soon|more to come|stay tuned|watch this space|details (?:soon|to follow)|"
    r"to be (?:announced|determined|confirmed|added|decided|written|updated)|"
    r"read more|click here|learn more|more|continue reading|untitled|update soon|more soon)")


_SPELLED_OUT = {"tbd", "tba", "tbc", "tbs", "na"}


def _wordlike(ch: str) -> bool:
    """A letter, a digit, or a combining mark (a vowel sign belongs to its word)."""
    return ch.isalnum() or unicodedata.category(ch).startswith("M")


def _trim(token: str) -> str:
    """The token without the punctuation at either end, by two scans (a regex for this is quadratic on a token with
    punctuation inside it)."""
    start, end = 0, len(token)
    while start < end and not _wordlike(token[start]):
        start += 1
    while end > start and not _wordlike(token[end - 1]):
        end -= 1
    return token[start:end]


def _tokens(text: str) -> list[str]:
    """Words as written: split on spaces, punctuation trimmed off the ends, tokens with no letter or digit left out.
    Not split inside a word, so a Hindi word keeps its vowel signs and Russian one-letter words stay."""
    out = []
    for raw in (text or "").split():
        token = _trim(raw)
        if any(ch.isalnum() for ch in token):
            out.append(token)
    return out


def word_count(text: str) -> int:
    """Meaningful words. A run of Chinese, Japanese or Korean characters counts one word for every two characters,
    and Thai, Lao, Myanmar or Khmer text one for every four, since those are not written with spaces; any other
    token is one word. A lone letter counts, so "T.B.D." is one token, not three."""
    count = 0
    for token in _tokens(text):
        if _CJK.search(token):
            count += max(1, len(token) // 2)
        elif _UNSPACED.search(token):
            count += max(1, len(token) // 4)
        elif len(token) >= 2 or token.isdigit() or ord(token) > 127:
            count += 1  # a lone ASCII letter ("a", "x") is not a word here; a lone Cyrillic or Greek one is
    return count


def _normal(text: str) -> str:
    return _NOT_ALNUM.sub(" ", (text or "").lower()).strip()


def classify(title: str, description: str) -> str:
    """ok, short, fragment, title-only, filler or empty (see the module's note)."""
    text = _BOILERPLATE.sub(" ", description or "")
    if not _tokens(text):
        return "empty"
    flat = _normal(text)
    if _LOREM.search(text) or _FILLER.fullmatch(flat) or flat.replace(" ", "") in _SPELLED_OUT:
        return "filler"  # "T.B.D." reads as "t b d"
    seen = {t.lower() for t in _tokens(title)}
    if not [t for t in _tokens(text) if t.lower() not in seen]:
        return "title-only"
    words = word_count(text)
    if words < FLOOR_WORDS:
        return "fragment"
    return "short" if words < MIN_WORDS else "ok"


def _host(name: str | None) -> str:
    host = (name or "").lower().rstrip(".")
    return host.removeprefix("www.")


def same_site(a: str, b: str) -> bool:
    """True when both addresses are https on the same host and port ("www." and a trailing dot ignored)."""
    try:
        pa, pb = urllib.parse.urlsplit(a), urllib.parse.urlsplit(b)
        host_a, host_b = _host(pa.hostname), _host(pb.hostname)
        port_a = 443 if pa.port is None else pa.port
        port_b = 443 if pb.port is None else pb.port
    except ValueError:
        return False
    return (pa.scheme == "https" and pb.scheme == "https" and bool(host_a) and host_a == host_b
            and port_a == port_b and pa.username is None and pb.username is None
            and pa.password is None and pb.password is None)


def page_address(link: str, feed_url: str) -> tuple[str, str]:
    """(address, "") to read for an item, or ("", why not): https, no user:password, on the feed's own site; the
    fragment is dropped, the query kept (some sites identify the article by it)."""
    link = (link or "").strip()
    if not link:
        return "", "the item has no link to its page"
    try:
        parts = urllib.parse.urlsplit(link)
        parts.port
    except ValueError:
        return "", "the item's link is not a valid address"
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        return "", "the item's link is not an https address"
    address = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
    if not same_site(address, feed_url):
        return "", "the item's page is on another site than the feed"
    return address, ""


class _Pages:
    """One source's page reads: a request count (hops included), one time limit, and the first timeout stops it."""

    def __init__(self, get, clock):
        self.get, self.clock = get, clock
        self.deadline = clock() + TOTAL_S
        self.requests = 0
        self.stopped = ""

    def read(self, address: str):
        """The Response for an item's page, or raise FetchError/FetchTimeout."""
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            self.stopped = "the pages for this source ran out of time"
            raise _fetch.FetchTimeout(self.stopped)
        if self.requests >= MAX_REQUESTS:
            self.stopped = "the limit on page requests for this source was reached"
            raise _fetch.FetchError(self.stopped)
        self.requests += 1

        def hop(target: str) -> None:  # a redirect is a request of its own, and must stay on the item's site
            if not same_site(target, address):
                raise _fetch.FetchError("the item's page leads to another site; not followed")
            if self.requests >= MAX_REQUESTS:
                raise _fetch.FetchError("the limit on page requests for this source was reached")
            self.requests += 1
        try:
            with _fetch.redirect_rules(hop):
                if self.get is _fetch.http_get:
                    return self.get(address, min(TIMEOUT_S, remaining), total_s=remaining)
                return self.get(address, min(TIMEOUT_S, remaining))
        except TimeoutError:
            self.stopped = "a page timed out; this site was not asked again"
            raise


def page_text(address: str, title: str, source, pages: _Pages) -> tuple[str, str, int]:
    """(article text, "", bytes) from the item's page, or ("", why not, bytes)."""
    from .. import html_extract
    try:
        resp = pages.read(address)
    except _fetch.FetchError as exc:
        return "", f"its page could not be read ({clean_text(str(exc)[:120]).text})", 0
    except Exception as exc:  # a failing page is a reason, never an exception
        return "", f"its page could not be read ({type(exc).__name__})", 0
    body = getattr(resp, "body", b"") or b""
    if resp.status != 200:
        return "", f"its page answered HTTP {resp.status}", len(body)
    final = getattr(resp, "url", "") or address
    if final != address and not same_site(final, address):
        return "", "its page led to another site", len(body)
    if b"\x00" in body[:2048]:
        return "", "its page is not text", len(body)
    _title, text = html_extract.article_text(body.decode("utf-8", "replace"), tier=source.extraction_tier)
    if classify(title, text) in ("ok", "short"):
        return text, "", len(body)
    return "", "its page had no readable article text", len(body)


def refine(items: list[dict], source, get, receipt: dict, *, max_items: int, clock=time.monotonic) -> list[dict]:
    """The feed's items with thin ones read from their pages or dropped; at most `max_items` come back.

    `items` may hold a few entries past max_items (they replace dropped ones). The receipt gets a `thin` note:
    how many were thin, how many pages were read, how many were filled in, and each dropped item with its reason."""
    pages = _Pages(get, clock)
    note = {"thin": 0, "page_requests": 0, "enriched": 0, "kept_short": 0, "dropped": []}
    kept: list[dict] = []
    for position, item in enumerate(items, 1):
        if len(kept) >= max_items:
            break
        kind = classify(item["title"], item["description"])
        if kind == "ok":
            kept.append(item)
            continue
        note["thin"] += 1
        if pages.stopped:
            why = pages.stopped
        else:
            address, why = page_address(item["url"], source.url)
            if address:
                text, why, size = page_text(address, item["title"], source, pages)
                receipt["bytes"] += size
                if text:
                    found = clean_text(text[:DESC_CAP])
                    receipt["cleaned"] += found.changes
                    kept.append({**item, "description": found.text})
                    note["enriched"] += 1
                    continue
        if kind == "short":  # real words, only few: kept as they are
            kept.append(item)
            note["kept_short"] += 1
            continue
        if len(note["dropped"]) < DROPPED_LISTED:
            note["dropped"].append({"position": position, "title": item["title"][:80],
                                    "reason": f"{kind} description; {why}"})
    note["page_requests"] = pages.requests
    note["dropped_count"] = note["thin"] - note["enriched"] - note["kept_short"]
    receipt["thin"] = note
    return kept
