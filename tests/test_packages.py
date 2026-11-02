"""Source packages: the picker's package chips, loaded from data the way the page reads them.

/data/options.json carries `packages` (each package's policy and its members' state now) and
`registry_health.packages`; the page draws a chip per package and applies its sources on a tap."""
import json
import tempfile
import unittest
from pathlib import Path

from composer import server, sources_registry
from composer.registry import BUNDLED

from helpers import ROOT, ScriptedGet

POLICY = {"unavailable_members": "refuse", "paid_requires_confirmation": False, "offline_trial_eligible": False}


def package(package_id, source_ids, **over):
    raw = {"package_id": package_id, "label": package_id.replace("-", " ").title(), "description": "A test set.",
           "provenance": "a test", "source_ids": source_ids, "selection_policy": dict(POLICY)}
    raw.update(over)
    return raw


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.packages_file = self.dir / "packages.json"
        self.service = sources_registry.SourceService(
            self.dir / "sources.json", bundled=BUNDLED, get=ScriptedGet({}),
            packages=sources_registry.PackageService(self.packages_file))
        self.app = server.App(self.service.snapshot(), lambda: "model", source_service=self.service,
                              data_root=self.dir / "data")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, packages):
        self.packages_file.write_text(json.dumps({"schema": "source-packages/v1", "packages": packages}))

    def test_the_bundled_package_reaches_the_page_options(self):
        options = self.app.options()
        self.assertEqual(list(options["packages"]), ["ai-labs"])
        chip = options["packages"]["ai-labs"]
        self.assertEqual(chip["label"], "AI labs")
        self.assertEqual(chip["selection_policy"]["unavailable_members"], "refuse")
        self.assertEqual([(m["source_id"], m["status"]) for m in chip["members"]],
                         [("google-ai", "available"), ("deepmind", "available")])
        self.assertFalse(options["registry_health"]["packages"]["degraded"])

    def test_your_own_packages_load_without_a_restart_and_a_bad_one_is_set_aside(self):
        self.write([package("both-blogs", ["deepmind", "google-ai"]),
                    package("broken", ["google-ai", "not-a-source"])])
        options = self.app.options()
        self.assertEqual(sorted(options["packages"]), ["ai-labs", "both-blogs"])
        health = options["registry_health"]["packages"]
        self.assertTrue(health["degraded"])
        self.assertIn("broken", health["refused_packages"])
        self.assertIn("not-a-source", health["error"])
        # a file that cannot be read keeps the last good set and says so
        self.packages_file.write_text("{")
        options = self.app.options()
        self.assertEqual(sorted(options["packages"]), ["ai-labs", "both-blogs"])
        self.assertTrue(options["registry_health"]["packages"]["degraded"])
        self.assertIn("not valid JSON", options["registry_health"]["packages"]["error"])

    def test_member_state_follows_the_registry(self):
        (self.dir / "sources.json").write_text(json.dumps({"schema": "composer-sources/v1", "sources": [
            {"id": "deepmind", "label": "Google DeepMind blog", "kind": "rss-or-atom",
             "url": "https://deepmind.google/blog/rss.xml", "available": False, "reason": "paused for a test"}]}))
        chip = self.app.options()["packages"]["ai-labs"]
        self.assertEqual([(m["source_id"], m["status"]) for m in chip["members"]],
                         [("google-ai", "available"), ("deepmind", "unavailable")])

    def test_a_package_is_only_a_suggestion(self):
        # compose requests name sources; a package id is not a source
        checked, refused = self.app._compose_request(json.dumps({"sources": ["ai-labs"], "lens": "x"}).encode(),
                                                     set())
        self.assertIsNone(checked)
        self.assertEqual(refused[0], 400)

    def test_the_shape_is_checked(self):
        bad = [({"package_id": "x"}, "needs exactly"), (package("Bad Id", ["google-ai"]), "package id"),
               (package("x", ["google-ai", "google-ai"]), "twice"),
               (package("x", ["google-ai"], selection_policy=dict(POLICY, unavailable_members="maybe")),
                "unavailable_members")]
        for raw, words in bad:
            with self.subTest(raw=raw):
                with self.assertRaises(sources_registry.SourceServiceError) as cm:
                    sources_registry.parse_package(raw)
                self.assertIn(words, str(cm.exception))


class PublicSourcesOnlyTests(unittest.TestCase):
    """Every package that ships names only sources that ship, all of them public feeds (test_banned scans the
    package text itself for names that must not be published)."""

    def test_bundled_packages_name_only_bundled_sources(self):
        packages = json.loads((ROOT / "composer" / "packages.json").read_text())["packages"]
        sources = {s["id"]: s for s in json.loads((ROOT / "composer" / "sources.json").read_text())["sources"]}
        for item in packages:
            sources_registry.parse_package(item)
            for source_id in item["source_ids"]:
                self.assertIn(source_id, sources)
                self.assertRegex(sources[source_id]["url"], r"^https://")


if __name__ == "__main__":
    unittest.main()
