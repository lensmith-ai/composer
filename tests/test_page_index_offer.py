"""A page with no feed: "Add a source" offers to read the page's own article links (an html-index source).

Offline: every fetch is answered from a table of recorded pages (tests/fixtures/blog-nofeed-*.html), and the table
records every address asked for, so each refusal is shown by what was NOT requested.

The shape of the page is that of a site with no feed and a blog folder: no <link rel="alternate">, every usual feed
address answers 404, and the blog index links its posts with relative addresses ("./blog/<post>") beside navigation,
other hosts, plain http, credentials, another port, dot segments and a lookalike folder."""
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from composer import adapters, discovery, lenses, registry, server, sources_registry
from composer.adapters import html_index
from composer.fetch import Response
from composer.registry import BUNDLED

from helpers import fixture

BLOG = "https://ledgerlight.example/blog"
POSTS = {
    "https://ledgerlight.example/blog/latency-per-decision": "blog-post-latency.html",
    "https://ledgerlight.example/blog/small-models-big-ledgers": "blog-post-small-models.html",
    "https://ledgerlight.example/blog/reading-the-fine-print": "blog-post-fine-print.html",
    "https://ledgerlight.example/blog/shipping-the-audit-log": "blog-post-audit-log.html",
}
EXPECTED_LINKS = list(POSTS)
NEVER_ASKED = (
    "http://ledgerlight.example/blog/plain-http-post",
    "https://elsewhere.example.net/blog/not-our-site",
    "https://ledgerlight.example/blog/with-credentials",
    "https://ledgerlight.example/blog/other-port",
    "https://ledgerlight.example:8443/blog/other-port",
    "https://ledgerlight.example/enterprise",
    "https://ledgerlight.example/enterprise/pricing",
    "https://ledgerlight.example/blogging/not-the-folder",
    "https://ledgerlight.example/blog/%2e%2e/enterprise/secret",
    "https://ledgerlight.example/enterprise/secret",
    "https://ledgerlight.example/blog/slash%2Fin-name",
    "https://ledgerlight.example/contact",
    "https://ledgerlight.example/legal/terms",
    "https://docs.ledgerlight.example/introduction",
)


class TableGet:
    """get(url, timeout): the table's answer, 404 for anything else; records every call. A tuple is (status, body),
    or (status, body, final address) for an answer that was reached through a redirect."""

    def __init__(self, table):
        self.table = table
        self.calls = []

    def __call__(self, url, timeout):
        self.calls.append(url)
        value = self.table.get(url, (404, b"not here"))
        if isinstance(value, BaseException):
            raise value
        if isinstance(value, tuple):
            return Response(value[2] if len(value) > 2 else url, value[0], value[1])
        return Response(url, 200, value)


def blog_site(**extra):
    table = {BLOG: fixture("blog-nofeed-index.html")}
    table.update({url: fixture(name) for url, name in POSTS.items()})
    table.update(extra)
    return TableGet(table)


