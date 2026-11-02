"""The shelf index at /data/index.json: what the app page's drawer, rejoin note and lens counts read.

It is rewritten (whole, by a replace) on every change to the store: a compose starting and finishing, save, delete
(to the trash), restore, the retention sweep, and at start. Only an allow list of fields is in it."""
import http.client
import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

from composer import server, shelf_index
from composer.job_store import JobStore
from composer.registry import BUNDLED, Registry, read_file


ENTRY_KEYS = {"job", "readable", "state", "phase", "title", "lens", "sources", "voice", "started_at", "finished_at",
              "composed_at", "items", "words", "audio", "audio_file", "test_job", "commit", "progress"}
SECRET = "PRIVATE-MARKER-7f3a"  # stands for a key; not key-shaped, so the banned-text test stays quiet


def edition(job_id: str) -> dict:
    return {"schema": "composer-edition/v1", "job": job_id, "lens": "Plain",
            "cards": [{"insight": "Harbor Lab maps its tide sensors in public, all forty of them along the coast",
                       "why": "w", "details": [], "citations": [], "state": "supported"},
                      {"insight": "A second card", "why": "w", "details": [], "citations": [], "state": "supported"}],
            "connection": {"headline": "Across the sources, sensors", "confidence": "low", "why": ""},
            "transcript": "one two three four five"}


class ShelfIndexRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "data"
        self.release = threading.Event()
        self.start_app()

    def worker(self, job, draft_ready):
        draft_ready(edition(job["job"]))
        self.release.wait(5)
        return {"status": "ok", "claim_evidence": {"job": job["job"], "draft_sha256": job["draft_sha256"]}}

    def start_app(self):
        self.app = server.App(Registry(read_file(BUNDLED)), lambda: "model", data_root=self.root,
                              job_worker=self.worker)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler_for(self.app))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.release.set)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def request(self, method, path, body=None, raw=False):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json"}
        if method == "POST":
            headers.update({"Origin": f"http://127.0.0.1:{self.port}", "Sec-Fetch-Site": "same-origin",
                            "X-Composer-CSRF": server.CSRF_VALUE})
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        connection.close()
        if raw:
            return response, payload
        return response.status, json.loads(payload)

    def index(self):
        status, doc = self.request("GET", "/data/index.json")
        self.assertEqual(200, status)
        return doc

    def entry(self, job_id):
        found = [b for b in self.index()["briefs"] if b["job"] == job_id]
        return found[0] if found else None

    def compose(self, lens="x"):
        status, payload = self.request("POST", "/compose", json.dumps({"sources": ["google-ai"], "lens": lens}))
        self.assertEqual(202, status, payload)
        return payload["job"]

    def finish(self, job_id):
        self.release.set()
        self.app.jobs.wait(job_id, 5)

    def test_the_index_is_served_on_a_fresh_store_with_the_data_headers(self):
        response, body = self.request("GET", "/data/index.json", raw=True)
        self.assertEqual(200, response.status)
        options, _ = self.request("GET", "/data/options.json", raw=True)
        for name in ("Content-Type", "Cache-Control", "X-Content-Type-Options", "Referrer-Policy", "X-Frame-Options"):
            self.assertEqual(options.getheader(name), response.getheader(name), name)
        doc = json.loads(body)
        self.assertEqual("brief-index/v0", doc["schema"])
        self.assertEqual(0, doc["count"])
        self.assertEqual([], doc["briefs"])

    def test_a_running_compose_is_listed_for_the_rejoin_note_then_done(self):
        job_id = self.compose()
        running = self.entry(job_id)
        self.assertIsNotNone(running, "a compose that started is not in the index")
        self.assertEqual("running", running["state"])
        self.assertTrue(running["readable"])
        self.finish(job_id)
        done = self.entry(job_id)
        self.assertEqual("done", done["state"])
        self.assertEqual("verified", done["phase"])
        self.assertEqual("Harbor Lab maps its tide sensors in…", done["title"])
        self.assertEqual(2, done["items"])
        self.assertEqual(5, done["words"])
        self.assertEqual(["google-ai"], done["sources"])
        self.assertEqual("x", done["lens"])
        self.assertEqual("unsaved", done["commit"]["state"])
        self.assertIsNotNone(done["composed_at"])
        self.assertEqual(["queued", "fetching", "synthesizing", "text_ready_checking", "verified"], done["progress"])
        self.assertFalse(done["audio"])
        self.assertEqual(ENTRY_KEYS, set(done))

    def test_save_delete_restore_and_page_buttons_each_rewrite_the_index(self):
        job_id = self.compose()
        self.finish(job_id)
        status, saved = self.request("POST", f"/save/{job_id}", "{}")
        self.assertEqual(200, status, saved)
        self.assertEqual("saved", self.entry(job_id)["commit"]["state"])
        self.assertEqual(saved["saved_at_utc"], self.entry(job_id)["commit"]["saved_at_utc"])
        self.assertEqual(200, self.request("POST", f"/delete/{job_id}", "{}")[0])
        self.assertIsNone(self.entry(job_id), "a brief in the trash is still on the shelf")
        self.assertEqual(200, self.request("POST", f"/restore/{job_id}", "{}")[0])
        self.assertEqual("saved", self.entry(job_id)["commit"]["state"])
        # the page's own Delete button posts {"delete_job": id} to /compose
        status, deleted = self.request("POST", "/compose", json.dumps({"delete_job": job_id}))
        self.assertEqual((200, {"deleted_job": job_id}), (status, deleted))
        self.assertIsNone(self.entry(job_id))

    def test_the_page_save_button_saves_and_the_drawer_entry_appears(self):
        job_id = self.compose()
        self.finish(job_id)
        status, saved = self.request("POST", "/compose", json.dumps({"save_job": job_id}))
        self.assertEqual(200, status, saved)
        self.assertTrue(saved["saved"])
        self.assertEqual("saved", self.entry(job_id)["commit"]["state"])
        for body in ({"save_job": job_id, "sources": ["google-ai"]}, {"save_job": "../etc"}, {"save_job": 3},
                     {"save_job": job_id, "delete_job": job_id}):
            with self.subTest(body=body):
                self.assertEqual(400, self.request("POST", "/compose", json.dumps(body))[0])
        self.assertEqual(404, self.request("POST", "/compose", json.dumps({"save_job": "job-" + "0" * 16}))[0])

    def test_retention_rewrites_the_index(self):
        job_id = self.compose()
        self.finish(job_id)
        self.assertIsNotNone(self.entry(job_id))
        later = datetime.now(timezone.utc) + timedelta(hours=25)
        result = self.app.jobs.retention(apply=True, now=later)
        self.assertEqual([job_id], result["trashed"])
        self.assertIsNone(self.entry(job_id))

    def test_the_index_is_rebuilt_at_start(self):
        job_id = self.compose()
        self.finish(job_id)
        self.httpd.shutdown()
        self.httpd.server_close()
        path = self.root / "generations" / "g1" / shelf_index.FILE
        path.write_text("stale", encoding="utf-8")
        self.start_app()
        self.assertEqual([job_id], [b["job"] for b in self.index()["briefs"]])
        path.unlink()
        self.start_app()
        self.assertEqual([job_id], [b["job"] for b in self.index()["briefs"]])

    def test_audio_is_reported_only_when_the_file_is_there(self):
        job_id = self.compose()
        self.finish(job_id)
        self.app.jobs.set_audio(job_id, {"state": "ready", "voice": "af_heart", "file": "composer-af_heart.mp3"})
        self.app.jobs.save(job_id)
        self.assertFalse(self.entry(job_id)["audio"])
        (self.app.jobs.job_dir(job_id) / "composer-af_heart.mp3").write_bytes(b"ID3")
        self.app.jobs.save(job_id)
        entry = self.entry(job_id)
        self.assertTrue(entry["audio"])
        self.assertEqual("composer-af_heart.mp3", entry["audio_file"])


class ShelfIndexContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def store(self, worker):
        return JobStore(Path(self.tmp.name) / "data", worker=worker)

    def test_no_private_fields_in_the_index(self):
        def worker(job, draft_ready):
            if job["request"]["lens"] == "fail":
                raise RuntimeError(SECRET)  # an error's text never reaches the index, only its kind
            draft_ready(edition(job["job"]))
            return {"status": "ok", "claim_evidence": {"job": job["job"], "draft_sha256": job["draft_sha256"]}}

        store = self.store(worker)
        job_id = store.submit({"sources": ["google-ai"], "lens": "x", "insights": 3, "api_key": SECRET,
                               "prompt": "the whole prompt", "path": str(store.root)})["job"]
        store.wait(job_id, 5)
        failing = store.submit({"sources": ["google-ai"], "lens": "fail"})["job"]
        store.wait(failing, 5)
        text = (store.generation_path("g1") / shelf_index.FILE).read_text(encoding="utf-8")
        self.assertNotIn(SECRET, text)
        self.assertNotIn(self.tmp.name, text)
        self.assertNotIn("the whole prompt", text)
        doc = json.loads(text)
        self.assertEqual({"schema", "count", "briefs"}, set(doc))
        self.assertEqual(["done", "failed"], sorted(b["state"] for b in doc["briefs"]))
        for brief in doc["briefs"]:
            self.assertLessEqual(set(brief), ENTRY_KEYS | {"error"})
            self.assertEqual({"state", "saved_at_utc", "expires_at_utc"}, set(brief["commit"]))

    def test_a_record_that_will_not_parse_is_listed_as_unreadable(self):
        store = self.store(lambda job, ready: None)
        folder = store.generation_path("g1") / "jobs" / ("job-" + "a" * 16)
        folder.mkdir(parents=True)
        (folder / "job.json").write_text("{not json", encoding="utf-8")
        store.index()  # any read or change of the shelf rewrites it
        brief = json.loads((store.generation_path("g1") / shelf_index.FILE).read_text())["briefs"][0]
        self.assertEqual({"job": "job-" + "a" * 16, "readable": False, "state": "unreadable",
                          "title": "Unreadable brief"}, brief)

    def test_the_index_is_replaced_whole_and_reads_parse_during_changes(self):
        def worker(job, draft_ready):
            draft_ready(edition(job["job"]))
            return {"status": "ok", "claim_evidence": {"job": job["job"], "draft_sha256": job["draft_sha256"]}}

        store = self.store(worker)
        jobs = []
        for _ in range(4):
            job_id = store.submit({"sources": ["google-ai"], "lens": "x"})["job"]
            store.wait(job_id, 5)
            jobs.append(job_id)
        stop = threading.Event()
        bad, reads = [], []

        def reader():
            while not stop.is_set():
                try:
                    json.loads(store.brief_index())
                    reads.append(1)
                except Exception as exc:  # noqa: BLE001 - any failure to read it whole is the finding
                    bad.append(f"{type(exc).__name__}: {exc}")
                    return

        thread = threading.Thread(target=reader)
        thread.start()
        try:
            for _ in range(5):
                for job_id in jobs:
                    store.save(job_id)
                    store.delete(job_id)
                    store.restore(job_id)
        finally:
            stop.set()
            thread.join()
        self.assertEqual([], bad)
        self.assertTrue(reads, "the reader never read the index")
        leftovers = [p.name for p in store.generation_path("g1").iterdir() if p.name.endswith(".tmp")]
        self.assertEqual([], leftovers)


if __name__ == "__main__":
    unittest.main()
