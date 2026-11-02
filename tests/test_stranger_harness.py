"""The stranger test (tests/stranger/) runs outside the unit suite, on a built release; these checks keep two of its
expectations honest without running it."""
import json
import os
import re
import shutil
import subprocess
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

    def test_the_flow_counts_refusals_through_the_quota(self):
        flow = (STRANGER / "browser_flow.mjs").read_text(encoding="utf-8")
        self.assertIn("if (!refusals.take(m.text())) consoleErrors.push(", flow)
        shot = flow[flow.index("const shot = async"):flow.index("const rec = async")]
        self.assertLess(shot.index("refusals.begin(page.frames().length)"), shot.index("page.screenshot"))
        self.assertLess(shot.index("page.screenshot"), shot.index("refusals.end()"))

    @unittest.skipUnless(shutil.which("node") or os.environ.get("COMPOSER_REQUIRE_NODE") == "1",
                         "node is not installed (the stranger test runs on node); CI's Linux jobs require it")
    def test_at_most_one_refusal_per_frame_of_each_screenshot_is_set_aside(self):
        self.assertTrue(shutil.which("node"), "COMPOSER_REQUIRE_NODE=1 but there is no node on PATH")
        refusal = ("Refused to apply a stylesheet because its hash, its nonce, or 'unsafe-inline' does not appear in "
                   "the style-src directive of the Content Security Policy.")
        script = """
import { screenshotRefusals } from %s;
const r = process.argv[1];
const out = {};
const w = screenshotRefusals('webkit');
out.outside = w.take(r);                                   // no screenshot: the page's own
w.begin(1); out.one = [w.take(r), w.take(r)]; w.end();     // one frame: the second is the page's own
w.begin(2); out.two = [w.take(r), w.take(r), w.take(r)]; w.end();
w.begin(1); out.other = w.take('Refused to load the script'); out.after = w.take(r); w.end();
out.ended = w.take(r);
out.setAside = w.setAside;
const c = screenshotRefusals('chromium');
c.begin(1); out.chromium = c.take(r); c.end();
console.log(JSON.stringify(out));
""" % json.dumps((STRANGER / "screenshot_refusals.mjs").as_uri())
        run = subprocess.run(["node", "--input-type=module", "-e", script, refusal], capture_output=True, text=True,
                             timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        got = json.loads(run.stdout)
        self.assertEqual(got, {"outside": False, "one": [True, False], "two": [True, True, False], "other": False,
                               "after": True, "ended": False, "setAside": 4, "chromium": False})

    def test_the_clean_machine_gets_every_file_its_sha256sums_names(self):
        run = (STRANGER / "run.sh").read_text(encoding="utf-8")
        self.assertIn('for f in "$RELDIR"/*; do docker cp "$f" "$NAME:$TH/downloads/"; done', run)


class NodeGuardInCITests(unittest.TestCase):
    def test_ci_runs_the_node_checks_on_linux_instead_of_skipping_them(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("COMPOSER_REQUIRE_NODE: ${{ matrix.os == 'ubuntu-latest' && '1' || '' }}", ci)
        self.assertIn("os: [ubuntu-latest, macos-14, windows-latest]", ci)


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
