"""What the app page asks the engine for, checked against what the engine answers: a brief opens from its own
link (?job=<id>, with the store's job ids), the page asks no route the engine does not have, and a brief saved from
the page stays saved when the server starts again."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from composer import live_files, server
from composer.job_store import JobStore
from composer.registry import BUNDLED, Registry, read_file

APP_JS = Path(__file__).resolve().parent.parent / "composer" / "web" / "app" / "app.js"


def page_job_pattern() -> re.Pattern:
    found = re.search(r"var JOB_RE=/(.+?)/;", APP_JS.read_text(encoding="utf-8"))
    if not found:
        raise AssertionError("app.js has no JOB_RE")
    return re.compile(found.group(1))


class BriefLinkTests(unittest.TestCase):
    def test_the_page_opens_the_store_job_ids_from_their_link(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = JobStore(Path(tmp.name), worker=lambda job, ready: None)
        job_id = store.submit({"sources": ["google-ai"], "lens": "x"})["job"]
        store.wait(job_id, 5)  # it fails (the worker writes nothing); only its id is used here
        pattern = page_job_pattern()
        self.assertTrue(pattern.match(job_id), f"the page would replay the demo for ?job={job_id}")
        self.assertTrue(live_files.JOB_ID.match(job_id))
        for other in ("2026-11-02-abcdef", "job-123", "../job-0123456789abcdef", "job-0123456789ABCDEF"):
            with self.subTest(other=other):
                self.assertIsNone(pattern.match(other))


class PageRouteTests(unittest.TestCase):
    def test_the_page_asks_for_no_liveness_route(self):
        js = APP_JS.read_text(encoding="utf-8")
        self.assertNotIn("liveness-probe", js)
        # the compose screen learns that the engine answers from /health, which the engine serves
        self.assertIn('fetch("/health",{credentials:"same-origin",cache:"no-store"})', js)


class SaveHoldsTests(unittest.TestCase):
    def test_a_brief_saved_from_the_page_is_still_saved_after_a_restart(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "data"

        def worker(job, draft_ready):
            draft_ready({"schema": "composer-edition/v1", "job": job["job"], "cards": [
                {"insight": "One finding", "why": "w", "details": [], "citations": [], "state": "supported"}]})
            return {"status": "ok", "claim_evidence": {"job": job["job"], "draft_sha256": job["draft_sha256"]}}

        def app():
            return server.App(Registry(read_file(BUNDLED)), lambda: "model", data_root=root, job_worker=worker)

        first = app()
        job_id = first.jobs.submit({"sources": ["google-ai"], "lens": "x"})["job"]
        first.jobs.wait(job_id, 5)
        status, body = first.submit_job({}, json.dumps({"save_job": job_id}).encode())
        self.assertEqual(200, status, body)
        again = app()
        shelf = json.loads(again.jobs.brief_index())
        self.assertEqual([("saved", job_id)], [(b["commit"]["state"], b["job"]) for b in shelf["briefs"]])
        self.assertEqual("saved", again.jobs.status(job_id)["commit"]["state"])


if __name__ == "__main__":
    unittest.main()
