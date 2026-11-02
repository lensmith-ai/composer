import json
import tempfile
import unittest
from pathlib import Path

from composer import html_extract, registry, sources_registry
from composer.registry import BUNDLED

from helpers import ScriptedGet, fixture

BUNDLED_IDS = [e.id for e in registry.read_file(BUNDLED)]  # the six default sources, in their file order


class SourceServiceTests(unittest.TestCase):
    def source_payload(self, source_id="fixture-feed"):
        return {"id": source_id, "label": "Fixture feed", "kind": "rss-or-atom",
                "url": "https://example.org/feed.xml", "max_items": 3}

    def test_probe_returns_safe_headlines_and_native_tier(self):
        get = ScriptedGet({"https://example.org/feed.xml": fixture("feed-rss.xml")})
        with tempfile.TemporaryDirectory() as d:
            service = sources_registry.SourceService(Path(d) / "sources.json", bundled=BUNDLED, get=get)
            result = service.probe(self.source_payload())
        self.assertEqual(result["receipt"]["status"], "ok")
        self.assertEqual(result["fetch_tier"], "native")
        self.assertTrue(result["headlines"])
        self.assertNotIn("description", result["headlines"][0])
        self.assertEqual(get.calls, ["https://example.org/feed.xml"])

    def test_register_reloads_without_restart_and_preserves_the_bundled_sources(self):
        get = ScriptedGet({"https://example.org/feed.xml": fixture("feed-rss.xml")})
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "sources.json"
            service = sources_registry.SourceService(target, bundled=BUNDLED, get=get)
            before = service.options()
            entry = service.register(self.source_payload())
            after = service.options()
            self.assertEqual(entry["id"], "fixture-feed")
            self.assertEqual([row["id"] for row in before["sources"]], BUNDLED_IDS)
            self.assertEqual([row["id"] for row in after["sources"]], BUNDLED_IDS + ["fixture-feed"])
            self.assertGreater(after["generation"], before["generation"])
            self.assertEqual(json.loads(target.read_text())["schema"], "composer-sources/v1")

    def test_bad_changed_overlay_keeps_last_known_good_registry_with_reason(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "sources.json"
            service = sources_registry.SourceService(target, bundled=BUNDLED, get=ScriptedGet({}))
            target.write_text("{", encoding="utf-8")
            snapshot = service.options()
        self.assertEqual([row["id"] for row in snapshot["sources"]], BUNDLED_IDS)
        self.assertEqual(snapshot["reload"]["state"], "degraded")
        self.assertTrue(snapshot["reload"]["reason"])

    def test_packages_are_data_only_and_resolve_only_current_ids(self):
        service = sources_registry.SourceService(Path("/tmp/not-used"), bundled=BUNDLED, get=ScriptedGet({}))
        policy = {"unavailable_members": "refuse", "paid_requires_confirmation": False,
                  "offline_trial_eligible": False}
        raw = {"package_id": "two-feeds", "label": "Two feeds", "description": "Both bundled feeds.",
               "provenance": "a test", "source_ids": ["google-ai", "deepmind"], "selection_policy": policy}
        package = sources_registry.parse_package(raw, service.snapshot())
        self.assertEqual(package.source_ids, ("google-ai", "deepmind"))
        with self.assertRaises(sources_registry.SourceServiceError):
            sources_registry.parse_package(dict(raw, package_id="bad", source_ids=["missing"]), service.snapshot())


class HtmlExtractionTests(unittest.TestCase):
    def test_native_tier_is_available_without_optional_dependency(self):
        title, description = html_extract.extract("<title>A</title><p>Words</p>", tier="native")
        self.assertEqual(title, "A")
        self.assertIn("Words", description)
        self.assertEqual(html_extract.available_tiers()["native"], "available")

    def test_unknown_tier_is_refused(self):
        with self.assertRaises(html_extract.ExtractionError):
            html_extract.extract("<p>x</p>", tier="not-a-tier")

    def test_html_index_source_can_select_the_optional_trafilatura_tier(self):
        entry = registry.parse_entry({"id": "example-index", "label": "Example index", "kind": "html-index",
                                      "url": "https://example.org/news/", "extraction_tier": "trafilatura",
                                      "discovery": {"allowed_hosts": ["example.org"],
                                                    "allowed_path_prefixes": ["/news/"], "max_candidates": 3}})
        self.assertEqual(entry.extraction_tier, "trafilatura")
        self.assertEqual(entry.to_json()["extraction_tier"], "trafilatura")


if __name__ == "__main__":
    unittest.main()
