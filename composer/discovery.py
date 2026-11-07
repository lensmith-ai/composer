"""Find the feeds behind a pasted web address, and propose them. Never pick one.

The page's "Add a source" sends one address. Most people paste a blog's front page, not its feed, so this
module tries, in order:

  1. the address itself, read as a feed;
  2. every RSS or Atom feed the page advertises (<link rel="alternate" type="application/rss+xml" ...>),
     resolved against the page's address;
  3. links on the page that point at a feed or at the site's own RSS page (a footer link such as /rss.cms with the
     text "RSS"): a link that answers as a feed is a candidate; one that answers as a web page is read once, on
     the same site only, and the feeds it lists are tried (Times of India keeps all of its feeds on one such
     page, and lists them with http:// addresses, which are read as https:// on the same site);
  4. only when none of the above gave a feed: a few usual feed addresses under it (/feed/, /feed, /rss/, /rss,
     /rss.xml, /rss.cms, /feeds, /blog/feed/, /blog/rss.xml, /feeds/stories, /feed.xml, /atom.xml, /index.xml),
     and /rss/<the same path> for sites that keep their feeds there.

Each try goes through the same reader a brief uses (composer.adapters, rss-or-atom), so what a person sees here is
what a brief would get. The answer is an ordered list of candidates, each with the newest titles it returned. It
names no "best" one: a site often advertises its whole-site feed and a comments feed next to the blog's own feed,
all three parse, and only a person reading the titles can tell which one they meant. Feeds that look like comment
feeds are marked and listed last; addresses that returned exactly the same items are shown once, on the narrowest
address, with the others listed beside it.

Safety: every request is the guarded fetch in composer.fetch (https only, public addresses only, checked again on
the address actually connected to and after every redirect, no proxies, at most 2 MB a request). The whole check
shares one time limit (TOTAL_S) and makes at most MAX_REQUESTS requests (the page-links preview below has its own,
INDEX_PREVIEW_S and INDEX_PREVIEW_REQUESTS, on top of those). A plain http:// address is tried as
https://; when no https feed answers, the check is refused with PLAIN_HTTP, a sentence the page shows, because a
feed read without encryption can be altered on the way and the claim check would then vouch for the altered text.

When no feed answered at all but the page itself was read, the answer also carries a `page_index` offer: read the
page's own article links instead (an html-index source, composer.adapters.html_index). The offer is built here, from
the address alone: the one host of the page, the page's own folder as the only path prefix, and fixed small limits.
It is shown with the links the reader found and the titles of the first articles it read (through the same reader a
brief uses, on its own small request and time budget), and nothing is saved until a person confirms it; the server
rebuilds the entry from the address again when it is confirmed (composer.sources_registry), so a browser can never
widen it.
"""
from __future__ import annotations

import html
import re
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET

from . import adapters, fetch, registry
from .adapters import html_index, rss_or_atom, thin

URL_MAX_CHARS = 2048
TOTAL_S = 60  # the whole check, every request included
MAX_REQUESTS = 24
MAX_CANDIDATES = 8
SUFFIXES = ("/feed/", "/feed", "/rss/", "/rss", "/rss.xml", "/rss.cms", "/feeds", "/blog/feed/", "/blog/rss.xml",
            "/feeds/stories", "/feed.xml", "/atom.xml", "/index.xml")
PAGE_LINK_TRIES = 4  # links on the page that look like a feed or an RSS page, tried (the first ones in page order)
RSS_PAGES_READ = 2  # of those, answers that were web pages and were read for the feeds they list
RSS_PAGE_FEEDS = 6  # feeds tried from one such page
FOUND_VIA = {"as-pasted": "you pasted it", "advertised": "the page advertises it",
             "suffix": "we guessed this address"}
PLAIN_HTTP = ("This address uses plain http, and Composer reads feeds only over https: a feed read without "
              "encryption can be changed on its way to you, and the claim check would then vouch for the changed "
              "text. No https feed was found at this address; ask the site for an https feed address.")
