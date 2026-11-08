"""The progress lines the app page reads: every stage the entry animation names is driven by a real event of the run."""
import http.client
import json
import re
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from composer import pipeline, server, stage_lines
from composer.registry import BUNDLED, Registry, read_file

# the page's own way of reading a line (composer/web/app/composer-entry-transition.js rawStage, and the loom's reader in
# app.js canonicalEventsFromProgress): the stage a line belongs to, 0 to 5, or -1 for a line that is only a note
STAGE_NAMES = ["ACCEPTING BRIEF", "GATHERING SOURCES", "SORTING SIGNALS", "APPLYING LENS", "WEAVING BRIEF", "CHECKING CLAIMS"]


def page_stage(raw: str) -> int:
    raw = raw.lower()
    if re.match(r"^compose started", raw):
        return 0
    if re.match(r"^fetching ", raw):
        return 1
    if re.match(r"^(scanning|sanitizing) |^prompt assembled", raw):
        return 2
    if re.match(r"^synthesizing", raw):
        return 3
    if re.match(r"^synthesis ok", raw):
        return 4
    if re.match(r"^verif", raw):
        return 5
    return -1


class Source:
    def __init__(self, id, label):
        self.id, self.label = id, label


SOURCES = [Source("google-ai", "Google AI blog"), Source("deepmind", "Google DeepMind blog")]


def pipeline_events(log):
    """The events pipeline.compose reports for a run over SOURCES, in its own wording."""
    log("run.started", "compose started · 2 sources · lens: Look for concrete improvements")
    for s, n in zip(SOURCES, (3, 1)):
        log("source.started", f"reading {s.label}")
        log("source.done", f"{s.label} · {n} item{'' if n == 1 else 's'} (ok)")
    log("sanitize.passed", "source text screened · 0 risky strings neutralized")
    log("lens.started", "writing under the lens")
    log("lens.applied", "brief written · 5 insights")
    log("claim.verifying", "checking each claim against the articles it cites")
    log("claim.verified", "checked · 3 supported · 2 partly supported")


class LineMakerTests(unittest.TestCase):
    def lines(self, lens_name="System improvements"):
        make = stage_lines.make_line_maker(SOURCES, lens_name)
        out = []
        pipeline_events(lambda kind, text: out.append(make(kind, text)))
        return out

    def test_every_pipeline_event_becomes_one_text_line(self):
        out = self.lines()
        self.assertEqual(10, len(out))
        for line in out:
            self.assertIsInstance(line, str)
            self.assertNotIn("[object", line)
        self.assertEqual("compose started · 2 sources · lens: System improvements", out[0])
        self.assertEqual(["fetching google-ai…", "scanning google-ai — 3 items (ok)",
                          "fetching deepmind…", "scanning deepmind — 1 items (ok)"], out[1:5])
        self.assertEqual("synthesis ok — 5 items", out[7])

    def test_lines_reach_the_six_stages_in_order(self):
        # the page keeps the highest stage a line has reached (a second source's "fetching" after the first one's
        # "scanning" does not take it back), so the stages it shows are the running highest
        reached, top = [], -1
        for line in self.lines():
            top = max(top, page_stage(line))
            if top not in reached:
                reached.append(top)
        self.assertEqual([0, 1, 2, 3, 4, 5], reached)
        self.assertEqual(STAGE_NAMES[5], STAGE_NAMES[top])

    def test_a_source_that_failed_is_a_note_not_a_scan(self):
        make = stage_lines.make_line_maker(SOURCES)
        line = make("source.done", "Google AI blog · failed: timed out")
        self.assertEqual("google-ai could not be read — failed: timed out", line)
        self.assertEqual(-1, page_stage(line))
        self.assertIsNone(make("source.started", "reading A source it was not given"))

    def test_other_events_pass_through_as_notes(self):
        make = stage_lines.make_line_maker(SOURCES)
        self.assertEqual("dropped 1 quote that copied too much of an article",
                         make("quote.dropped", "dropped 1 quote that copied too much of an article"))
        self.assertIsNone(make("quote.dropped", ""))


