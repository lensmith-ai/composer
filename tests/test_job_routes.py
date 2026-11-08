import http.client
import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

from composer import server
from composer.registry import BUNDLED, Registry, read_file


class JobRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.release = threading.Event()

        def worker(job, draft_ready):
            draft_ready({"schema": "composer-edition/v1", "job": job["job"], "cards": []})
            self.release.wait(2)
            return {"status": "ok", "claim_evidence": {"job": job["job"], "draft_sha256": job["draft_sha256"]}}

        self.app = server.App(Registry(read_file(BUNDLED)), lambda: "model", data_root=self.tmp.name, job_worker=worker)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler_for(self.app))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.release.set)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        supplied = headers or {}
        base = {"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json"}
        base.update(supplied)
        if method == "POST" and "Origin" not in supplied:
            base["Origin"] = f"http://127.0.0.1:{self.port}"
        if method == "POST" and "Sec-Fetch-Site" not in supplied:
            base["Sec-Fetch-Site"] = "same-origin"
        if method == "POST" and "X-Composer-CSRF" not in supplied:
            base["X-Composer-CSRF"] = server.CSRF_VALUE
        connection.request(method, path, body=body, headers=base)
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        return response.status, payload

    def compose(self):
        status, payload = self.request("POST", "/compose", json.dumps({"sources": ["google-ai"], "lens": "x"}))
        self.assertEqual(202, status)
        return payload["job"]

    def wait_for_draft(self, job_id):
        for _ in range(100):
            status, job = self.request("GET", "/status/" + job_id)
            self.assertEqual(200, status)
            if job["phase"] == "text_ready_checking":
                return job
            time.sleep(0.01)
        self.fail("job did not reach text_ready_checking")

    def finish(self, job_id):
        self.release.set()
        for _ in range(100):
            _, job = self.request("GET", "/status/" + job_id)
            if job["phase"] in {"verified", "verification_failed", "compose_failed"}:
                return job
            time.sleep(0.01)
        self.fail("job did not finish")

    def test_compose_has_two_route_slots_health_and_bounded_memo(self):
        first = self.compose()
        second = self.compose()
        status, full = self.request("POST", "/compose", json.dumps({"sources": ["google-ai"], "lens": "x"}))
        self.assertEqual(409, status)
        self.assertEqual("compose capacity is full", full["error"])
        status, health = self.request("GET", "/health")
        self.assertEqual(200, status)
        self.assertEqual({"ok", "active_jobs", "active_count", "capacity", "available", "generation", "memo_jobs"},
                         set(health))
        self.assertEqual(2, health["capacity"])
        self.assertEqual(sorted([first, second]), health["active_jobs"])
        self.assertEqual(2, health["active_count"])
        self.assertEqual(0, health["available"])
        self.release.set()
        self.assertEqual("verified", self.finish(first)["phase"])
        self.assertEqual("verified", self.finish(second)["phase"])
        self.assertLessEqual(self.app.jobs.memo_jobs(), self.app.jobs.MEMO_CAP)

    def test_status_serves_live_contract_draft_then_verified(self):
        job_id = self.compose()
        draft = self.wait_for_draft(job_id)
        self.assertEqual("running", draft["state"])
        self.assertEqual("text_ready_checking", draft["phase"])
        self.assertEqual("running", draft["verification"]["status"])
        self.assertEqual(job_id, draft["result"]["job"])
        self.assertIn("draft_sha256", draft)
        self.assertEqual(["queued", "fetching", "synthesizing", "text_ready_checking"],
                         [step["phase"] for step in draft["progress"]])
        verified = self.finish(job_id)
        self.assertEqual("done", verified["state"])
        self.assertEqual("verified", verified["phase"])
        self.assertEqual("verified", verified["progress"][-1]["phase"])
        self.assertEqual({"schema", "job", "state", "phase", "progress", "result", "verification", "receipts", "request", "started_at", "finished_at", "error", "commit", "draft_sha256", "verification_started_at", "lines"}, set(verified))

    def test_status_routes_expose_compose_and_verification_failures(self):
        def compose_failure(job, draft_ready):
            raise RuntimeError("worker failure")

        self.app.jobs.worker = compose_failure
        failed_job = self.compose()
        failed = self.finish(failed_job)
        self.assertEqual("failed", failed["state"])
        self.assertEqual("compose_failed", failed["phase"])
        self.assertEqual("compose_failed", failed["progress"][-1]["phase"])

        def verification_failure(job, draft_ready):
            draft_ready({"schema": "composer-edition/v1", "job": job["job"], "cards": []})
            return {"status": "unsupported", "claim_evidence": {"job": job["job"],
                                                                      "draft_sha256": job["draft_sha256"]}}

        self.app.jobs.worker = verification_failure
        verification_job = self.compose()
        verification_failed = self.finish(verification_job)
        self.assertEqual("done", verification_failed["state"])
        self.assertEqual("verification_failed", verification_failed["phase"])
        self.assertEqual("verification_failed", verification_failed["progress"][-1]["phase"])

    def test_change_routes_refuse_missing_or_bad_guards_before_work(self):
        body = json.dumps({"sources": ["google-ai"], "lens": "x"})
        cases = (
            ("host", {"Host": f"evil.invalid:{self.port}"}),
            ("origin", {"Origin": "https://evil.invalid"}),
            ("fetch-site", {"Sec-Fetch-Site": "cross-site"}),
            ("csrf-missing", {"X-Composer-CSRF": ""}),
            ("csrf-wrong", {"X-Composer-CSRF": "wrong"}),
        )
        for name, headers in cases:
            with self.subTest(guard=name):
                self.assertEqual(403, self.request("POST", "/compose", body, headers)[0])
                self.assertEqual(403, self.request("POST", "/retention", "{}", headers)[0])
        self.assertEqual([], self.app.jobs.health()["active_jobs"])

    def test_save_refuses_mixed_payload_and_is_idempotent(self):
        job_id = self.compose()
        self.wait_for_draft(job_id)
        self.finish(job_id)
        path = "/save/" + job_id
        self.assertEqual(400, self.request("POST", path, json.dumps({"sources": ["google-ai"]}))[0])
        status, first = self.request("POST", path, "{}")
        self.assertEqual(200, status)
        status, second = self.request("POST", path, "{}")
        self.assertEqual(200, status)
        self.assertEqual(first, second)
        status, shelf = self.request("GET", "/shelf")
        self.assertEqual(200, status)
        self.assertEqual(job_id, shelf["items"][0]["job"])
        status, latest = self.request("GET", "/latest")
        self.assertEqual(200, status)
        self.assertEqual(job_id, latest["job"])

    def test_delete_restore_and_latest_pointer_are_real_routes(self):
        job_id = self.compose()
        self.wait_for_draft(job_id)
        self.finish(job_id)
        self.assertEqual(200, self.request("POST", "/save/" + job_id, "{}")[0])
        self.assertEqual(200, self.request("POST", "/delete/" + job_id, "{}")[0])
        self.assertEqual([], self.request("GET", "/shelf")[1]["items"])
        self.assertEqual(404, self.request("GET", "/latest")[0])
        status, restored = self.request("POST", "/restore/" + job_id, "{}")
        self.assertEqual(200, status)
        self.assertEqual(job_id, restored["restored"])
        self.assertEqual(job_id, self.request("GET", "/latest")[1]["job"])

    def test_retention_is_dry_by_default_and_apply_is_explicit_route(self):
        job_id = self.compose()
        self.wait_for_draft(job_id)
        job = self.finish(job_id)
        record = self.app.jobs.job_path(job["job"]) / "job.json"
        doc = json.loads(record.read_text())
        doc["finished_at"] = "2000-01-01T00:00:00Z"
        record.write_text(json.dumps(doc))
        status, dry = self.request("POST", "/retention", "{}")
        self.assertEqual(200, status)
        self.assertTrue(dry["dry_run"])
        self.assertEqual([job_id], dry["would_trash"])
        status, applied = self.request("POST", "/retention", json.dumps({"apply": True}))
        self.assertEqual(200, status)
        self.assertFalse(applied["dry_run"])
        self.assertEqual([job_id], applied["trashed"])

    def test_update_switch_and_rollback_are_real_routes(self):
        status, _ = self.request("POST", "/update/migrate", json.dumps({"schema": "2"}))
        self.assertEqual(200, status)
        status, switched = self.request("POST", "/update/switch", json.dumps({"target": "g2"}))
        self.assertEqual(200, status)
        self.assertEqual("g2", switched["generation"])
        status, rollback = self.request("POST", "/update/rollback", "{}")
        self.assertEqual(200, status)
        self.assertIn("exported_jobs", rollback)
        self.assertEqual("g1", self.app.jobs.current_generation())


if __name__ == "__main__":
    unittest.main()