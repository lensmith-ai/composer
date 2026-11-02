"""Add a source from the app page: paste an address, see the candidate feeds behind it, pick one, name it.

The page posts {"url"} to /source/probe and reads `candidates`; then {candidate, label, pasted_url} to
/source/register. Offline: every fetch is answered from a table, except the tests that show the real guarded fetch
refusing an address on this machine before any connection."""
import http.client
import json
import os
import socket
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from composer import discovery, fetch, lenses, server, sources_registry
from composer.fetch import Response
from composer.registry import BUNDLED

from helpers import fixture

PAGE = b"""<!doctype html><html><head><title>Harbor Lab</title>
<link rel="alternate" type="application/rss+xml" title="Harbor Lab notes" href="/harbor/feed.xml">
<link rel="alternate" type="application/rss+xml" title="Comments on Harbor Lab" href="/harbor/comments/feed/">
<link rel="stylesheet" href="/site.css">
</head><body><p>Our notes.</p></body></html>"""

COMMENTS_FEED = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Comments</title>
<item><title>Comment on the tide map by a reader</title><link>https://example.org/c/1</link></item>
</channel></rss>"""


class TableGet:
    """get(url, timeout): the table's answer, 404 for anything else; records every call."""

    def __init__(self, table):
        self.table = table
        self.calls = []

    def __call__(self, url, timeout):
        self.calls.append(url)
        value = self.table.get(url, (404, b"not here"))
        if isinstance(value, BaseException):
            raise value
        if isinstance(value, tuple):
            return Response(url, value[0], value[1])
        return Response(url, 200, value)


def harbor_site():
    return TableGet({"https://example.org/harbor": PAGE,
                     "https://example.org/harbor/feed.xml": fixture("feed-rss.xml"),
                     "https://example.org/harbor/comments/feed/": COMMENTS_FEED})


