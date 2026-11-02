import hashlib
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from composer.job_store import JobStore, SimulatedCrash


def tree_digest(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        digest.update(path.relative_to(root).as_posix().encode())
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


class JobStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "data"
        self.started = threading.Event()
        self.release = threading.Event()

        def worker(job, draft_ready):
            self.started.set()
            draft = {"schema": "composer-edition/v1", "cards": [], "job": job["job"]}
            draft_ready(draft)
            self.release.wait(2)
            return {"status": "ok", "claim_evidence": {"job": job["job"], "draft_sha256": job["draft_sha256"]}}

        self.store = JobStore(self.root, worker=worker, capacity=2, wall_cap_s=5)

    def tearDown(self):
        self.tmp.cleanup()

    def finish(self, accepted):
        self.assertTrue(self.started.wait(1))
        self.release.set()
        return self.store.wait(accepted["job"], 2)

    def test_submit_persists_queued_job_and_capacity_returns_full(self):
        first = self.store.submit({"sources": ["google-ai"], "lens": "x"})
        second = self.store.submit({"sources": ["google-ai"], "lens": "x"})
        self.assertTrue((self.root / "generations" / "g1" / "jobs" / first["job"] / "job.json").is_file())
        self.assertTrue(self.started.wait(1))
        with self.assertRaisesRegex(RuntimeError, "capacity"):
            self.store.submit({"sources": ["google-ai"], "lens": "x"})
        self.release.set()
        self.assertEqual("verified", self.store.wait(first["job"], 2)["phase"])
        self.assertEqual("verified", self.store.wait(second["job"], 2)["phase"])
        self.assertLessEqual(self.store.memo_jobs(), self.store.MEMO_CAP)

    def test_draft_is_visible_before_checker_finishes_and_is_bound_to_job_digest(self):
        accepted = self.store.submit({"sources": ["google-ai"], "lens": "x"})
        self.assertTrue(self.started.wait(1))
        status = self.store.status(accepted["job"])
        self.assertEqual("text_ready_checking", status["phase"])
        self.assertEqual("running", status["verification"]["status"])
        self.assertEqual(accepted["job"], status["result"]["job"])
        self.assertEqual(hashlib.sha256(json.dumps(status["result"], sort_keys=True, separators=(",", ":")).encode()).hexdigest(), status["draft_sha256"])
        self.release.set()
        self.assertEqual("verified", self.store.wait(accepted["job"], 2)["phase"])

    def test_missing_or_mismatched_verdict_binding_is_refused(self):
        for label, evidence in (
            ("missing", {}),
            ("wrong-job", {"job": "job-0000000000000000", "draft_sha256": "0" * 64}),
            ("wrong-digest", {"job": None, "draft_sha256": "0" * 64}),
        ):
            with self.subTest(verdict=label), tempfile.TemporaryDirectory() as temp:
                def worker(job, draft_ready):
                    draft_ready({"schema": "composer-edition/v1", "job": job["job"], "cards": []})
                    bound = dict(evidence)
                    if bound.get("job") is None and label == "wrong-digest":
                        bound["job"] = job["job"]
                    return {"status": "ok", "claim_evidence": bound}

                store = JobStore(Path(temp) / "data", worker=worker)
                accepted = store.submit({"sources": ["google-ai"], "lens": "x"})
                result = store.wait(accepted["job"], 2)
                self.assertEqual("verification_failed", result["phase"])
                self.assertEqual("failed", result["state"])

    def test_watchdog_fails_hung_job_and_releases_capacity(self):
        release = threading.Event()

        def hung(job, draft_ready):
            release.wait(1)
            draft_ready({"schema": "composer-edition/v1", "job": job["job"], "cards": []})
            return {"status": "ok"}

        store = JobStore(Path(self.tmp.name) / "watchdog", worker=hung, capacity=1, wall_cap_s=0.05)
        accepted = store.submit({"sources": ["google-ai"], "lens": "x"})
        result = store.wait(accepted["job"], 1)
        self.assertEqual("compose_failed", result["phase"])
        self.assertEqual("failed", result["state"])
        self.assertEqual([], store.health()["active_jobs"])
        release.set()
        time.sleep(0.1)
        self.assertEqual("compose_failed", store.status(accepted["job"])["phase"])

    def test_save_is_idempotent_and_shelf_marks_unreadable_saved_briefs(self):
        accepted = self.store.submit({"sources": ["google-ai"], "lens": "x"})
        job = self.finish(accepted)
        first = self.store.save(job["job"])
        second = self.store.save(job["job"])
        self.assertEqual(first, second)
        record = self.store.job_path(job["job"]) / "job.json"
        record.write_text("not-json")
        item = self.store.index()["items"][0]
        self.assertEqual(job["job"], item["job"])
        self.assertFalse(item["readable"])
        self.assertEqual("unreadable", item["phase"])

    def test_save_shelf_delete_restore_and_latest_pointer(self):
        accepted = self.store.submit({"sources": ["google-ai"], "lens": "x"})
        job = self.finish(accepted)
        self.assertTrue(self.store.save(job["job"])["saved"])
        self.assertEqual(job["job"], self.store.index()["items"][0]["job"])
        self.assertEqual(job["job"], self.store.latest()["job"])
        self.store.delete(job["job"])
        self.assertEqual([], self.store.index()["items"])
        self.assertIsNone(self.store.latest())
        self.assertTrue((self.root / "generations" / "g1" / "trash" / job["job"] / "trash.json").is_file())
        self.store.restore(job["job"])
        self.assertEqual(job["job"], self.store.latest()["job"])

    def test_retention_is_dry_run_by_default_and_removes_expired_when_applied(self):
        accepted = self.store.submit({"sources": ["google-ai"], "lens": "x"})
        job = self.finish(accepted)
        stale = self.store.job_path(job["job"]) / "job.json"
        record = json.loads(stale.read_text())
        record["finished_at"] = "2000-01-01T00:00:00Z"
        stale.write_text(json.dumps(record))
        self.assertEqual([job["job"]], self.store.retention()["would_trash"])
        self.assertTrue(self.store.job_path(job["job"]).exists())
        self.assertEqual([job["job"]], self.store.retention(apply=True)["trashed"])

    def test_retention_expires_test_jobs_before_regular_unsaved_jobs(self):
        self.release.set()
        regular = self.store.submit({"sources": ["google-ai"], "lens": "x"})
        self.store.wait(regular["job"], 2)
        test_job = self.store.submit({"sources": ["google-ai"], "lens": "x", "test": True})
        self.store.wait(test_job["job"], 2)
        for job_id in (regular["job"], test_job["job"]):
            record = self.store.job_path(job_id) / "job.json"
            document = json.loads(record.read_text())
            document["finished_at"] = "2000-01-01T00:00:00Z" if job_id == test_job["job"] else "2099-01-01T00:00:00Z"
            record.write_text(json.dumps(document))
        self.assertEqual([test_job["job"]], self.store.retention()["would_trash"])

    def test_update_crash_recovery_is_stage_specific_and_preserves_g1_bytes(self):
        for stage in JobStore.MIGRATION_STAGES + JobStore.SWITCH_STAGES:
            with self.subTest(stage=stage):
                root = Path(self.tmp.name) / stage
                store = JobStore(root, worker=lambda *_: {"status": "ok"})
                store._project()
                baseline = tree_digest(store.generation_path("g1"))
                if stage in JobStore.MIGRATION_STAGES:
                    with self.assertRaisesRegex(SimulatedCrash, stage):
                        store.migrate_copy("2", crash_after=stage)
                else:
                    store.migrate_copy("2")
                    with self.assertRaisesRegex(SimulatedCrash, stage):
                        store.switch("g2", crash_after=stage)
                reopened = JobStore(root, worker=lambda *_: {"status": "ok"})
                self.assertEqual(baseline, tree_digest(reopened.generation_path("g1")))
                expected = "g2" if stage in {"pointer_replaced", "pointer_parent_synced", "switch_committed"} else "g1"
                self.assertEqual(expected, reopened.current_generation())
                self.assertFalse((root / "current.tmp").exists())
                self.assertTrue((root / "recovery" / "pairs.json").is_file())

    def test_rollback_exports_post_switch_jobs_and_restores_g1_byte_for_byte(self):
        before = tree_digest(self.store.generation_path("g1"))
        self.store.migrate_copy("2")
        self.store.switch("g2")
        accepted = self.store.submit({"sources": ["google-ai"], "lens": "x"})
        self.finish(accepted)
        result = self.store.rollback()
        self.assertEqual("g1", self.store.current_generation())
        self.assertIn(accepted["job"], result["exported_jobs"])
        self.assertTrue((Path(result["export_directory"]) / accepted["job"] / "job.json").is_file())
        self.assertEqual(before, tree_digest(self.store.generation_path("g1")))


if __name__ == "__main__":
    unittest.main()