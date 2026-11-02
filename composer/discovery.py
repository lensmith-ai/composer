"""Find the feeds behind a pasted web address, and propose them. Never pick one.

The page's "Add a source" sends one address. Most people paste a blog's front page, not its feed, so this
module tries, in order:

  1. the address itself, read as a feed;
  2. every RSS or Atom feed the page advertises (<link rel="alternate" type="application/rss+xml" ...>),
     resolved against the page's address;
  3. a few usual feed addresses under it (/feed/, /feed, /rss/, /rss.xml, /blog/feed/, /blog/rss.xml,
     /feeds/stories, /feed.xml, /atom.xml), and /rss/<the same path> for sites that keep their feeds there.

Each try goes through the same reader a brief uses (composer.adapters, rss-or-atom), so what a person sees here is
what a brief would get. The answer is an ordered list of candidates, each with the newest titles it returned. It
names no "best" one: a site often advertises its whole-site feed and a comments feed next to the blog's own feed,
all three parse, and only a person reading the titles can tell which one they meant. Feeds that look like comment
feeds are marked and listed last; addresses that returned exactly the same items are shown once, on the narrowest
address, with the others listed beside it.

Safety: every request is the guarded fetch in composer.fetch (https only, public addresses only, checked again on
the address actually connected to and after every redirect, no proxies, at most 2 MB a request). The whole check
shares one time limit (TOTAL_S) and makes at most MAX_REQUESTS requests. A plain http:// address is tried as
https://; when no https feed answers, the check is refused with PLAIN_HTTP, a sentence the page shows, because a
feed read without encryption can be altered on the way and the claim check would then vouch for the altered text.
"""
from __future__ import annotations

import html
import re
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET

from . import adapters, fetch, registry
from .adapters import rss_or_atom

URL_MAX_CHARS = 2048
TOTAL_S = 60  # the whole check, every request included
MAX_REQUESTS = 14
MAX_CANDIDATES = 8
SUFFIXES = ("/feed/", "/feed", "/rss/", "/rss.xml", "/blog/feed/", "/blog/rss.xml", "/feeds/stories", "/feed.xml",
            "/atom.xml")
PLAIN_HTTP = ("This address uses plain http, and Composer reads feeds only over https: a feed read without "
              "encryption can be changed on its way to you, and the claim check would then vouch for the changed "
              "text. No https feed was found at this address; ask the site for an https feed address.")
RULE = ("Addresses that returned the same items are shown once, on the row with the narrowest address; anything "
        "that looks like a comments feed is listed last.")