class DiscoveryTests(unittest.TestCase):
    def test_a_page_address_gives_its_advertised_feeds_with_comments_last_and_none_chosen(self):
        get = harbor_site()
        result = discovery.discover("https://example.org/harbor", get=get)
        self.assertIsNone(result["selected"])
        self.assertTrue(result["page"]["fetched"])
        rows = result["candidates"]
        self.assertEqual([r["url"] for r in rows],
                         ["https://example.org/harbor/feed.xml", "https://example.org/harbor/comments/feed/"])
        first, comments = rows
        self.assertTrue(first["ok"])
        self.assertEqual(first["origin"], "advertised")
        self.assertEqual(first["items"], 4)
        self.assertEqual(first["titles"][0], "Harbor Lab opens a tide-sensor map")
        self.assertEqual(first["suggested_label"], "Harbor Lab notes")  # the feed's own title
        self.assertFalse(first["looks_like_comments"])
        self.assertTrue(comments["looks_like_comments"])
        # the page itself was fetched once, though it was tried as a feed and read as a page
        self.assertEqual(get.calls.count("https://example.org/harbor"), 1)

    def test_the_pasted_address_can_itself_be_the_feed(self):
        get = TableGet({"https://example.org/feed.xml": fixture("feed-atom.xml")})
        result = discovery.discover("https://example.org/feed.xml", get=get)
        self.assertEqual(result["candidates"][0]["origin"], "as-pasted")
        self.assertTrue(result["candidates"][0]["ok"])

    def test_addresses_with_the_same_items_are_shown_once_on_the_narrowest(self):
        feed = fixture("feed-rss.xml")
        get = TableGet({"https://example.org": b"<html><head></head></html>", "https://example.org/feed/": feed,
                        "https://example.org/blog/feed/": feed})
        rows = discovery.discover("https://example.org/", get=get)["candidates"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://example.org/blog/feed/")
        self.assertEqual(rows[0]["same_as"], ["https://example.org/feed/"])

    def test_a_plain_http_or_bare_address_is_checked_as_https(self):
        get = harbor_site()
        result = discovery.discover("http://example.org/harbor", get=get)
        self.assertEqual(result["checked"], "https://example.org/harbor")
        self.assertIn("https", result["note"])
        self.assertTrue(all(url.startswith("https://") for url in get.calls))
        self.assertEqual(discovery.discover("example.org/harbor", get=harbor_site())["checked"],
                         "https://example.org/harbor")

    def test_addresses_on_this_machine_or_a_private_network_are_refused_before_any_fetch(self):
        get = TableGet({})
        for address in ("https://127.0.0.1/feed", "http://localhost:8765/", "https://10.1.2.3/blog",
                        "https://169.254.169.254/latest/meta-data/", "https://[::1]/", "file:///etc/passwd",
                        "https://user:pass@example.org/", "", "https://" + "a" * 2050):
            with self.subTest(address=address):
                with self.assertRaises(discovery.DiscoveryError):
                    discovery.discover(address, get=get)
        self.assertEqual(get.calls, [])

    def test_the_real_fetch_refuses_a_name_that_resolves_to_this_machine(self):
        # the name passes the address check (it is not an IP or localhost), so the guarded fetch must refuse it on
        # the address it resolves to, for the page and for every guessed feed address, before connecting
        real = socket.getaddrinfo

        def resolve(host, port, *args, **kwargs):
            if host == "feeds.example.org":
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]
            return real(host, port, *args, **kwargs)
        connects = []
        with mock.patch.dict(os.environ, {fetch.ALLOW_PRIVATE_ENV: ""}), \
                mock.patch("socket.getaddrinfo", side_effect=resolve), \
                mock.patch("socket.socket.connect", side_effect=lambda *a: connects.append(a)):
            result = discovery.discover("https://feeds.example.org/blog")
        self.assertEqual(connects, [])
        self.assertFalse(any(r["ok"] for r in result["candidates"]))
        self.assertIn("private network", result["page"]["refusal"])

    def test_one_time_limit_and_a_request_cap_cover_the_whole_check(self):
        links = "".join(f'<link rel="alternate" type="application/rss+xml" href="/f{n}.xml">' for n in range(40))
        get = TableGet({"https://example.org/": f"<html><head>{links}</head></html>".encode()})
        result = discovery.discover("https://example.org/", get=get)
        self.assertLessEqual(len(get.calls), discovery.MAX_REQUESTS)
        self.assertTrue(result["candidates"])  # failed advertised feeds are still shown, with why
        self.assertTrue(all(r["refusal"] for r in result["candidates"]))
        slow = TableGet({})
        ticks = iter([0.0] + [1000.0] * 200)
        result = discovery.discover("https://example.org/", get=slow, total_s=60, clock=lambda: next(ticks))
        self.assertEqual(slow.calls, [])
        self.assertIn("out of time", json.dumps(result))

    def test_an_advertised_feed_on_a_private_address_is_listed_as_refused_not_fetched(self):
        page = b'<link rel="alternate" type="application/atom+xml" href="https://192.168.1.5/feed.xml">'
        get = TableGet({"https://example.org/": page})
        rows = discovery.discover("https://example.org/", get=get)["candidates"]
        self.assertEqual(rows[0]["url"], "https://192.168.1.5/feed.xml")
        self.assertFalse(rows[0]["ok"])
        self.assertIn("private network", rows[0]["refusal"])
        self.assertNotIn("https://192.168.1.5/feed.xml", get.calls)

    def test_one_check_at_a_time(self):
        self.assertTrue(discovery._one_at_a_time.acquire(blocking=False))
        try:
            with self.assertRaises(discovery.Busy):
                discovery.discover("https://example.org/", get=TableGet({}))
        finally:
            discovery._one_at_a_time.release()