RULE = ("Addresses that returned the same items are shown once, on the row with the narrowest address; anything "
        "that looks like a comments feed is listed last.")

_LINK_TAG = re.compile(r"<link\b[^<>]*>", re.I)
_ATTR = re.compile(r"""([a-zA-Z-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_COMMENTS = re.compile(r"comment", re.I)
# A link that looks like a feed or a feed list: "rss" in the path, a whole /feed or /feeds segment, atom as a segment
# or an extension. (Not "feedback": the whole segment must be feed or feeds.)
_FEEDISH_PATH = re.compile(r"rss|(?:^|/)feeds?(?:[/.]|$)|(?:^|[/._-])atom(?:[/.]|$)", re.I)
_FEEDISH_TEXT = re.compile(r"^(?:subscribe(?: via| with| to)? )?(?:rss|atom|feeds?|rss feeds?|syndication)\b", re.I)
_TAG_END = " \t\n\r\f/>"
ANCHOR_TEXT_CHARS = 80
_GENERIC_TITLES = {"", "feed", "rss", "rss feed", "atom", "atom feed", "main site feed", "site feed", "blog", "home",
                   "news", "articles", "posts", "all posts", "untitled"}
_GENERIC_LEAD = re.compile(r"^(blog|home|news|feed|articles|posts)\s*[-–—|:·]\s+", re.I)
PAGE_SCAN_CHARS = 512 * 1024  # the part of a page searched for feed links

# The html-index offer: how much it may read, and how long the preview of it may take (on top of the feed check).
INDEX_MAX_CANDIDATES = 10  # links on the page that may be followed
INDEX_MAX_ITEMS = 5  # articles one brief reads
INDEX_PREVIEW_S = 30  # the preview's own time and request limits: they come on top of TOTAL_S and MAX_REQUESTS
INDEX_PREVIEW_REQUESTS = INDEX_MAX_CANDIDATES
_PAGE_FILE = re.compile(r"\.(?:html?|php\d?|aspx?|jsp)$", re.I)  # a last part with one of these is a file, not a folder
INDEX_NO_ROOT = ("This is the front page of the site, so its links are not a list of articles. Paste the address "
                 "of the page that lists them, such as https://example.com/blog.")
_SEGMENT = re.compile(r"[A-Za-z0-9._~!$&'()*+,=:@%-]+")  # no ";" (a path parameter some servers read as a dot segment)
_ENCODED_DOT_OR_SLASH = re.compile(r"%(2e|2f|5c|00|25|u)", re.I)


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


def _anchors(markup: str):
    """(href, text) for every <a href> in the markup, in order, read in one pass (each stretch looked at once). The
    text is what follows the tag up to the next tag, cut short."""
    lower = markup.lower()
    at = lower.find("<a")
    while at >= 0:
        if lower[at + 2:at + 3] not in _TAG_END:
            at = lower.find("<a", at + 2)
            continue
        next_lt = lower.find("<", at + 2)
        limit = len(lower) if next_lt < 0 else next_lt
        gt = lower.find(">", at + 2, limit)
        if gt < 0:
            at = lower.find("<a", limit)
            continue
        href = html_index._attrs(markup[at + 2:gt]).get("href", "").strip()
        end = lower.find("<", gt + 1, gt + 1 + 400)
        text = html.unescape(markup[gt + 1:gt + 1 + 400 if end < 0 else end])
        if href:
            yield html.unescape(href), " ".join(text.split())[:ANCHOR_TEXT_CHARS]
        at = lower.find("<a", gt)


def _same_site_https(href: str, page_url: str) -> str:
    """The absolute https address of a link when it is on the same site as the page, else "". A plain http:// link
    to the same host is read as https:// (Composer reads nothing over plain http); a link to another host, a
    fragment-only link or one with a fragment, and anything that is not http or https are left out."""
    try:
        absolute = urllib.parse.urljoin(page_url, href)
        parts = urllib.parse.urlsplit(absolute)
        parts.port
    except ValueError:
        return ""
    if parts.scheme == "http" and parts.port is None:
        parts = parts._replace(scheme="https")
    if parts.fragment or parts.scheme != "https" or parts.username or parts.password:
        return ""
    address = urllib.parse.urlunsplit(parts)
    return address if thin.same_site(address, page_url) else ""


def page_feed_links(page_url: str, markup: str, *, limit: int) -> list[tuple[str, str]]:
    """[(address, link text)] for the links on a page that look like a feed or a list of feeds, on the same site,
    in page order, the first `limit`. A link that is the page itself is left out; the first text a link had is kept
    (the same address is often linked twice, the second time as an icon with no text)."""
    found: dict[str, str] = {}
    own = page_url.split("#", 1)[0]
    for href, text in _anchors(markup):
        address = _same_site_https(href, page_url)
        if not address or address == own or len(address) > URL_MAX_CHARS:
            continue
        path = urllib.parse.urlsplit(address).path
        if not (_FEEDISH_PATH.search(path) or _FEEDISH_TEXT.match(text)):
            continue
        if address not in found or (not found[address] and text):
            found[address] = text
    return list(found.items())[:limit]


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
            with fetch.redirect_rules(self._hop):  # every redirect hop is a request of its own
                if self.get is fetch.http_get:
                    got = self.get(url, min(timeout, remaining), total_s=remaining)
                else:
                    got = self.get(url, min(timeout, remaining))
        except Exception as exc:
            self.seen[url] = exc
            raise
        self.seen[url] = got
        return got

    def _hop(self, _target: str) -> None:
        if self.clock() >= self.deadline:
            raise fetch.FetchTimeout("the check ran out of time")
        if self.left <= 0:
            raise fetch.FetchError("the check has made as many requests as it may")
        self.left -= 1

    @property
    def spent(self) -> bool:
        return self.left <= 0 or self.clock() >= self.deadline


def _stay_on(address: str):
    """Redirect rule for a fetch of a link found on a page: each hop must stay on that link's own site."""
    def rule(target: str) -> None:
        if not thin.same_site(target, address):
            raise fetch.FetchError("the link leads to another site; not followed")
    return rule


def _try_feed(url: str, origin: str, advertised: str, get: _Budget, via: str = "") -> dict:
    row = {"url": url, "origin": origin, "found_via": via or FOUND_VIA[origin], "advertised_title": advertised,
           "feed_title": "", "suggested_label": "", "ok": False, "items": 0, "titles": [], "bytes": 0, "cleaned": 0, "refusal": "",
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
    shown, own = clean_title(advertised).lower(), row["suggested_label"].lower()
    if via and shown and own != shown and not own.startswith(shown + " "):
        # one site's RSS page lists many feeds that share the site's name: the link's own words tell them apart
        room = max(0, 60 - len(shown) - 3)  # the link's words always fit; the site's name gives way
        row["suggested_label"] = f"{row['suggested_label'][:room].rstrip()} \u00b7 {clean_title(advertised)}"[:60]
    return row


def index_entry(address: object) -> dict:
    """The raw html-index registry entry for reading the article links on one page, built from its address alone.

    The browser never supplies any part of the scope: the allowed host is the page's own host, the only allowed path
    prefix is the page's own folder ("/blog" and "/blog/" both give "/blog/"; a file name such as /blog/index.html
    gives its folder), and the limits are fixed. A DiscoveryError, written for a person, says why an address cannot be
    used: not https, a user:password part, an address on this machine or a private network, a port that is not a
    number, a path with dot segments, encoded slashes or odd characters, or the front page of a site (its links are
    not a list of articles, and a prefix of "/" would allow the whole host)."""
    try:
        value = registry.public_https(address, "that address")
    except registry.RegistryError as exc:
        raise DiscoveryError(str(exc)) from None
    if len(value) > URL_MAX_CHARS:
        raise DiscoveryError(f"that address is longer than {URL_MAX_CHARS} characters")
    parts = urllib.parse.urlsplit(value)
    try:
        parts.port
    except ValueError:
        raise DiscoveryError("that address has a port number that is not valid") from None
    host = (parts.hostname or "").lower().rstrip(".")
    segments = parts.path.split("/")[1:] if parts.path.startswith("/") else []
    ends_in_slash = bool(segments) and segments[-1] == ""
    if ends_in_slash:
        segments.pop()
    for segment in segments:
        if (not segment or segment in (".", "..") or not _SEGMENT.fullmatch(segment)
                or _ENCODED_DOT_OR_SLASH.search(segment)):
            raise DiscoveryError("the path of that address has a part Composer will not use as a folder to read "
                                 "(an empty part, dots, an encoded slash or an unusual character)")
    if segments and not ends_in_slash and _PAGE_FILE.search(segments[-1]):
        segments.pop()  # the address of a page file (index.html): its folder is the scope
    if not segments:
        raise DiscoveryError(INDEX_NO_ROOT)
    page = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
    return {"id": "candidate", "label": "candidate", "kind": "html-index", "url": page, "max_items": INDEX_MAX_ITEMS,
            "discovery": {"allowed_hosts": [host], "allowed_path_prefixes": ["/" + "/".join(segments) + "/"],
                          "max_candidates": INDEX_MAX_CANDIDATES}}


def _origin(url: str) -> tuple[str, int]:
    """(host, port) of an address, for telling whether two addresses are the same site."""
    parts = urllib.parse.urlsplit(url)
    return (parts.hostname or "").lower().rstrip("."), (443 if parts.port is None else parts.port)


def _page_index_offer(url: str, page, get, clock) -> dict:
    """What reading this page's own article links would do, shown before anything is saved. Reads the first articles
    through the same reader a brief uses, with its own small request and time budget (the page is not fetched again)."""
    offer = {"offered": False, "reason": "", "url": url, "allowed_host": "", "allowed_path_prefix": "",
             "max_candidates": INDEX_MAX_CANDIDATES, "max_items": INDEX_MAX_ITEMS, "links": [], "ok": False,
             "items": 0, "articles": [], "suggested_label": "", "refusal": ""}
    if page is None or page.status != 200:
        offer["reason"] = "the page itself could not be read, so there are no article links to follow"
        return offer
    try:
        raw = index_entry(url)
        source = registry.parse_entry(raw)
    except (DiscoveryError, registry.RegistryError) as exc:
        offer["reason"] = str(exc)
        return offer
    host, prefix = raw["discovery"]["allowed_hosts"][0], raw["discovery"]["allowed_path_prefixes"][0]
    offer.update(allowed_host=host, allowed_path_prefix=prefix)
    landed = page.url or url
    try:
        same_site = _origin(landed) == _origin(source.url)
        markup = page.body.decode("utf-8", "replace")
        found = html_index.links(markup, landed, source) if same_site else []
        title = html_index.extract(markup)[0] if found else ""
    except ValueError:
        offer["reason"] = "this page has a link or address that could not be read, so its article links were not used"
        return offer
    if not same_site:
        offer["reason"] = (f"this address leads to another site ({(urllib.parse.urlsplit(landed).netloc or '')[:100]});"
                           " paste that address instead")
        return offer
    if not found:
        offer["reason"] = f"no links to articles were found on this page: no link to {host} under {prefix}"
        return offer
    offer.update(offered=True, links=found, suggested_label=suggest_label("", title, url))
    preview = _Budget(get, INDEX_PREVIEW_S, INDEX_PREVIEW_REQUESTS, clock)
    preview.seen[source.url] = page
    items, receipt = adapters.fetch(source, preview)
    if receipt.get("status") != "ok" or not items:
        offer["refusal"] = str(receipt.get("error") or "the articles could not be read")[:300]
        return offer
    offer.update(ok=True, items=len(items), articles=[{"title": item["title"], "url": item["url"]} for item in items])
    return offer


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
                  "page": {"fetched": False, "refusal": ""}, "candidates": [], "selected": None, "rule": RULE,
                  "page_index": {"offered": False, "reason": "a feed was found"}}
        rows = []
        first = _try_feed(url, "as-pasted", "", budget)
        if first["ok"]:
            rows.append(first)
        body, markup, page_url, page = "", "", url, None
        try:
            page = budget(url, adapters.common.TIMEOUT_S)
            if page.status == 200:
                markup = page.body.decode("utf-8", "replace")  # links in a footer are far down a large page
                body = markup[:PAGE_SCAN_CHARS]  # the head, where feeds are advertised
                page_url = page.url or url
                result["page"]["fetched"] = True
            else:
                result["page"]["refusal"] = f"the page answered HTTP {page.status}"
        except Exception as exc:
            result["page"]["refusal"] = (f"the page could not be read ({str(exc)[:200]}); paste the feed address "
                                         "if you have it")
        seen = {url}

        def room() -> bool:
            return len([r for r in rows if r["ok"]]) < MAX_CANDIDATES and not budget.spent

        # 2. the feeds the page advertises
        for feed_url, title in advertised_feeds(page_url, body):
            if feed_url in seen or not room():
                continue
            seen.add(feed_url)
            rows.append(_try_feed(feed_url, "advertised", title, budget))  # a failed advertised feed is news
        # 3. links on the page to a feed, or to the site's own page that lists its feeds
        pages_read = 0
        for link, text in page_feed_links(page_url, markup, limit=PAGE_LINK_TRIES) if markup else []:
            if link in seen or not room():
                continue
            seen.add(link)
            with fetch.redirect_rules(_stay_on(link)):
                row = _try_feed(link, "advertised", text, budget, via="the site links to it from the page")
            if row["ok"]:
                rows.append(row)
                continue
            got = budget.seen.get(link)
            if pages_read >= RSS_PAGES_READ or isinstance(got, BaseException) or getattr(got, "status", 0) != 200:
                continue
            pages_read += 1  # it answered, but not as a feed: it may be the site's page that lists its feeds
            listed = page_feed_links(got.url or link, got.body.decode("utf-8", "replace"), limit=RSS_PAGE_FEEDS + 8)
            where = urllib.parse.urlsplit(link).path or "/"
            for feed_url, label in [x for x in listed if x[0] not in seen][:RSS_PAGE_FEEDS]:
                if not room():
                    break
                seen.add(feed_url)
                with fetch.redirect_rules(_stay_on(feed_url)):
                    found = _try_feed(feed_url, "advertised", label, budget,
                                      via=f"the site's own RSS page lists it ({where})")
                if found["ok"]:
                    rows.append(found)
        # 4. usual feed addresses, only when the page itself gave no feed
        if not any(r["ok"] for r in rows):
            base = url.split("#", 1)[0].split("?", 1)[0].rstrip("/")
            guesses = [base + suffix for suffix in SUFFIXES]
            parts = urllib.parse.urlsplit(base)
            if parts.path and parts.path != "/":
                guesses.append(f"{parts.scheme}://{parts.netloc}/rss{parts.path}")
            for guess in guesses:
                if guess in seen or not room():
                    continue
                seen.add(guess)
                row = _try_feed(guess, "suffix", "", budget)
                if row["ok"]:  # a failed guess is ours, not news
                    rows.append(row)
        rows.sort(key=lambda r: (r["looks_like_comments"], not r["ok"],
                                 {"as-pasted": 0, "advertised": 1, "suffix": 2}[r["origin"]]))
        result["candidates"] = collapse_duplicates(rows)
        if note and not any(r["ok"] for r in rows):
            # a pasted http:// address with no https feed behind it: say why in words the page shows
            raise DiscoveryError(PLAIN_HTTP)
        if not any(r["ok"] for r in rows):
            # no feed at all: offer the page's own article links (never when a feed answered, never for pasted http)
            result["page_index"] = _page_index_offer(url, page, get, clock)
        if budget.spent and not any(r["ok"] for r in rows) and not result["page_index"]["offered"]:
            result["page"]["refusal"] = result["page"]["refusal"] or "the check ran out of time or requests"
        return result
    finally:
        _one_at_a_time.release()