class LabelTests(unittest.TestCase):
    """Source labels are what the pipeline's events carry; the page wants ids."""

    def make(self, *pairs):
        return stage_lines.make_line_maker([Source(i, label) for i, label in pairs])

    def test_a_label_that_starts_another_label_does_not_take_its_lines_in_either_order(self):
        for pairs in ((("a", "OpenAI"), ("b", "OpenAI \u00b7 Research")), (("b", "OpenAI \u00b7 Research"), ("a", "OpenAI"))):
            make = self.make(*pairs)
            self.assertEqual("fetching b\u2026", make("source.started", "reading OpenAI \u00b7 Research"))
            self.assertEqual("scanning b \u2014 4 items (ok)", make("source.done", "OpenAI \u00b7 Research \u00b7 4 items (ok)"))
            self.assertEqual("fetching a\u2026", make("source.started", "reading OpenAI"))
            self.assertEqual("scanning a \u2014 2 items (ok)", make("source.done", "OpenAI \u00b7 2 items (ok)"))

    def test_a_failure_keeps_its_own_words_even_when_the_label_has_a_dot(self):
        make = self.make(("b", "OpenAI \u00b7 Research"))
        make("source.started", "reading OpenAI \u00b7 Research")
        self.assertEqual("b could not be read \u2014 failed: timeout",
                         make("source.done", "OpenAI \u00b7 Research \u00b7 failed: timeout"))

    def test_two_sources_with_one_label_each_get_their_own_lines_in_order(self):
        make = self.make(("a", "Same"), ("b", "Same"))
        self.assertEqual("fetching a\u2026", make("source.started", "reading Same"))
        self.assertEqual("scanning a \u2014 1 items (ok)", make("source.done", "Same \u00b7 1 item (ok)"))
        self.assertEqual("fetching b\u2026", make("source.started", "reading Same"))
        self.assertEqual("scanning b \u2014 3 items (ok)", make("source.done", "Same \u00b7 3 items (ok)"))


class PageReaderTests(unittest.TestCase):
    """The lines must satisfy the page's own readers: the regular expressions are read out of app.js and the entry
    animation's script, not copied here."""

    JS_DIR = Path(__file__).resolve().parents[1] / "composer" / "web" / "app"

    def literals(self, name, start, end):
        text = (self.JS_DIR / name).read_text(encoding="utf-8")
        body = text[text.index(start):text.index(end, text.index(start))]
        found = re.findall(r"/(\^[^/\n]*?)/(?=[.)]|\s)", body)
        self.assertTrue(found, f"no regular expressions found in {name}")
        return [re.compile(x, re.I) for x in found]

    def test_the_loom_reader_takes_the_lines_it_draws_from(self):
        regexes = self.literals("app.js", "function canonicalEventsFromProgress", "function prepareLiveStage")
        make = stage_lines.make_line_maker(SOURCES, "System improvements")
        lines = []
        pipeline_events(lambda kind, text: lines.append(make(kind, text)))
        for line in (lines[0], lines[1], lines[2], lines[6], lines[7], lines[8], lines[9]):
            lower = line.lower()
            self.assertTrue(any(r.search(lower) for r in regexes), f"the loom's reader does not take: {line}")
        scanned = [r for r in regexes if r.search(lines[2].lower())]
        self.assertTrue(any(r.match(lines[2].lower()) and r.pattern.count("(") >= 3 for r in scanned),
                        "the scan line must give the loom its source id and item count")

    def test_the_entry_animation_reaches_every_stage_from_the_lines(self):
        regexes = self.literals("composer-entry-transition.js", "function rawStage", "function phaseMark")
        self.assertGreaterEqual(len(regexes), 6)
        make = stage_lines.make_line_maker(SOURCES, "System improvements")
        lines = []
        pipeline_events(lambda kind, text: lines.append(make(kind, text)))
        reached = set()
        for line in lines:
            for i, r in enumerate(regexes):
                if r.search(line.lower()):
                    reached.add(i)
        self.assertEqual(set(range(len(regexes))), reached)


