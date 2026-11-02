"""The optional article parser (trafilatura): an install extra pinned by hash, a hash-locked install offered by
setup, and a text-only fallback when it is not installed."""
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

from composer import html_extract, installer, registry, settings as S
from composer.adapters import html_index

from helpers import ROOT, ScriptedGet, fixture
from install_helpers import fake_home


def index_source(tier="trafilatura"):
    return registry.parse_entry({"id": "example-news", "label": "Example news", "kind": "html-index",
                                 "url": "https://example.org/news/", "max_items": 2, "extraction_tier": tier,
                                 "discovery": {"allowed_hosts": ["example.org"], "allowed_path_prefixes": ["/news/"],
                                               "max_candidates": 5}})


def site():
    return ScriptedGet({"https://example.org/news/": fixture("index-page.html"),
                        "https://example.org/news/first-story": fixture("article-1.html"),
                        "https://example.org/news/second-story": fixture("article-2.html")})


class FallbackTests(unittest.TestCase):
    def test_without_the_parser_a_trafilatura_source_is_read_text_only_and_the_receipt_says_so(self):
        with mock.patch.object(html_extract, "trafilatura_installed", return_value=False):
            items, receipt = html_index.fetch(index_source(), site())
        self.assertEqual(receipt["status"], "ok", receipt)
        self.assertTrue(items)
        self.assertEqual(receipt["fetch_tier"], "native")
        self.assertEqual(receipt["fetch_tiers"], {"native": len(items), "trafilatura": 0})
        self.assertIn("not installed", receipt["note"])

    def test_with_the_parser_the_tier_is_recorded_per_article(self):
        fake = mock.Mock()
        fake.extract.return_value = "Text the parser found in the article body."
        with mock.patch.object(html_extract, "trafilatura_installed", return_value=True), \
                mock.patch.dict(sys.modules, {"trafilatura": fake}):
            items, receipt = html_index.fetch(index_source(), site())
        self.assertEqual(receipt["fetch_tier"], "trafilatura")
        self.assertEqual(receipt["fetch_tiers"]["trafilatura"], len(items))
        self.assertEqual(items[0]["description"], "Text the parser found in the article body.")
        self.assertNotIn("note", receipt)

    def test_a_native_source_never_asks_for_the_parser(self):
        with mock.patch.object(html_extract, "trafilatura_installed", side_effect=AssertionError("asked")):
            items, receipt = html_index.fetch(index_source("native"), site())
        self.assertEqual((receipt["status"], receipt["fetch_tier"]), ("ok", "native"))


class PinnedInstallTests(unittest.TestCase):
    def test_there_is_one_install_path_and_it_is_hash_locked_end_to_end(self):
        # no pip extra: an extra pins the parser but lets pip choose the packages it needs, without hashes
        self.assertNotIn("optional-dependencies", (ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        for path in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md")), ROOT / "composer" / "html_extract.py"]:
            self.assertNotIn("lensmith-composer[trafilatura]", path.read_text(encoding="utf-8"), path.name)
        lock = (ROOT / "composer" / html_extract.LOCK).read_text(encoding="utf-8")
        self.assertIn('"extraction-requirements.lock"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        pins = dict(re.findall(r"^([a-z0-9-]+)==(\S+)", lock, re.M))
        self.assertIn("trafilatura", pins)
        for block in re.split(r"\n(?=[a-z])", lock.split("\n", 5)[-1]):
            if block.strip() and not block.startswith("#"):
                self.assertIn("--hash=sha256:", block, block[:60])
        # the closure: every package named as needing another is itself pinned here
        needed_by = set(re.findall(r"#\s+(?:via\s+)?([a-z0-9-]+)\s*$", lock, re.M)) - {"via"}
        self.assertLessEqual(needed_by - {"-r"}, set(pins), needed_by - set(pins))

    def test_install_uses_the_lock_with_hashes_and_wheels_only(self):
        calls = []
        with mock.patch("subprocess.run", side_effect=lambda cmd, **kw: calls.append(cmd)):
            html_extract.install_trafilatura(python="/app/python", log=lambda *_: None)
        self.assertEqual(calls[0][:3], ["/app/python", "-m", "pip"])
        for flag in ("--require-hashes", "--no-deps", "--only-binary", ":all:"):
            self.assertIn(flag, calls[0])
        # the lock shipped next to the module that runs (an installed release reads its own copy, not this folder's)
        self.assertEqual(Path(calls[0][-1]), Path(html_extract.__file__).with_name(html_extract.LOCK))
        self.assertEqual(Path(calls[0][-1]).read_bytes(), (ROOT / "composer" / html_extract.LOCK).read_bytes())


class SetupOfferTests(unittest.TestCase):
    def run_setup(self, home, answers, install):
        path = home.parent / "answers.toml"
        path.write_text(answers, encoding="utf-8")
        target = home / ".lensmith-composer"
        installer.run(home=target, data=None, answers_file=str(path), assume_yes=False, reconfigure=[],
                      data_only=False, out=lambda *_: None, interactive=False, install_parser=install)
        return S.load(target / "data")

    def test_setup_offers_the_parser_and_records_the_choice(self):
        installed = []
        with fake_home() as home, mock.patch.object(html_extract, "trafilatura_installed", return_value=False):
            cfg = self.run_setup(home, "[parser]\ntrafilatura = true\n",
                                 lambda **kw: installed.append(kw.get("env", {}).get("PIP_REQUIRE_VIRTUALENV")))
        self.assertEqual(installed, ["1"])
        self.assertTrue(cfg["extraction"]["trafilatura"])

    def test_a_failed_install_leaves_the_built_in_parser(self):
        def fail(**_kw):
            raise html_extract.ExtractionError("no network")
        with fake_home() as home, mock.patch.object(html_extract, "trafilatura_installed", return_value=False):
            cfg = self.run_setup(home, "[parser]\ntrafilatura = true\n", fail)
        self.assertFalse(cfg["extraction"]["trafilatura"])

    def test_by_default_nothing_is_installed(self):
        with fake_home() as home:
            cfg = self.run_setup(home, "[provider]\nkind = \"anthropic\"\n",
                                 lambda **kw: self.fail("installed without being asked"))
        self.assertFalse(cfg["extraction"]["trafilatura"])
        self.assertIn("parser", installer.SECTIONS)


if __name__ == "__main__":
    unittest.main()
