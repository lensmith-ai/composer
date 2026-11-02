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


if __name__ == "__main__":
    unittest.main()
