"""The scheduler's daily seal re-check of every saved brief, and the daily brief with no model provider key."""
import json
import unittest
from datetime import datetime, timezone
from unittest import mock

from install_helpers import FAKE_KEY, fake_home

from composer import cli, seal, settings as S
from composer.job_store import JobStore
from composer.scheduler import Scheduler

CFG = {"schedule": {"enabled": True, "time": "07:00", "timezone": "UTC", "sources": ["google-ai"], "lens": "daily",
                    "insights": 5}, "backup": {"weekly": False, "keep": 8}, "seals": {"daily": True}}


def at(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


class Store:
    def __init__(self):
        self.submitted = []

    def submit(self, request):
        self.submitted.append(request)
        return {"job": f"job-{len(self.submitted):016x}"}


def saved_briefs(data, n=2, seal_value="abc"):
    def worker(job, draft_ready):
        draft_ready({"lens": "x", "cards": [], "check": {"seal": seal_value}})
        return {"status": "ok", "claim_evidence": {"job": job["job"], "draft_sha256": job["draft_sha256"]}}
    store = JobStore(data, worker=worker)
    jobs = []
    for _ in range(n):
        job = store.submit({"sources": ["google-ai"], "lens": "x", "insights": 3})["job"]
        store.wait(job, 10)
        store.save(job)
        store.write_artifact(job, "check.json", {"claim_evidence": {"verification": {"seal": {"value": seal_value}}}})
        jobs.append(job)
    return jobs


class DailySealTests(unittest.TestCase):
    def test_once_a_day_every_saved_brief_is_reverified_and_the_result_logged(self):
        with fake_home() as home:
            data = home / "data"
            S.generation_dir(data)
            jobs = saved_briefs(data)
            seen, logs = [], []
            clock = {"now": at("2026-11-02 00:10")}
            cfg = dict(CFG, schedule=dict(CFG["schedule"], enabled=False))

            def check():
                return seal.recheck_saved(data, verify=lambda evidence: seen.append(evidence) or True)
            sched = Scheduler(data, cfg, Store(), clock=lambda: clock["now"], log=logs.append, seal_check=check)
            sched.tick()
            sched.tick()
            self.assertEqual(len(seen), 2)  # two briefs, once
            self.assertEqual(sched.state()["last_seal_day"], "2026-11-02")
            self.assertIn("2 saved brief(s) re-verified", sched.state()["last_seal_outcome"])
            self.assertIn("daily seal re-check 2026-11-02: 2 saved brief(s) re-verified", logs[-1])
            self.assertEqual(sched.status()["last_seal_outcome"], sched.state()["last_seal_outcome"])
            # the next day, a brief edited after it was checked fails the check, and the log says which
            path = data / "generations" / "g1" / "jobs" / jobs[0] / "job.json"
            record = json.loads(path.read_text())
            record["result"]["lens"] = "changed after the check"
            path.write_text(json.dumps(record))
            clock["now"] = at("2026-11-03 00:01")
            sched.tick()
            self.assertTrue(sched.state()["last_seal_outcome"].startswith("FAILED:"))
            self.assertIn(jobs[0], logs[-1])

    def test_a_check_that_cannot_run_is_logged_not_raised_and_it_can_be_turned_off(self):
        with fake_home() as home:
            logs = []

            def broken():
                raise seal.SealError("claim-seal is not installed")
            sched = Scheduler(home, dict(CFG, schedule=dict(CFG["schedule"], enabled=False)), Store(),
                              clock=lambda: at("2026-11-02 08:00"), log=logs.append, seal_check=broken)
            sched.tick()
            self.assertEqual(sched.state()["last_seal_outcome"], "could not run: claim-seal is not installed")
            off = Scheduler(home / "other", dict(CFG, seals={"daily": False}), Store(),
                            clock=lambda: at("2026-11-02 08:00"), log=logs.append,
                            seal_check=lambda: self.fail("ran while turned off"), model_ready=lambda: None)
            (home / "other").mkdir()
            off.tick()
            self.assertNotIn("last_seal_day", off.state())


class NoKeyTests(unittest.TestCase):
    def test_the_daily_brief_skips_with_the_reason_when_no_key_is_set(self):
        with fake_home() as home, mock.patch("composer.providers._KEY_FILE", None):
            data = home / "data"
            S.generation_dir(data)
            logs, store = [], Store()
            sched = cli.build_scheduler(data, dict(S.DEFAULTS, schedule=CFG["schedule"]), {}, store=store,
                                        clock=lambda: at("2026-11-02 07:05"), log=logs.append)
            self.assertEqual(sched.tick(), "skipped")
            self.assertEqual(store.submitted, [])  # no job, so no "failed: ProviderError" later
            outcome = sched.state()["last_outcome"]
            self.assertEqual(outcome, "skipped: Composer needs a model key to write a brief. "
                                      "Run ./setup.sh --reconfigure provider.")
            self.assertTrue(any(line.endswith("brief: Composer needs a model key to write a brief. Run ./setup.sh "
                                              "--reconfigure provider.") for line in logs), logs)
            self.assertIsNone(sched.tick())  # the slot is used up: one line, not one every 30 seconds
            # the same scheduler also ran the daily seal re-check (nothing saved yet)
            self.assertEqual(sched.state()["last_seal_outcome"], "0 saved brief(s) re-verified")

    def test_with_a_key_the_brief_starts(self):
        with fake_home(ANTHROPIC_API_KEY=FAKE_KEY) as home:
            data = home / "data"
            S.generation_dir(data)
            store = Store()
            sched = cli.build_scheduler(data, dict(S.DEFAULTS, schedule=CFG["schedule"]),
                                        {}, store=store,
                                        clock=lambda: at("2026-11-02 07:05"), log=lambda *_: None)
            self.assertEqual(sched.tick(), "started")
            self.assertEqual(len(store.submitted), 1)


if __name__ == "__main__":
    unittest.main()
