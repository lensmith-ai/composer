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

    def test_every_console_error_counts_and_none_is_set_aside(self):
        # a refusal the page causes reads exactly like the one a WebKit screenshot causes, so no message may be
        # excused by its text or its timing: every console error goes into page_health
        flow = (STRANGER / "browser_flow.mjs").read_text(encoding="utf-8")
        handlers = re.findall(r"page\.on\('console', \(m\) => (.+)\);", flow)
        self.assertEqual(handlers, ["{ if (m.type() === 'error') consoleErrors.push(`[${step}] ${m.text().slice(0, 200)}`); }"])
        for word in ("SHOT_STYLE", "setAside", "screenshot_refusals", "excused"):
            self.assertNotIn(word, flow)
        self.assertFalse((STRANGER / "screenshot_refusals.mjs").exists())

    def test_webkit_takes_no_screenshot_before_page_health_is_counted(self):
        flow = (STRANGER / "browser_flow.mjs").read_text(encoding="utf-8")
        shot = flow[flow.index("const shot = async"):flow.index("const rec = async")]
        self.assertLess(shot.index("if (engine === 'webkit' && !healthRecorded) return '';"),
                        shot.index("page.screenshot"))
        finish = flow[flow.index("async function finish()"):]
        counted = finish.index("if (consoleErrors.length) problems.push(")
        self.assertLess(counted, finish.index("healthRecorded = true;"))
        self.assertLess(finish.index("healthRecorded = true;"), finish.index("await rec('page_health'"))
        self.assertEqual(flow.count("healthRecorded = true"), 1)

    def test_the_flow_lets_a_page_finish_loading_before_it_leaves(self):
        # WebKit reports a request cut off by the test's own navigation as a page error; every navigation after the
        # first one in a browser run goes through go() (or settle() before a reload)
        flow = (STRANGER / "browser_flow.mjs").read_text(encoding="utf-8")
        combo = flow[flow.index("async function combo("):flow.index("async function finish()")]
        self.assertIn("const settle = async () => { await page.waitForLoadState('networkidle'", combo)
        gotos = re.findall(r"page\.goto\((.{0,40})", combo)
        self.assertEqual(len(gotos), 2, gotos)  # the first visit, and go() itself
        self.assertIn("base + '/'", gotos[1] if "url" in gotos[0] else gotos[0])
        reload_at = combo.index("page.reload(")
        self.assertIn("await settle();", combo[reload_at - 40:reload_at])

    def test_the_clean_machine_gets_every_file_its_sha256sums_names(self):
        run = (STRANGER / "run.sh").read_text(encoding="utf-8")
        self.assertIn('for f in "$RELDIR"/*; do docker cp "$f" "$NAME:$TH/downloads/"; done', run)


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