class JobLinesTests(unittest.TestCase):
    """A real server and job store: the job's `lines` carry the run's stages, and its phase records stay objects."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        picked = []

        def compose(**kw):
            picked.extend(kw["sources"])
            make_sources = kw["sources"]
            self.assertTrue(callable(kw["log"]), "the job's worker must give the pipeline a log")
            pipeline_events(kw["log"])
            return {"edition": {"schema": "composer-edition/v1", "cards": [], "sources": [], "lens": "x"},
                    "result": {}, "fetched": {}, "sources": make_sources}

        self.picked = picked
        self.app = server.App(Registry(read_file(BUNDLED)), lambda: "model", data_root=self.tmp.name, compose=compose)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler_for(self.app))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def request(self, method, path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json",
                   "Origin": f"http://127.0.0.1:{self.port}", "Sec-Fetch-Site": "same-origin",
                   "X-Composer-CSRF": server.CSRF_VALUE}
        c.request(method, path, body=body, headers=headers)
        r = c.getresponse()
        out = (r.status, json.loads(r.read()))
        c.close()
        return out

    def test_status_carries_the_run_as_text_lines_and_keeps_phase_records(self):
        status, payload = self.request("POST", "/compose", json.dumps({"sources": ["google-ai", "deepmind"], "lens": "x"}))
        self.assertEqual(202, status)
        job_id = payload["job"]
        for _ in range(200):
            _, job = self.request("GET", "/status/" + job_id)
            if job["phase"] in {"verified", "verification_failed", "compose_failed"}:
                break
            time.sleep(0.02)
        self.assertEqual("verified", job["phase"], job.get("error"))
        # the phase records are objects, as before; the lines are text
        self.assertTrue(all(isinstance(p, dict) for p in job["progress"]))
        lines = job["lines"]
        self.assertTrue(lines and all(isinstance(line, str) for line in lines), lines)
        self.assertNotIn("[object Object]", " ".join(lines))
        self.assertTrue(lines[0].startswith("compose started"), lines[0])
        self.assertEqual("done ✓", lines[-1])
        reached, top = [], -1
        for line in lines:
            top = max(top, page_stage(line))
            if top not in reached:
                reached.append(top)
        self.assertEqual([0, 1, 2, 3, 4, 5], reached, [(page_stage(line), line) for line in lines])
        # the lines name the sources by id, which is what the page draws its loom from
        self.assertIn("fetching google-ai…", lines)
        self.assertIn("fetching deepmind…", lines)

    def test_a_check_that_did_not_pass_does_not_end_on_done(self):
        def worker(job, draft_ready):
            self.app.jobs.note(job["job"], "compose started \u00b7 1 source \u00b7 lens: x")
            draft_ready({"schema": "composer-edition/v1", "job": job["job"], "cards": []})
            return {"status": "unsupported", "claim_evidence": {"job": job["job"], "draft_sha256": job["draft_sha256"]}}

        self.app.jobs.worker = worker
        _, payload = self.request("POST", "/compose", json.dumps({"sources": ["google-ai"], "lens": "x"}))
        for _ in range(200):
            _, job = self.request("GET", "/status/" + payload["job"])
            if job["phase"] in {"verified", "verification_failed", "compose_failed"}:
                break
            time.sleep(0.02)
        self.assertEqual("verification_failed", job["phase"])
        self.assertNotIn("done \u2713", job["lines"])

    def test_a_finished_job_takes_no_more_lines(self):
        status, payload = self.request("POST", "/compose", json.dumps({"sources": ["google-ai"], "lens": "x"}))
        job_id = payload["job"]
        for _ in range(200):
            _, job = self.request("GET", "/status/" + job_id)
            if job["phase"] == "verified":
                break
            time.sleep(0.02)
        before = list(job["lines"])
        self.app.jobs.note(job_id, "late line")
        _, again = self.request("GET", "/status/" + job_id)
        self.assertEqual(before, again["lines"])


if __name__ == "__main__":
    unittest.main()