class AddSourceRouteTests(unittest.TestCase):
    """The two page requests, through the real server and its anti-forgery checks."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.get = harbor_site()
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

    def post(self, path, body, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        sent = {"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json",
                "Origin": f"http://127.0.0.1:{self.port}", server.CSRF_HEADER: server.CSRF_VALUE}
        sent.update(headers or {})
        conn.request("POST", path, body=json.dumps(body), headers=sent)
        reply = conn.getresponse()
        doc = json.loads(reply.read())
        conn.close()
        return reply.status, doc

    def options(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/data/options.json", headers={"Host": f"127.0.0.1:{self.port}"})
        doc = json.loads(conn.getresponse().read())
        conn.close()
        return doc

    def test_paste_pick_and_name_adds_a_live_source(self):
        status, probe = self.post("/source/probe", {"url": "https://example.org/harbor"})
        self.assertEqual(status, 200)
        picked = probe["candidates"][0]
        self.assertTrue(picked["ok"])
        before = len(self.get.calls)
        status, added = self.post("/source/register", {"candidate": picked, "label": "Harbor Lab",
                                                       "pasted_url": "https://example.org/harbor"})
        self.assertEqual(status, 201, added)
        self.assertEqual(added["source"]["id"], "harbor-lab")
        self.assertEqual(added["source"]["url"], "https://example.org/harbor/feed.xml")
        self.assertIn("from https://example.org/harbor", added["source"]["note"])
        self.assertEqual(self.get.calls[before:], ["https://example.org/harbor/feed.xml"])  # read again, once
        options = self.options()
        self.assertIn("harbor-lab", options["sources"])
        self.assertEqual(options["source_meta"]["harbor-lab"]["label"], "Harbor Lab")
        saved = json.loads((Path(self.tmp.name) / "sources.json").read_text())
        self.assertEqual([s["id"] for s in saved["sources"]], ["harbor-lab"])
        # the same feed twice, or the same name twice, is refused
        status, again = self.post("/source/register", {"candidate": picked, "label": "Other name",
                                                       "pasted_url": ""})
        self.assertEqual(status, 400)
        self.assertIn("already here", again["error"])

    def test_the_candidate_is_not_trusted_its_address_is_read_again(self):
        forged = {"url": "https://example.org/harbor/missing.xml", "ok": True, "items": 9, "titles": ["x"]}
        status, doc = self.post("/source/register", {"candidate": forged, "label": "Forged", "pasted_url": ""})
        self.assertEqual(status, 400)
        self.assertIn("did not give any items", doc["error"])
        for url in ("https://127.0.0.1/feed.xml", "http://example.org/harbor/feed.xml"):
            status, doc = self.post("/source/register", {"candidate": {"url": url, "ok": True}, "label": "X",
                                                         "pasted_url": ""})
            self.assertEqual(status, 400, url)
        self.assertFalse((Path(self.tmp.name) / "sources.json").exists())

    def test_both_requests_need_the_page_headers_before_any_fetch(self):
        for path, body in (("/source/probe", {"url": "https://example.org/harbor"}),
                           ("/source/register", {"candidate": {"url": "https://example.org/harbor/feed.xml"},
                                                 "label": "x", "pasted_url": ""})):
            status, _ = self.post(path, body, {server.CSRF_HEADER: ""})
            self.assertEqual(status, 403)
        self.assertEqual(self.get.calls, [])

    def test_an_http_only_address_is_refused_with_the_reason_the_page_shows(self):
        self.get.table["https://example.org/plain"] = (404, b"no https here")
        status, doc = self.post("/source/probe", {"url": "http://example.org/plain"})
        self.assertEqual(status, 400)
        self.assertTrue(doc["error"].startswith("This address uses plain http, and Composer reads feeds only over "
                                                "https"), doc["error"])
        self.assertIn("the claim check would then vouch for the changed text", doc["error"])
        self.assertFalse(any(url.startswith("http://") for url in self.get.calls))  # nothing is read in the clear
        # the same site over https still works
        status, doc = self.post("/source/probe", {"url": "http://example.org/harbor"})
        self.assertEqual(status, 200)
        self.assertTrue(doc["candidates"][0]["ok"])

    def test_a_refused_address_answers_400_with_a_sentence(self):
        status, doc = self.post("/source/probe", {"url": "https://127.0.0.1:8765/"})
        self.assertEqual(status, 400)
        self.assertIn("private network", doc["error"])


class FullProbeBudgetTests(unittest.TestCase):
    """A full registry entry sent to /source/probe: one request and byte budget for the whole probe."""

    def index_source(self):
        return {"id": "big-index", "label": "Big index", "kind": "html-index", "url": "https://example.org/news/",
                "max_items": 20, "discovery": {"allowed_hosts": ["example.org"], "allowed_path_prefixes": ["/news/"],
                                               "max_candidates": 40}}

    def page(self):
        return "".join(f'<a href="/news/a{n}">a</a>' for n in range(40)).encode()

    def test_many_failing_articles_stop_at_the_request_budget(self):
        get = TableGet({"https://example.org/news/": self.page()})  # every article answers 404
        with tempfile.TemporaryDirectory() as d:
            service = sources_registry.SourceService(Path(d) / "s.json", bundled=BUNDLED, get=get)
            service.probe(self.index_source())
        self.assertEqual(len(get.calls), 24)  # the index and 23 articles, not the index and all 40

    def test_large_articles_stop_at_the_byte_budget(self):
        big = b"<title>t</title>" + b"x" * (1900 * 1024)
        get = TableGet({"https://example.org/news/": self.page(),
                        **{f"https://example.org/news/a{n}": big for n in range(40)}})
        with tempfile.TemporaryDirectory() as d:
            service = sources_registry.SourceService(Path(d) / "s.json", bundled=BUNDLED, get=get)
            service.probe(self.index_source())
        read = len(self.page()) + (len(get.calls) - 1) * len(big)
        self.assertLessEqual(read, 8 * 1024 * 1024 + len(big))  # 8 MB in all, at most one article over
        self.assertLess(len(get.calls), 10)


class SourceFileWriterTests(unittest.TestCase):
    """Every writer of one sources file takes the same lock for its whole read-check-write: two `composer serve`
    processes (here two services with their own in-process locks), `composer sources add` and setup."""

    def entry(self, n):
        return {"id": f"feed-{n}", "label": f"Feed {n}", "kind": "rss-or-atom",
                "url": f"https://example.org/f{n}.xml", "max_items": 3}

    def table(self, count):
        return TableGet({f"https://example.org/f{n}.xml": fixture("feed-rss.xml") for n in range(count)})

    def test_a_writer_waits_for_the_lock_held_by_another(self):
        from composer import registry
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "sources.json"
            service = sources_registry.SourceService(path, bundled=BUNDLED, get=self.table(2))
            done = []
            with registry.file_lock(path):
                worker = threading.Thread(target=lambda: done.append(service.register(self.entry(0))))
                worker.start()
                cli_add = threading.Thread(target=lambda: done.append(
                    registry.add_to_file(path, registry.parse_entry(self.entry(1)))))
                cli_add.start()
                worker.join(0.6)
                cli_add.join(0.1)
                self.assertTrue(worker.is_alive() and cli_add.is_alive(), "a writer went ahead without the lock")
                self.assertFalse(path.exists())
            worker.join(10)
            cli_add.join(10)
            ids = [s["id"] for s in json.loads(path.read_text())["sources"]]
            self.assertEqual(sorted(ids), ["feed-0", "feed-1"])
            self.assertEqual([p.name for p in Path(d).glob("*.tmp")], [])

    def test_two_services_on_one_file_lose_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "sources.json"
            get = self.table(24)
            services = [sources_registry.SourceService(path, bundled=BUNDLED, get=get) for _ in range(2)]
            errors = []

            def register(n):
                try:
                    services[n % 2].register(self.entry(n))
                except Exception as exc:  # recorded, so a lost or failed write shows in the assertion
                    errors.append(repr(exc))
            workers = [threading.Thread(target=register, args=(n,)) for n in range(24)]
            for w in workers:
                w.start()
            for w in workers:
                w.join(30)
            ids = {s["id"] for s in json.loads(path.read_text())["sources"]}
        self.assertEqual(errors, [])
        self.assertEqual(ids, {f"feed-{n}" for n in range(24)})

    def test_a_new_source_that_appeared_meanwhile_is_refused_not_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "sources.json"
            first = sources_registry.SourceService(path, bundled=BUNDLED, get=harbor_site())
            second = sources_registry.SourceService(path, bundled=BUNDLED, get=harbor_site())
            second.snapshot()  # its view is taken before the first one writes
            pick = {"url": "https://example.org/harbor/feed.xml"}
            first.register_candidate({"candidate": pick, "label": "Harbor Lab", "pasted_url": ""})
            with mock.patch.object(second, "snapshot", return_value=second._registry):
                with self.assertRaises(sources_registry.SourceServiceError) as cm:
                    second.register_candidate({"candidate": pick, "label": "Harbor Lab", "pasted_url": ""})
            self.assertIn("someone else", str(cm.exception))
            self.assertEqual(len(json.loads(path.read_text())["sources"]), 1)


if __name__ == "__main__":
    unittest.main()