class IndexEntryTests(unittest.TestCase):
    """The scope is built from the address alone."""

    def scope(self, address):
        raw = discovery.index_entry(address)
        d = raw["discovery"]
        registry.parse_entry(raw)  # always a valid registry entry
        return d["allowed_hosts"], d["allowed_path_prefixes"], d["max_candidates"], raw["max_items"], raw["url"]

    def test_the_host_is_the_pages_host_and_the_prefix_is_its_folder(self):
        for address in (BLOG, BLOG + "/", BLOG + "/index.html", "https://LedgerLight.Example:443/blog",
                        BLOG + "#latest"):
            with self.subTest(address=address):
                hosts, prefixes, candidates, items, _ = self.scope(address)
                self.assertEqual((hosts, prefixes), (["ledgerlight.example"], ["/blog/"]))
                self.assertEqual((candidates, items), (10, 5))
        self.assertEqual(self.scope("https://ledgerlight.example/notes/2026/")[1], ["/notes/2026/"])
        self.assertEqual(self.scope(BLOG + "?page=1#x")[4], BLOG + "?page=1")  # no fragment is kept

    def test_only_a_page_file_name_is_dropped_a_dotted_folder_stays_the_scope(self):
        self.assertEqual(self.scope("https://ledgerlight.example/docs/api.v2")[1], ["/docs/api.v2/"])
        self.assertEqual(self.scope("https://ledgerlight.example/blog/2024.11")[1], ["/blog/2024.11/"])
        for page in ("index.html", "index.htm", "default.aspx", "index.php", "INDEX.HTML"):
            self.assertEqual(self.scope(f"https://ledgerlight.example/blog/{page}")[1], ["/blog/"], page)

    def test_a_host_spelled_with_a_trailing_dot_is_the_same_host(self):
        self.assertEqual(self.scope("https://ledgerlight.example./blog")[0], ["ledgerlight.example"])

    def test_the_front_page_is_refused_because_a_prefix_of_slash_would_allow_the_whole_host(self):
        for address in ("https://ledgerlight.example", "https://ledgerlight.example/",
                        "https://ledgerlight.example/index.html", "https://ledgerlight.example/?x=1"):
            with self.subTest(address=address):
                with self.assertRaises(discovery.DiscoveryError) as cm:
                    discovery.index_entry(address)
                self.assertIn("front page", str(cm.exception))

    def test_unsafe_addresses_are_refused(self):
        for address in ("http://ledgerlight.example/blog", "https://user:pw@ledgerlight.example/blog",
                        "https://127.0.0.1/blog", "https://localhost/blog", "https://10.0.0.5/blog",
                        "https://[::1]/blog", "https://ledgerlight.example:99999/blog",
                        "https://ledgerlight.example:abc/blog", "ftp://ledgerlight.example/blog", "",
                        "https://" + "a" * 2050, None, 5):
            with self.subTest(address=address):
                with self.assertRaises(discovery.DiscoveryError):
                    discovery.index_entry(address)

    def test_a_path_that_could_name_a_folder_outside_the_prefix_is_refused(self):
        for path in ("/blog/../enterprise", "/blog/./x", "/blog//x", "/blog/%2e%2e/enterprise", "/blog/%2E%2E/x",
                     "/blog/..%2fenterprise", "/blog/x%2Fy", "/blog/x%5Cy", "/blog/x%00", "/blog\\x",
                     "/blog/..;/admin", "/blog/x;jsessionid=1", "/blog/%252e%252e/x", "/blog/%u002e%u002e/x",
                     "/blog/café", "/blog/a b"):
            with self.subTest(path=path):
                with self.assertRaises(discovery.DiscoveryError):
                    discovery.index_entry("https://ledgerlight.example" + path)