_LINK_TAG = re.compile(r"<link\b[^<>]*>", re.I)
_ATTR = re.compile(r"""([a-zA-Z-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_COMMENTS = re.compile(r"comment", re.I)
_GENERIC_TITLES = {"", "feed", "rss", "rss feed", "atom", "atom feed", "main site feed", "site feed", "blog", "home",
                   "news", "articles", "posts", "all posts", "untitled"}
_GENERIC_LEAD = re.compile(r"^(blog|home|news|feed|articles|posts)\s*[-–—|:·]\s+", re.I)
PAGE_SCAN_CHARS = 512 * 1024  # the part of a page searched for feed links


class DiscoveryError(ValueError):
    """The address cannot be checked at all (the message is written to be shown to a person)."""


class Busy(DiscoveryError):
    """Another address is being checked right now."""


_one_at_a_time = threading.Lock()


def normalise(address: object) -> tuple[str, str]:
    """(https address, note) for what a person pasted, or DiscoveryError saying why it cannot be checked."""
    if not isinstance(address, str) or not address.strip():
        raise DiscoveryError("paste the address of a blog or a feed")
    value = address.strip()
    if len(value) > URL_MAX_CHARS:
        raise DiscoveryError(f"that address is longer than {URL_MAX_CHARS} characters")
    note = ""
    if "://" not in value:
        value = "https://" + value
    scheme = value.split("://", 1)[0].lower()
    if scheme == "http":
        value = "https://" + value.split("://", 1)[1]
        note = "plain http addresses are not fetched; this checked the https address instead"
    elif scheme != "https":
        raise DiscoveryError("only web addresses can be checked; paste the page or feed address")
    try:
        registry.public_https(value, "that address")
    except registry.RegistryError as exc:
        raise DiscoveryError(str(exc)) from None
    return value, note


def clean_title(raw: str) -> str:
    """Whitespace collapsed, entities decoded, a generic lead-in dropped ("Blog - X" -> "X"), at most 60 chars."""
    text = html.unescape(re.sub(r"\s+", " ", str(raw or "")).strip())
    text = _GENERIC_LEAD.sub("", text).strip(" -–—|:·")
    return text[:60].strip()


def suggest_label(feed_title: str, advertised_title: str, url: str) -> str:
    """The name to offer: the feed's own title unless it is generic, then the advertised one, then the host."""
    for candidate in (feed_title, advertised_title):
        cleaned = clean_title(candidate)
        if cleaned and cleaned.lower() not in _GENERIC_TITLES:
            return cleaned
    host = urllib.parse.urlsplit(url).hostname or url
    return host.removeprefix("www.")[:60]


def advertised_feeds(page_url: str, body: str) -> list[tuple[str, str]]:
    """[(absolute url, advertised title)] for every RSS or Atom <link rel="alternate"> on the page."""
    out = []
    for tag in _LINK_TAG.findall(body[:PAGE_SCAN_CHARS]):
        attrs = {m.group(1).lower(): (m.group(2) if m.group(2) is not None else m.group(3) or "")
                 for m in _ATTR.finditer(tag)}
        if "alternate" not in attrs.get("rel", "").lower().split():
            continue
        kind = attrs.get("type", "").lower()
        href = html.unescape(attrs.get("href", "").strip())
        if not href or ("rss" not in kind and "atom" not in kind):
            continue
        out.append((urllib.parse.urljoin(page_url, href), html.unescape(attrs.get("title", "").strip())))
    return out


def feed_title(raw: bytes) -> str:
    """The feed's own <title> (the channel's, or the Atom feed's), cleaned; "" when there is none."""
    try:
        rss_or_atom._refuse_entities(raw)
        root = ET.fromstring(raw)
    except Exception:
        return ""
    for el in root.iter():
        name = rss_or_atom._local(el.tag)
        if name in rss_or_atom.ITEM_TAGS:
            return ""  # an item came first: the feed has no title of its own
        if name == "title" and (el.text or "").strip():
            return clean_title(el.text)
    return ""


def _depth(url: str) -> int:
    return len([part for part in urllib.parse.urlsplit(url).path.split("/") if part])


def collapse_duplicates(rows: list[dict]) -> list[dict]:
    """One row per set of identical items: the deepest path (a narrower feed), then the shortest spelling of it;
    the other addresses are kept on that row as `same_as`. Order is otherwise kept."""
    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    singles = []
    for row in rows:
        if not row["ok"]:
            singles.append(row)
            continue
        key = tuple(row["titles"])
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)
    out = []
    for key in order:
        members = groups[key]
        keep = min(members, key=lambda r: (-_depth(r["url"]), len(r["url"])))
        keep["same_as"] = [r["url"] for r in members if r is not keep]
        out.append(keep)
    return out + singles


class _Budget:
    """One time limit and one request count for the whole check; answers are kept so no address is fetched twice."""

    def __init__(self, get, total_s: float, max_requests: int, clock=time.monotonic):
        self.get = get
        self.clock = clock
        self.deadline = clock() + total_s
        self.left = max_requests
        self.seen: dict[str, object] = {}

    def __call__(self, url: str, timeout: float):
        if url in self.seen:
            got = self.seen[url]
            if isinstance(got, BaseException):
                raise got
            return got
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise fetch.FetchTimeout("the check ran out of time")
        if self.left <= 0:
            raise fetch.FetchError("the check has made as many requests as it may")
        self.left -= 1
        try:
            if self.get is fetch.http_get:
                got = self.get(url, min(timeout, remaining), total_s=remaining)
            else:
                got = self.get(url, min(timeout, remaining))
        except Exception as exc:
            self.seen[url] = exc
            raise
        self.seen[url] = got
        return got

    @property
    def spent(self) -> bool:
        return self.left <= 0 or self.clock() >= self.deadline


