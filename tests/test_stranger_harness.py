"""The stranger test (tests/stranger/) runs outside the unit suite, on a built release; these checks keep two of its
expectations honest without running it."""
import json
import re
import unittest

from helpers import ROOT

STRANGER = ROOT / "tests" / "stranger"


class StrangerHarnessTests(unittest.TestCase):
    def test_the_brief_link_is_opened_before_the_brief_is_moved_to_the_trash(self):
        flow = (STRANGER / "browser_flow.mjs").read_text(encoding="utf-8")
        link, trash = flow.index("check('brief_link'"), flow.index("check('trash'")
        self.assertLess(link, trash, "the flow trashes the only saved brief, then expects its link to open it")

    def test_the_expected_default_sources_match_the_bundled_file(self):
        run = (STRANGER / "run.sh").read_text(encoding="utf-8")
        expect = int(re.search(r"\$\{STRANGER_EXPECT_SOURCES:-(\d+)\}", run).group(1))
        bundled = json.loads((ROOT / "composer" / "sources.json").read_text(encoding="utf-8"))["sources"]
        self.assertEqual(expect, len(bundled))
        self.assertEqual(expect, 6)

    def test_no_early_exit_grep_reads_a_tar_listing_under_pipefail(self):
        # `tar -tzf f | grep -q` fails on SIGPIPE under pipefail even when the file is there
        run = (STRANGER / "run.sh").read_text(encoding="utf-8")
        self.assertIn("set -uo pipefail", run)
        self.assertIsNone(re.search(r"tar -t[a-z]*f [^|]*\|\s*grep -q", run))

    def test_update_and_rollback_get_the_local_feed_settings(self):
        # update and rollback run the new version's doctor, which checks the local feeds the test set up
        inside = (STRANGER / "in_container.sh").read_text(encoding="utf-8")
        for command in ("composer update --from-file", "composer rollback"):
            line = next(x for x in inside.splitlines() if command in x and "as_tester" in x)
            self.assertIn("$FIXENV", line)

    def test_only_webkits_screenshot_refusals_are_set_aside_one_per_screenshot(self):
        flow = (STRANGER / "browser_flow.mjs").read_text(encoding="utf-8")
        self.assertIn("engine === 'webkit' && SHOT_STYLE.test(m.text())", flow)
        self.assertIn("Math.min(shotStyleRefusals.length, shotNo)", flow)
        self.assertIn("consoleErrors.push(...shotStyleRefusals.slice(excused))", flow)


class BrowserFixtureTests(unittest.TestCase):
    def test_every_bundled_source_reads_a_local_feed(self):
        # the browser flow composes with the default sources and no internet: each bundled id must be overridden
        fixture = (ROOT / "tests" / "browser" / "fixture_app.py").read_text(encoding="utf-8")
        self.assertIn("bundled = [e.id for e in read_file(BUNDLED)]", fixture)
        n = len(json.loads((ROOT / "composer" / "sources.json").read_text(encoding="utf-8"))["sources"])
        letters = re.search(r'letters = "([a-z]+)"', fixture).group(1)
        self.assertGreaterEqual(len(letters), n)
        for letter in letters[:n]:
            self.assertTrue(f'"/lab-{letter}/feed.xml"' in fixture or letter in re.search(r'for _letter in "([a-z]+)"',
                                                                                           fixture).group(1), letter)


if __name__ == "__main__":
    unittest.main()