class EligibleTests(unittest.TestCase):
    """The reader's own link rule, which the offer relies on (a tighter rule than the page's host and prefix alone)."""

    def eligible(self, url):
        source = registry.parse_entry({**discovery.index_entry(BLOG), "id": "x", "label": "x"})
        return html_index.eligible(url, source)

    def test_a_page_on_its_own_port_follows_only_that_port(self):
        raw = discovery.index_entry("https://ledgerlight.example:8443/blog")
        self.assertEqual(raw["url"], "https://ledgerlight.example:8443/blog")
        source = registry.parse_entry({**raw, "id": "x", "label": "x"})
        self.assertEqual(html_index.eligible("https://ledgerlight.example:8443/blog/a", source),
                         "https://ledgerlight.example:8443/blog/a")
        for url in ("https://ledgerlight.example/blog/a", "https://ledgerlight.example:443/blog/a",
                    "https://ledgerlight.example:9443/blog/a"):
            self.assertIsNone(html_index.eligible(url, source), url)

    def test_same_host_other_port_and_unsafe_paths_are_not_followed(self):
        good = "https://ledgerlight.example/blog/a-post"
        self.assertEqual(self.eligible(good), good)
        self.assertEqual(self.eligible("https://ledgerlight.example:443/blog/a-post"), good)  # the default port is implied
        for url in ("https://ledgerlight.example:8443/blog/a-post", "https://ledgerlight.example:80/blog/a-post",
                    "https://ledgerlight.example:99999/blog/a-post", "http://ledgerlight.example/blog/a-post",
                    "https://u:p@ledgerlight.example/blog/a-post", "https://other.example/blog/a-post",
                    "https://ledgerlight.example/blogging/a-post", "https://ledgerlight.example/blog",
                    "https://ledgerlight.example/blog/../enterprise", "https://ledgerlight.example/blog/%2e%2e/x",
                    "https://ledgerlight.example/blog/%2E%2e/x", "https://ledgerlight.example/blog/a%2fb",
                    "https://ledgerlight.example/blog/a%5cb", "https://ledgerlight.example/blog/a/./b",
                    "https://ledgerlight.example/blog/a/..", "https://ledgerlight.example/blog/..;/admin",
                    "https://ledgerlight.example/blog/x/..;/..;/admin", "https://ledgerlight.example/blog/a;b",
                    "https://ledgerlight.example/blog/%252e%252e/admin", "https://ledgerlight.example/blog/%u002e%u002e/a",
                    "https://ledgerlight.example/blog/a b", "https://ledgerlight.example/blog/a\\b",
                    "https://ledgerlight.example/blog/a%00b", "https://ledgerlight.example/blog/a\x01b",
                    "https://ledgerlight.example/blog/a\x7fb", "https://ledgerlight.example:0/blog/a-post"):
            with self.subTest(url=url):
                self.assertIsNone(self.eligible(url))

    def test_a_trailing_dot_host_and_the_default_port_are_the_same_site_and_one_link(self):
        self.assertEqual(self.eligible("https://ledgerlight.example./blog/a"), "https://ledgerlight.example./blog/a")
        source = registry.parse_entry({**discovery.index_entry(BLOG), "id": "x", "label": "x"})
        page = ('<a href="/blog/a">A</a><a href="https://ledgerlight.example:443/blog/a">A</a>'
                '<a href="https://LEDGERLIGHT.example/blog/a">A</a><a href="/blog/b">B</a>')
        self.assertEqual(html_index.links(page, BLOG, source),
                         ["https://ledgerlight.example/blog/a", "https://ledgerlight.example/blog/b"])

    def test_a_link_that_cannot_be_read_as_an_address_is_skipped_not_fatal(self):
        source = registry.parse_entry({**discovery.index_entry(BLOG), "id": "x", "label": "x"})
        page = ('<a href="//[::1">bad</a><a href="https://[abc/blog/x">bad</a><a href="/blog/ok">ok</a>')
        self.assertEqual(html_index.links(page, BLOG, source), ["https://ledgerlight.example/blog/ok"])

    def test_an_article_that_leads_to_another_host_port_or_folder_is_not_read(self):
        source = registry.parse_entry({**discovery.index_entry(BLOG), "id": "x", "label": "x"})
        a, b, c = (f"https://ledgerlight.example/blog/{n}" for n in "abc")
        page = f'<a href="{a}">a</a><a href="{b}">b</a><a href="{c}">c</a>'
        table = {BLOG: page.encode(),
                 a: (200, b"<title>A</title>", "https://elsewhere.example.net/blog/a"),
                 b: (200, b"<title>B</title>", "https://ledgerlight.example/enterprise/b"),
                 c: (200, b"<title>C</title>", "https://ledgerlight.example/blog/c/")}
        items, receipt = html_index.fetch(source, TableGet(table))
        self.assertEqual([i["title"] for i in items], ["C"])  # a redirect inside the folder is fine
        self.assertEqual(receipt["item_errors"], 2)