def _try_feed(url: str, origin: str, advertised: str, get: _Budget) -> dict:
    row = {"url": url, "origin": origin, "advertised_title": advertised, "feed_title": "", "suggested_label": "",
           "ok": False, "items": 0, "titles": [], "bytes": 0, "cleaned": 0, "refusal": "",
           "looks_like_comments": bool(_COMMENTS.search(url) or _COMMENTS.search(advertised)), "same_as": []}
    try:
        entry = registry.parse_entry({"id": "candidate", "label": "candidate", "kind": "rss-or-atom", "url": url,
                                      "max_items": 5})
    except registry.RegistryError as exc:
        row["refusal"] = f"this address cannot be a source: {str(exc).removeprefix('candidate: ')}"
        return row
    items, receipt = adapters.fetch(entry, get)
    row["bytes"], row["cleaned"] = receipt.get("bytes", 0), receipt.get("cleaned", 0)
    if receipt.get("status") != "ok" or not items:
        row["refusal"] = str(receipt.get("error") or "fetched, but no items could be read from it")[:300]
        return row
    row.update(ok=True, items=len(items), titles=[item["title"] for item in items])
    got = get.seen.get(url)
    row["feed_title"] = feed_title(got.body) if hasattr(got, "body") else ""
    row["suggested_label"] = suggest_label(row["feed_title"], advertised, url)
    return row


def discover(address: object, *, get=fetch.http_get, total_s: float = TOTAL_S,
             max_requests: int = MAX_REQUESTS, clock=time.monotonic) -> dict:
    """{"input", "checked", "note", "page": {"fetched", "refusal"}, "candidates": [...], "selected": None, "rule"}.

    Raises DiscoveryError when the address cannot be checked at all, Busy when another check is running."""
    url, note = normalise(address)
    if not _one_at_a_time.acquire(blocking=False):
        raise Busy("another address is being checked right now; try again in a moment")
    try:
        budget = _Budget(get, total_s, max_requests, clock)
        result = {"input": address.strip(), "checked": url, "note": note,
                  "page": {"fetched": False, "refusal": ""}, "candidates": [], "selected": None, "rule": RULE}
        rows = []
        first = _try_feed(url, "as-pasted", "", budget)
        if first["ok"]:
            rows.append(first)
        body, page_url = "", url
        try:
            page = budget(url, adapters.common.TIMEOUT_S)
            if page.status == 200:
                body = page.body[:PAGE_SCAN_CHARS].decode("utf-8", "replace")
                page_url = page.url or url
                result["page"]["fetched"] = True
            else:
                result["page"]["refusal"] = f"the page answered HTTP {page.status}"
        except Exception as exc:
            result["page"]["refusal"] = (f"the page could not be read ({str(exc)[:200]}); paste the feed address "
                                         "if you have it")
        tries, seen = [], {url}
        for feed_url, title in advertised_feeds(page_url, body):
            if feed_url not in seen:
                seen.add(feed_url)
                tries.append((feed_url, "advertised", title))
        base = url.split("#", 1)[0].split("?", 1)[0].rstrip("/")
        guesses = [base + suffix for suffix in SUFFIXES]
        parts = urllib.parse.urlsplit(base)
        if parts.path and parts.path != "/":
            guesses.append(f"{parts.scheme}://{parts.netloc}/rss{parts.path}")
        for guess in guesses:
            if guess not in seen:
                seen.add(guess)
                tries.append((guess, "suffix", ""))
        for feed_url, origin, title in tries:
            if len([r for r in rows if r["ok"]]) >= MAX_CANDIDATES or budget.spent:
                break
            row = _try_feed(feed_url, origin, title, budget)
            if row["ok"] or origin == "advertised":  # a failed guess is ours; a failed advertised feed is news
                rows.append(row)
        rows.sort(key=lambda r: (r["looks_like_comments"], not r["ok"],
                                 {"as-pasted": 0, "advertised": 1, "suffix": 2}[r["origin"]]))
        result["candidates"] = collapse_duplicates(rows)
        if note and not any(r["ok"] for r in rows):
            # a pasted http:// address with no https feed behind it: say why in words the page shows
            raise DiscoveryError(PLAIN_HTTP)
        if budget.spent and not any(r["ok"] for r in rows):
            result["page"]["refusal"] = result["page"]["refusal"] or "the check ran out of time or requests"
        return result
    finally:
        _one_at_a_time.release()
