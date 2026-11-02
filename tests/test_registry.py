import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from composer import registry
from composer.registry import Registry, RegistryError, parse_entry

from helpers import ROOT

DEFAULT_IDS = ("google-ai", "deepmind", "huggingface", "microsoft-research", "pytorch", "arxiv-cs-ai")
DEFAULT_URLS = {
    "google-ai": "https://blog.google/innovation-and-ai/technology/ai/rss/",
    "deepmind": "https://deepmind.google/blog/rss.xml",
    "huggingface": "https://huggingface.co/blog/feed.xml",
    "microsoft-research": "https://www.microsoft.com/en-us/research/blog/feed/",
    "pytorch": "https://pytorch.org/blog/feed/",
    "arxiv-cs-ai": "https://rss.arxiv.org/rss/cs.AI",
}


class BundledTests(unittest.TestCase):
    def test_bundled_sources_are_the_six_public_feeds(self):
        with tempfile.TemporaryDirectory() as d, mock.patch("pathlib.Path.cwd", return_value=Path(d)), \
                mock.patch.dict(os.environ, {"COMPOSER_SOURCES": ""}):
            reg = Registry.load()
        self.assertEqual(reg.ids, DEFAULT_IDS)
        self.assertEqual({sid: reg.get(sid).url for sid in reg.ids}, DEFAULT_URLS)
        for sid in reg.ids:
            self.assertEqual(reg.get(sid).kind, "rss-or-atom", sid)

    def test_no_bundled_source_comes_from_a_publisher_that_opted_out(self):
        # These publishers' terms or robots.txt opt out of automated or AI use; a default must never point at them.
        denied = ("technologyreview.com", "machinelearning.apple.com", "bair.berkeley.edu")
        raw = (ROOT / "composer" / "sources.json").read_text(encoding="utf-8").lower()
        for host in denied:
            self.assertNotIn(host, raw)

    def test_example_file_is_valid(self):
        entries = registry.read_file(ROOT / "examples" / "composer-sources.example.json")
        self.assertEqual({e.kind for e in entries}, set(registry.KINDS))


class EntryTests(unittest.TestCase):
    def ok(self, **over):
        raw = {"id": "my-feed", "label": "My feed", "kind": "rss-or-atom", "url": "https://example.org/feed.xml"}
        raw.update(over)
        return parse_entry(raw)

    def test_good_entry(self):
        e = self.ok()
        self.assertEqual((e.id, e.max_items), ("my-feed", 5))

    def test_refusals(self):
        for over in ({"id": "Bad Id"}, {"kind": "python"}, {"url": "http://example.org/feed"},
                     {"url": "https://u:p@example.org/feed"}, {"max_items": 99}, {"max_items": True},
                     {"label": ""}, {"extra": 1}, {"discovery": {"allowed_hosts": ["x"]}}):
            with self.subTest(over=over), self.assertRaises(RegistryError):
                self.ok(**over)

    def test_html_index_needs_discovery(self):
        with self.assertRaises(RegistryError):
            self.ok(kind="html-index")
        e = self.ok(kind="html-index", discovery={"allowed_hosts": ["example.org"],
                                                  "allowed_path_prefixes": ["/news/"], "max_candidates": 10})
        self.assertEqual(e.discovery["allowed_hosts"], ["example.org"])


class LocalFileTests(unittest.TestCase):
    def test_add_then_load_merges_and_overrides(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "mine.json"
            registry.add_to_file(path, parse_entry({"id": "my-feed", "label": "My feed", "kind": "rss-or-atom",
                                                    "url": "https://example.org/feed.xml"}))
            registry.add_to_file(path, parse_entry({"id": "deepmind", "label": "DeepMind (mine)",
                                                    "kind": "rss-or-atom", "url": "https://example.org/dm.xml"}))
            doc = json.loads(path.read_text())
            self.assertEqual(doc["schema"], "composer-sources/v1")
            reg = Registry.load(str(path))
        self.assertEqual(reg.ids, DEFAULT_IDS + ("my-feed",))
        self.assertEqual(reg.get("deepmind").label, "DeepMind (mine)")

    def test_env_and_cwd_default(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / registry.LOCAL_DEFAULT
            registry.add_to_file(p, parse_entry({"id": "x1", "label": "X", "kind": "rss-or-atom",
                                                 "url": "https://example.org/x.xml"}))
            with mock.patch("pathlib.Path.cwd", return_value=Path(d)), mock.patch.dict(os.environ, {"COMPOSER_SOURCES": ""}):
                self.assertIn("x1", Registry.load().ids)
            with mock.patch.dict(os.environ, {"COMPOSER_SOURCES": str(p)}):
                self.assertIn("x1", Registry.load().ids)

    def test_unknown_source_and_bad_file(self):
        reg = Registry(registry.read_file(registry.BUNDLED))
        with self.assertRaisesRegex(RegistryError, "known sources: " + ", ".join(DEFAULT_IDS)):
            reg.pick(["nope"])
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.json"
            bad.write_text("{")
            with self.assertRaises(RegistryError):
                registry.read_file(bad)
            dup = Path(d) / "dup.json"
            entry = {"id": "a", "label": "A", "kind": "rss-or-atom", "url": "https://example.org/a"}
            dup.write_text(json.dumps({"schema": registry.SCHEMA, "sources": [entry, entry]}))
            with self.assertRaisesRegex(RegistryError, "duplicate"):
                registry.read_file(dup)


if __name__ == "__main__":
    unittest.main()