class OfferTests(unittest.TestCase):
    def test_a_page_with_no_feed_is_offered_as_its_own_article_links_and_none_is_chosen(self):
        get = blog_site()
        result = discovery.discover(BLOG, get=get)
        self.assertEqual(result["candidates"], [])
        self.assertIsNone(result["selected"])
        offer = result["page_index"]
        self.assertTrue(offer["offered"])
        self.assertTrue(offer["ok"])
        self.assertEqual((offer["allowed_host"], offer["allowed_path_prefix"]), ("ledgerlight.example", "/blog/"))
        self.assertEqual((offer["max_candidates"], offer["max_items"]), (10, 5))
        self.assertEqual(offer["url"], BLOG)
        # the links the reader found: this host, under /blog/, https, no credentials, each once, in page order
        self.assertEqual(offer["links"], EXPECTED_LINKS)
        # what a brief would read, as titles, newest first as the page lists them
        self.assertEqual([a["title"] for a in offer["articles"]],
                         ["Latency per decision - Ledgerlight Labs", "Small models, big ledgers - Ledgerlight Labs",
                          "Reading the fine print - Ledgerlight Labs", "Shipping the audit log - Ledgerlight Labs"])
        self.assertEqual([a["url"] for a in offer["articles"]], EXPECTED_LINKS)
        self.assertEqual(offer["suggested_label"], "Notes | Ledgerlight Labs")
        # the page was fetched once (as a feed, as a page and for the preview), and nothing else was asked for
        self.assertEqual(get.calls.count(BLOG), 1)
        for url in NEVER_ASKED:
            self.assertNotIn(url, get.calls)
        self.assertTrue(all(url.startswith("https://ledgerlight.example/") for url in get.calls), get.calls)

    def test_the_offer_reads_through_the_same_reader_a_brief_uses(self):
        get = blog_site()
        offer = discovery.discover(BLOG, get=get)["page_index"]
        source = registry.parse_entry({**discovery.index_entry(BLOG), "id": "ledgerlight", "label": "Ledgerlight"})
        items, receipt = adapters.fetch(source, blog_site())
        self.assertEqual([i["title"] for i in items], [a["title"] for a in offer["articles"]])
        self.assertEqual(receipt["status"], "ok")

    def test_the_preview_has_its_own_small_request_budget(self):
        many = "".join(f'<a href="/blog/post-{n}">Post {n}</a>' for n in range(40))
        table = {BLOG: f"<html><head><title>Notes</title></head><body>{many}</body></html>".encode()}
        get = TableGet(table)  # every post answers 404
        result = discovery.discover(BLOG, get=get)
        offer = result["page_index"]
        self.assertTrue(offer["offered"])
        self.assertFalse(offer["ok"])
        self.assertEqual(len(offer["links"]), discovery.INDEX_MAX_CANDIDATES)
        self.assertTrue(offer["refusal"])
        posts = [url for url in get.calls if "/blog/post-" in url]
        self.assertLessEqual(len(posts), discovery.INDEX_MAX_CANDIDATES)
        self.assertLessEqual(len(get.calls), discovery.MAX_REQUESTS + discovery.INDEX_MAX_CANDIDATES)

    def test_the_preview_stops_at_its_own_request_limit_and_its_own_time_limit(self):
        from unittest import mock
        get = TableGet({BLOG: fixture("blog-nofeed-index.html"), **{u: fixture(n) for u, n in POSTS.items()}})
        with mock.patch.object(discovery, "INDEX_PREVIEW_REQUESTS", 2):
            offer = discovery.discover(BLOG, get=get)["page_index"]
        self.assertEqual(len([u for u in get.calls if u in POSTS]), 2)
        self.assertEqual(len(offer["articles"]), 2)
        # time: the clock jumps past the preview's limit while the first article is read, so no other is asked for
        get = TableGet({BLOG: fixture("blog-nofeed-index.html"), **{u: fixture(n) for u, n in POSTS.items()}})
        now = {"t": 0.0}

        def clock():
            return now["t"]

        class Jumping(TableGet):
            def __call__(self, url, timeout):
                got = super().__call__(url, timeout)
                if url in POSTS:
                    now["t"] += discovery.INDEX_PREVIEW_S + 1  # one article took longer than the preview may
                return got
        slow = Jumping(get.table)
        offer = discovery.discover(BLOG, get=slow, clock=clock, total_s=10000)["page_index"]
        self.assertEqual(len([u for u in slow.calls if u in POSTS]), 1)
        self.assertEqual(len(offer["articles"]), 1)

    def test_a_page_with_a_malformed_link_still_gets_its_offer(self):
        page = (b'<html><head><title>Notes</title></head><body><a href="//[::1">x</a><a href="https://[abc/blog/q">y</a>'
                b'<a href="/blog/latency-per-decision">Latency per decision</a></body></html>')
        get = blog_site(**{BLOG: page})
        result = discovery.discover(BLOG, get=get)
        self.assertTrue(result["page_index"]["offered"])
        self.assertEqual(result["page_index"]["links"], ["https://ledgerlight.example/blog/latency-per-decision"])

    def test_links_are_read_against_the_page_that_answered_not_the_pasted_address(self):
        page = b'<html><head><title>Notes</title></head><body><a href="latency-per-decision">Latency</a></body></html>'
        get = blog_site(**{BLOG: (200, page, BLOG + "/")})  # /blog answered from /blog/
        offer = discovery.discover(BLOG, get=get)["page_index"]
        self.assertTrue(offer["offered"], offer)
        self.assertEqual(offer["links"], ["https://ledgerlight.example/blog/latency-per-decision"])

    def test_a_page_answered_from_another_port_gets_no_offer(self):
        get = blog_site(**{BLOG: (200, fixture("blog-nofeed-index.html"), "https://ledgerlight.example:8443/blog")})
        offer = discovery.discover(BLOG, get=get)["page_index"]
        self.assertFalse(offer["offered"])
        self.assertIn("another site", offer["reason"])

    def test_no_offer_when_a_feed_was_found_and_no_article_is_fetched(self):
        feed = fixture("feed-rss.xml")
        get = blog_site(**{"https://ledgerlight.example/blog/feed": feed})
        result = discovery.discover(BLOG, get=get)
        self.assertTrue(result["candidates"][0]["ok"])
        self.assertFalse(result["page_index"]["offered"])
        self.assertFalse(any(url in get.calls for url in POSTS))

    def test_a_pasted_http_address_is_still_refused_with_the_plain_http_sentence(self):
        get = blog_site()
        with self.assertRaises(discovery.DiscoveryError) as cm:
            discovery.discover("http://ledgerlight.example/blog", get=get)
        self.assertEqual(str(cm.exception), discovery.PLAIN_HTTP)
        self.assertFalse(any(url in get.calls for url in POSTS))
        self.assertFalse(any(url.startswith("http://") for url in get.calls))

    def test_a_bare_address_is_checked_as_https_and_offered(self):
        offer = discovery.discover("ledgerlight.example/blog", get=blog_site())["page_index"]
        self.assertTrue(offer["offered"])

    def test_the_front_page_gets_no_offer_and_no_article_is_fetched(self):
        get = blog_site(**{"https://ledgerlight.example/": fixture("blog-nofeed-index.html")})
        result = discovery.discover("https://ledgerlight.example/", get=get)
        self.assertFalse(result["page_index"]["offered"])
        self.assertIn("front page", result["page_index"]["reason"])
        self.assertFalse(any(url in get.calls for url in POSTS))

    def test_a_page_that_redirects_to_another_site_gets_no_offer(self):
        get = blog_site(**{BLOG: (200, fixture("blog-nofeed-index.html"), "https://elsewhere.example.net/blog")})
        offer = discovery.discover(BLOG, get=get)["page_index"]
        self.assertFalse(offer["offered"])
        self.assertIn("another site", offer["reason"])
        self.assertFalse(any(url in get.calls for url in POSTS))

    def test_a_page_that_cannot_be_read_gets_no_offer(self):
        for answer in ((404, b"gone"), (500, b"error"), TimeoutError("slow")):
            with self.subTest(answer=repr(answer)):
                offer = discovery.discover(BLOG, get=TableGet({BLOG: answer}))["page_index"]
                self.assertFalse(offer["offered"])
                self.assertIn("could not be read", offer["reason"])

    def test_a_page_with_no_links_under_its_folder_gets_no_offer_and_says_why(self):
        page = b'<html><body><a href="/about">About</a><a href="https://elsewhere.example.net/blog/x">X</a></body></html>'
        get = TableGet({BLOG: page})
        offer = discovery.discover(BLOG, get=get)["page_index"]
        self.assertFalse(offer["offered"])
        self.assertIn("ledgerlight.example under /blog/", offer["reason"])
        self.assertEqual(offer["links"], [])

    def test_a_page_with_links_whose_articles_cannot_be_read_is_offered_but_not_selectable(self):
        get = TableGet({BLOG: fixture("blog-nofeed-index.html")})
        offer = discovery.discover(BLOG, get=get)["page_index"]
        self.assertTrue(offer["offered"])
        self.assertFalse(offer["ok"])
        self.assertEqual(offer["articles"], [])
        self.assertTrue(offer["refusal"])

    def test_the_address_is_refused_before_any_fetch_when_it_is_unsafe(self):
        get = TableGet({})
        for address in ("https://user:pw@ledgerlight.example/blog", "https://127.0.0.1/blog"):
            with self.assertRaises(discovery.DiscoveryError):
                discovery.discover(address, get=get)
        self.assertEqual(get.calls, [])

    def test_a_dot_segment_address_gets_no_offer(self):
        get = blog_site(**{"https://ledgerlight.example/blog/../enterprise": fixture("blog-nofeed-index.html")})
        offer = discovery.discover("https://ledgerlight.example/blog/../enterprise", get=get)["page_index"]
        self.assertFalse(offer["offered"])
        self.assertFalse(any(url in get.calls for url in POSTS))


