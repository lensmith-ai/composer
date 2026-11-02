import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from composer import demo, lenses, server, sources_registry
from composer.registry import BUNDLED

from helpers import ScriptedGet, fixture


class P1bRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.get = get = ScriptedGet({"https://example.org/feed.xml": fixture("feed-rss.xml")})
        self.sources = sources_registry.SourceService(Path(self.tmp.name) / "sources.json", bundled=BUNDLED, get=get)
        self.app = server.App(self.sources.snapshot(), lambda: "model", source_service=self.sources,
                              lens_store=lenses.LensStore(Path(self.tmp.name) / "lenses"),
                              compose=lambda **kw: {"edition": {"lens": kw["lens"], "cards": [], "sources": []}},
                              data_root=Path(self.tmp.name) / "data")
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler_for(self.app))
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        headers = dict(headers or {})
        headers.setdefault("Host", f"127.0.0.1:{self.port}")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path, body=body, headers=headers)
        reply = conn.getresponse()
        data = reply.read()
        conn.close()
        return reply.status, json.loads(data)

    def mutation_headers(self):
        return {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}",
                "Sec-Fetch-Site": "same-origin", server.CSRF_HEADER: server.CSRF_VALUE}

    def payload(self):
        return {"id": "fixture-feed", "label": "Fixture feed", "kind": "rss-or-atom",
                "url": "https://example.org/feed.xml", "max_items": 3}

    def test_options_probe_and_register_through_real_local_server(self):
        status, options = self.request("GET", "/data/options.json")
        self.assertEqual(status, 200)
        self.assertEqual(options["insights"]["default"], 5)
        self.assertEqual((options["insights"]["min"], options["insights"]["max"]), (3, 10))
        self.assertEqual(options["reading_levels"], ["plain", "standard", "technical"])
        self.assertEqual(options["lenses"][:3], ["system-improvements", "second-order-effects", "raised-eyebrow"])
        self.assertIn("voices", options)  # the narration part of the options stays
        body = json.dumps(self.payload())
        status, probe = self.request("POST", "/source/probe", body, self.mutation_headers())
        self.assertEqual(status, 200)
        self.assertEqual(probe["receipt"]["status"], "ok")
        status, registered = self.request("POST", "/source/register", body, self.mutation_headers())
        self.assertEqual(status, 201)
        self.assertEqual(registered["source"]["id"], "fixture-feed")
        status, options = self.request("GET", "/data/options.json")
        self.assertIn("fixture-feed", options["sources"])
        self.assertEqual(options["source_meta"]["fixture-feed"]["label"], "Fixture feed")
        self.assertTrue(options["source_status"]["fixture-feed"]["available"])

    def test_every_mutation_needs_the_anti_forgery_header_before_service_work(self):
        for path, payload in (("/source/probe", self.payload()), ("/source/register", self.payload()),
                              ("/lens/save", {"name": "New", "instruction": "Look for clear changes.", "reading_level": "plain"})):
            with self.subTest(path=path):
                headers = {k: v for k, v in self.mutation_headers().items() if k != server.CSRF_HEADER}
                status, result = self.request("POST", path, json.dumps(payload), headers)
                self.assertEqual(status, 403)
                self.assertIn("anti-forgery", result["error"])
                headers = {k: v for k, v in self.mutation_headers().items() if k != "Origin"}
                status, result = self.request("POST", path, json.dumps(payload), headers)
                self.assertEqual(status, 403)
        self.assertEqual(self.get.calls, [])
        self.assertFalse((Path(self.tmp.name) / "sources.json").exists())
        self.assertFalse((Path(self.tmp.name) / "lenses").exists())

    def test_lens_save_uses_the_real_server_and_content_addressed_store(self):
        payload = {"name": "Team focus", "instruction": "Look for durable team improvements.",
                   "reading_level": "plain"}
        status, result = self.request("POST", "/lens/save", json.dumps(payload), self.mutation_headers())
        self.assertEqual(status, 201)
        revision = result["lens"]["digest"]
        self.assertTrue((Path(self.tmp.name) / "lenses" / revision / "recipe.json").exists())

    def test_lens_edit_creates_a_new_revision_linked_to_the_saved_recipe(self):
        first = {"name": "Team focus", "instruction": "Look for durable team improvements.",
                 "reading_level": "plain"}
        status, saved = self.request("POST", "/lens/save", json.dumps(first), self.mutation_headers())
        self.assertEqual(status, 201)
        changed = {**first, "instruction": "Look for durable team improvements and tradeoffs.",
                   "previous": saved["lens"]["digest"]}
        status, edited = self.request("POST", "/lens/save", json.dumps(changed), self.mutation_headers())
        self.assertEqual(status, 201)
        self.assertNotEqual(edited["lens"]["digest"], saved["lens"]["digest"])
        recipe = json.loads((Path(self.tmp.name) / "lenses" / edited["lens"]["digest"] / "recipe.json").read_text())
        self.assertEqual(recipe["previous"], saved["lens"]["digest"])

    def test_custom_lens_option_resolves_to_its_recipe_for_composition(self):
        payload = {"name": "Team focus", "instruction": "Look for durable team improvements.",
                   "reading_level": "plain"}
        status, saved = self.request("POST", "/lens/save", json.dumps(payload), self.mutation_headers())
        self.assertEqual(status, 201)
        captured = {}

        def compose(**kwargs):
            captured.update(kwargs)
            return {"edition": {"lens": kwargs["lens"], "cards": [], "sources": []}}

        self.app.compose = compose
        status, _ = self.request("POST", "/api/compose", json.dumps({"sources": ["google-ai"],
                                                                         "lens": saved["lens"]["id"]}),
                                 self.mutation_headers())
        self.assertEqual(status, 200)
        self.assertEqual(captured["lens"], payload["instruction"])
        self.assertEqual(captured["lens_definition"].revision, saved["lens"]["digest"])

    def test_background_compose_takes_a_lens_id_and_reading_level_and_serves_its_receipts(self):
        captured = {}
        edition = dict(demo.load(), transcript="A spoken script. " * 20)

        def compose(**kwargs):
            captured.update(kwargs)
            receipt = {"source": "google-ai", "label": "Google AI", "status": "ok", "items": 4, "bytes": 900,
                       "cleaned": 0, "fetch_tier": "native"}
            return {"edition": edition, "result": {}, "fetched": {"google-ai": ([{"title": "private words"}], receipt)},
                    "receipt": {"provider": "fixture", "calls": 2}}

        self.app.compose = compose
        status, accepted = self.request("POST", "/compose", json.dumps(
            {"sources": ["google-ai"], "lens": "raised-eyebrow", "reading_level": "plain", "insights": 10}),
            self.mutation_headers())
        self.assertEqual(status, 202, accepted)
        job = self.app.jobs.wait(accepted["job"], 10)
        self.assertEqual(job["phase"], "verified", job)
        self.assertEqual(captured["lens_definition"].id, "raised-eyebrow")
        self.assertEqual(captured["lens_definition"].reading_level, "plain")
        self.assertEqual(captured["lens"], captured["lens_definition"].instruction)
        self.assertEqual(captured["count"], 10)
        status, receipt = self.request("GET", f"/data/live/{accepted['job']}/receipts.json")
        self.assertEqual(status, 200)
        self.assertEqual(receipt["requested_sources"], ["google-ai"])
        self.assertEqual(receipt["sources"]["google-ai"]["fetch_tier"], "native")
        self.assertNotIn("private words", json.dumps(receipt))
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", f"/data/live/{accepted['job']}/transcript.txt", headers={"Host": f"127.0.0.1:{self.port}"})
        reply = conn.getresponse()
        self.assertEqual((reply.status, reply.read().decode("utf-8")), (200, edition["transcript"].strip() + "\n"))
        conn.close()

    def test_background_compose_refuses_a_bad_reading_level_and_an_eleventh_insight(self):
        for body in ({"sources": ["google-ai"], "lens": "raised-eyebrow", "reading_level": "loud"},
                     {"sources": ["google-ai"], "lens": "raised-eyebrow", "insights": 11}):
            with self.subTest(body=body):
                status, _ = self.request("POST", "/compose", json.dumps(body), self.mutation_headers())
                self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