class RegisterTests(unittest.TestCase):
    """The confirmed offer: the server rebuilds the entry from the address, reads it once, and saves it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "sources.json"
        self.get = blog_site()
        self.service = sources_registry.SourceService(self.path, bundled=BUNDLED, get=self.get)

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, candidate, label="Ledgerlight notes", pasted=BLOG):
        return self.service.register_candidate({"candidate": candidate, "label": label, "pasted_url": pasted})

    def saved(self):
        return json.loads(self.path.read_text())["sources"]

    def test_confirming_the_offer_saves_one_html_index_source_with_the_pages_scope(self):
        added = self.add({"kind": "html-index", "url": BLOG})
        self.assertEqual(added["source"]["kind"], "html-index")
        self.assertEqual(added["source"]["id"], "ledgerlight-notes")
        self.assertIn("reads the article links on that page (ledgerlight.example/blog/ only)",
                      added["source"]["note"])
        self.assertIn("from " + BLOG, added["source"]["note"])
        [entry] = self.saved()
        self.assertEqual(entry["kind"], "html-index")
        self.assertEqual(entry["url"], BLOG)
        self.assertEqual(entry["max_items"], 5)
        self.assertEqual(entry["discovery"], {"allowed_hosts": ["ledgerlight.example"],
                                              "allowed_path_prefixes": ["/blog/"], "max_candidates": 10})
        registry.parse_document({"schema": registry.SCHEMA, "sources": self.saved()}, "saved")
        # it is live, and a brief reads it with the same reader
        self.assertIn("ledgerlight-notes", self.service.snapshot().ids)
        for url in NEVER_ASKED:
            self.assertNotIn(url, self.get.calls)

    def test_a_saved_source_reads_only_its_scope_when_a_brief_uses_it(self):
        self.add({"kind": "html-index", "url": BLOG})
        source = self.service.snapshot().get("ledgerlight-notes")
        brief_get = blog_site()
        items, receipt = adapters.fetch(source, brief_get)
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual([i["url"] for i in items], EXPECTED_LINKS)
        for url in NEVER_ASKED:
            self.assertNotIn(url, brief_get.calls)

    def test_the_browser_cannot_widen_the_scope(self):
        forged = {"kind": "html-index", "url": BLOG, "ok": True,
                  "discovery": {"allowed_hosts": ["elsewhere.example.net", "ledgerlight.example"],
                                "allowed_path_prefixes": ["/"], "max_candidates": 40},
                  "allowed_hosts": ["elsewhere.example.net"], "allowed_path_prefixes": ["/"],
                  "max_candidates": 40, "max_items": 20, "allowed_host": "elsewhere.example.net",
                  "allowed_path_prefix": "/", "extraction_tier": "trafilatura", "id": "bundled", "label": "x"}
        self.add(forged)
        [entry] = self.saved()
        self.assertEqual(entry["discovery"], {"allowed_hosts": ["ledgerlight.example"],
                                              "allowed_path_prefixes": ["/blog/"], "max_candidates": 10})
        self.assertEqual(entry["max_items"], 5)
        self.assertNotIn("extraction_tier", entry)
        self.assertEqual(entry["id"], "ledgerlight-notes")

    def test_unsafe_pages_are_refused_and_nothing_is_saved_or_fetched(self):
        for url in ("http://ledgerlight.example/blog", "https://user:pw@ledgerlight.example/blog",
                    "https://127.0.0.1/blog", "https://ledgerlight.example:99999/blog",
                    "https://ledgerlight.example/", "https://ledgerlight.example/blog/../enterprise",
                    "https://ledgerlight.example/blog/%2e%2e/enterprise"):
            with self.subTest(url=url):
                with self.assertRaises(sources_registry.SourceServiceError):
                    self.add({"kind": "html-index", "url": url})
        self.assertEqual(self.get.calls, [])
        self.assertFalse(self.path.exists())

    def test_a_page_whose_articles_cannot_be_read_again_is_not_saved(self):
        service = sources_registry.SourceService(self.path, bundled=BUNDLED,
                                                 get=TableGet({BLOG: fixture("blog-nofeed-index.html")}))
        with self.assertRaises(sources_registry.SourceServiceError) as cm:
            service.register_candidate({"candidate": {"kind": "html-index", "url": BLOG}, "label": "Ledgerlight",
                                        "pasted_url": BLOG})
        self.assertIn("did not give any items", str(cm.exception))
        self.assertFalse(self.path.exists())

    def test_the_same_page_or_name_twice_is_refused(self):
        self.add({"kind": "html-index", "url": BLOG})
        with self.assertRaises(sources_registry.SourceServiceError) as cm:
            self.add({"kind": "html-index", "url": BLOG + "#again"}, label="Another name")
        self.assertIn("already here", str(cm.exception))
        with self.assertRaises(sources_registry.SourceServiceError) as cm:
            self.add({"kind": "html-index", "url": BLOG + "/"}, label="ledgerlight NOTES")
        self.assertIn("already exists", str(cm.exception))
        self.assertEqual(len(self.saved()), 1)

    def test_hidden_and_direction_characters_are_removed_from_the_name_and_the_note(self):
        self.add({"kind": "html-index", "url": BLOG}, label="Ledger\u202elight\u200b notes",
                 pasted=BLOG + "?q=a\u202eb")
        [entry] = self.saved()
        self.assertEqual(entry["label"], "Ledgerlight notes")
        for ch in ("\u202e", "\u200b"):
            self.assertNotIn(ch, entry["note"])
            self.assertNotIn(ch, entry["label"])

    def test_a_feed_candidate_is_still_an_rss_or_atom_source(self):
        service = sources_registry.SourceService(
            self.path, bundled=BUNDLED, get=TableGet({"https://ledgerlight.example/feed.xml": fixture("feed-rss.xml")}))
        service.register_candidate({"candidate": {"url": "https://ledgerlight.example/feed.xml"},
                                    "label": "Ledgerlight feed", "pasted_url": ""})
        [entry] = json.loads(self.path.read_text())["sources"]
        self.assertEqual(entry["kind"], "rss-or-atom")
        self.assertNotIn("discovery", entry)


class RouteTests(unittest.TestCase):
    """Through the real server: probe, then register, with the page's anti-forgery headers."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.get = blog_site()
        self.sources = sources_registry.SourceService(Path(self.tmp.name) / "sources.json", bundled=BUNDLED,
                                                      get=self.get)
        self.app = server.App(self.sources.snapshot(), lambda: "model", source_service=self.sources,
                              lens_store=lenses.LensStore(Path(self.tmp.name) / "lenses"),
                              data_root=Path(self.tmp.name) / "data")
        quiet = type("Quiet", (server.handler_for(self.app),), {"log_message": lambda *a: None})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), quiet)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.port = self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def post(self, path, body):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        conn.request("POST", path, body=json.dumps(body),
                     headers={"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json",
                              "Origin": f"http://127.0.0.1:{self.port}", server.CSRF_HEADER: server.CSRF_VALUE})
        reply = conn.getresponse()
        doc = json.loads(reply.read())
        conn.close()
        return reply.status, doc

    def test_check_then_confirm_adds_a_live_source_the_picker_lists(self):
        status, probe = self.post("/source/probe", {"url": BLOG})
        self.assertEqual(status, 200)
        offer = probe["page_index"]
        self.assertTrue(offer["offered"] and offer["ok"])
        # nothing is saved by the check
        self.assertFalse((Path(self.tmp.name) / "sources.json").exists())
        status, added = self.post("/source/register", {"candidate": {"kind": "html-index", "url": offer["url"]},
                                                       "label": offer["suggested_label"], "pasted_url": BLOG})
        self.assertEqual(status, 201, added)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/data/options.json", headers={"Host": f"127.0.0.1:{self.port}"})
        options = json.loads(conn.getresponse().read())
        conn.close()
        self.assertIn(added["source"]["id"], options["sources"])

    def test_the_check_of_an_unsafe_address_answers_400(self):
        for url in ("https://user:pw@ledgerlight.example/blog", "http://ledgerlight.example/blog"):
            status, doc = self.post("/source/probe", {"url": url})
            self.assertEqual(status, 400, url)
            self.assertIn("error", doc)
        self.assertFalse(any(url.startswith("http://") for url in self.get.calls))


if __name__ == "__main__":
    unittest.main()
