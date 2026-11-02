"""`composer doctor`: each flag really runs its checks; and the app's own daily scheduler."""
import json
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from helpers import ROOT, fixture
from install_helpers import FAKE_KEY, FakeRender, fake_home

from composer import doctor, installer, narration as N, settings as S
from composer.fetch import Response
from composer.job_store import JobStore
from composer.scheduler import Scheduler, next_slot, slot_for


def install(home: Path, answers: str = "") -> Path:
    target = home / ".lensmith-composer"
    path = None
    if answers:
        path = home.parent / "answers.toml"
        path.write_text(answers, encoding="utf-8")
    installer.run(home=target, data=None, answers_file=str(path) if path else None, assume_yes=not answers,
                  reconfigure=[], data_only=False, out=lambda *_: None, interactive=False)
    return target


class DoctorFlagTests(unittest.TestCase):
    def run_doctor(self, target, **kw):
        lines = []
        rc = doctor.run(target, target / "data", out=lines.append, **kw)
        return rc, lines

    def names(self, lines):
        """Check names as printed ("STATUS name: detail"; a flagged check's name is "flag: what")."""
        out = []
        for ln in lines:
            if ln[:4] in ("PASS", "FAIL", "SKIP"):
                rest = ln[5:]
                parts = rest.split(": ")
                flagged = parts[0] in ("online", "parity")
                out.append(": ".join(parts[:2]) if flagged else parts[0])
        return out

    def test_plain_doctor_runs_no_flagged_check(self):
        with fake_home() as home:
            target = install(home)
            rc, lines = self.run_doctor(target)
            self.assertEqual(rc, 0, "\n".join(lines))
            names = self.names(lines)
            for name in ("python", "manifest", "data", "permissions", "settings", "key", "sources", "narration",
                         "port", "scheduler", "disk"):
                self.assertIn(name, names)
            self.assertFalse([n for n in names if n.startswith(("online", "parity", "seals"))])

    def test_online_calls_the_model_reads_every_source_and_renders(self):
        with fake_home() as home:
            with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": FAKE_KEY}):
                target = install(home, "[provider]\nkind = \"anthropic\"\nkey_from_env = \"ANTHROPIC_API_KEY\"\n"
                                       "[narration]\nenabled = false\n")
            data = target / "data"
            cfg = S.load(data)
            cfg["narration"] = dict(cfg["narration"], enabled=True, engine="kokoro-onnx", voices=list(N.VOICES))
            S.save(data, cfg)
            calls = {"model": [], "get": []}

            def transport(url, headers, body, timeout):
                calls["model"].append((url, headers.get("x-api-key")))
                return 200, json.dumps({"model": "claude-sonnet-5-5", "stop_reason": "end_turn",
                                        "content": [{"type": "text", "text": "OK"}], "usage": {}}).encode()

            def get(url, timeout):
                calls["get"].append(url)
                return Response(url, 200, fixture("feed-rss.xml"))

            render = FakeRender()
            rc, lines = self.run_doctor(target, online=True, transport=transport, get=get, render=render)
            names = self.names(lines)
            self.assertIn("online: model", names)
            self.assertIn("online: source google-ai", names)
            self.assertIn("online: source deepmind", names)
            self.assertIn("online: narration", names)
            self.assertEqual(len(calls["model"]), 1)
            self.assertEqual(calls["model"][0][1], FAKE_KEY)  # the stored key file, read at call time
            self.assertEqual(len(calls["get"]), 2)
            self.assertEqual(len(render.calls), 1)
            self.assertTrue(any(ln.startswith("PASS online: model") for ln in lines), lines)
            self.assertFalse(any(FAKE_KEY in ln for ln in lines))

    def test_parity_runs_a_brief_through_the_real_routes(self):
        with fake_home() as home:
            target = install(home)
            rc, lines = self.run_doctor(target, parity=True)
            self.assertEqual(rc, 0, "\n".join(lines))
            names = self.names(lines)
            for name in ("parity: page", "parity: options", "parity: compose", "parity: brief files",
                         "parity: save and shelf", "parity: text-only", "parity: delete"):
                self.assertIn(name, names)
            self.assertTrue(all(ln.startswith("PASS") for ln in lines if ln[5:].startswith("parity")), lines)

    def test_parity_with_narration_on_checks_the_audio_and_the_script(self):
        with fake_home() as home:
            target = install(home)
            data = target / "data"
            cfg = S.load(data)
            cfg["narration"] = dict(cfg["narration"], enabled=True, engine="kokoro-onnx", voices=["af_heart"])
            S.save(data, cfg)
            rc, lines = self.run_doctor(target, parity=True, render=FakeRender())
            self.assertTrue(any(ln.startswith("PASS parity: narration") for ln in lines), "\n".join(lines))
            rc, lines = self.run_doctor(target, parity=True, render=FakeRender(fail=True))
            self.assertTrue(any(ln.startswith("FAIL parity: narration") for ln in lines), "\n".join(lines))

    def test_seals_reverify_every_saved_brief(self):
        with fake_home() as home:
            target = install(home)
            data = target / "data"

            def worker(job, draft_ready):
                draft_ready({"lens": "x", "cards": [], "check": {"seal": "abc"}})
                return {"status": "ok", "claim_evidence": {"job": job["job"], "draft_sha256": job["draft_sha256"]}}
            store = JobStore(data, worker=worker)
            jobs = []
            for _ in range(2):
                job = store.submit({"sources": ["google-ai"], "lens": "x", "insights": 3})["job"]
                store.wait(job, 10)
                store.save(job)
                store.write_artifact(job, "check.json", {"claim_evidence": {"verification": {"seal": {"value": "abc"}}}})
                jobs.append(job)
            seen = []

            def verify(evidence):
                seen.append(evidence)
                return True
            rc, lines = self.run_doctor(target, seals=True, verify=verify)
            self.assertEqual(len(seen), 2)
            self.assertTrue(any(ln.startswith("PASS seals: 2 saved brief(s) re-verified") for ln in lines), lines)
            path = data / "generations" / "g1" / "jobs" / jobs[0] / "job.json"
            rec = json.loads(path.read_text())
            rec["result"]["lens"] = "changed after the check"
            path.write_text(json.dumps(rec))
            rc, lines = self.run_doctor(target, seals=True, verify=verify)
            self.assertEqual(rc, 1)
            self.assertTrue(any(ln.startswith("FAIL seals") and "changed after it was checked" in ln for ln in lines))

    def test_the_command_line_flags_reach_the_checks(self):
        with fake_home() as home:
            target = install(home)
            run = subprocess.run([sys.executable, "-m", "composer", "doctor", "--parity", "--seals", "--home",
                                  str(target)], capture_output=True, text=True, timeout=120, cwd=ROOT)
            self.assertIn("parity: delete", run.stdout)
            self.assertIn("seals:", run.stdout)
            self.assertNotIn("online:", run.stdout)


class SchedulerTests(unittest.TestCase):
    CFG = {"schedule": {"enabled": True, "time": "07:00", "timezone": "UTC", "sources": ["google-ai"],
                        "lens": "daily", "insights": 5}, "backup": {"weekly": False, "keep": 8}}

    class Store:
        def __init__(self):
            self.submitted, self.saved, self.full = [], [], False
            self.jobs = {}

        def submit(self, request):
            if self.full:
                raise RuntimeError("capacity full")
            job = f"job-{len(self.submitted):016x}"
            self.submitted.append(request)
            self.jobs[job] = {"job": job, "request": request, "phase": "verified", "result": {}}
            return {"job": job}

        def status(self, job):
            return self.jobs[job]

        def save(self, job):
            self.saved.append(job)

    def at(self, text):
        return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)

    def make(self, tmp, now, store=None, **kw):
        clock = {"now": now}
        store = store or self.Store()
        sched = Scheduler(tmp, self.CFG, store, clock=lambda: clock["now"], log=lambda *_: None, **kw)
        return sched, store, clock

    def test_slots(self):
        self.assertEqual(slot_for(self.at("2026-11-02 06:59"), "07:00", "UTC"), self.at("2026-11-01 07:00"))
        self.assertEqual(slot_for(self.at("2026-11-02 07:00"), "07:00", "UTC"), self.at("2026-11-02 07:00"))
        self.assertEqual(next_slot(self.at("2026-11-02 07:30"), "07:00", "UTC"), self.at("2026-11-03 07:00"))

    def test_once_per_slot_and_never_stacked(self):
        with fake_home() as home:
            sched, store, clock = self.make(home, self.at("2026-11-02 07:01"))
            self.assertEqual(sched.tick(), "started")
            self.assertIsNone(sched.tick())
            clock["now"] = self.at("2026-11-02 12:00")
            self.assertIsNone(sched.tick())
            self.assertEqual(len(store.submitted), 1)
            self.assertEqual(store.submitted[0]["scheduled"], "2026-11-02T07:00Z")
            sched.on_finished("job-0000000000000000")
            self.assertEqual(store.saved, ["job-0000000000000000"])
            self.assertEqual(sched.state()["last_outcome"], "saved to the shelf")
            # a fresh scheduler (a restart) on the same day does not run it again
            again, store2, _ = self.make(home, self.at("2026-11-02 13:00"))
            self.assertIsNone(again.tick())
            self.assertEqual(store2.submitted, [])

    def test_missed_by_more_than_six_hours_is_skipped_and_logged(self):
        with fake_home() as home:
            sched, store, clock = self.make(home, self.at("2026-11-02 13:01"))
            self.assertEqual(sched.tick(), "skipped")
            self.assertEqual(store.submitted, [])
            self.assertIn("skipped", sched.state()["last_outcome"])
            clock["now"] = self.at("2026-11-03 12:59")  # next day, 5 h 59 min late: still runs, once
            self.assertEqual(sched.tick(), "started")
            self.assertEqual(len(store.submitted), 1)

    def test_busy_engine_does_not_stack(self):
        with fake_home() as home:
            store = self.Store()
            store.full = True
            sched, _, _ = self.make(home, self.at("2026-11-02 07:05"), store=store)
            self.assertEqual(sched.tick(), "busy")
            store.full = False
            self.assertIsNone(sched.tick())  # the slot is used up; the next one runs tomorrow

    def test_weekly_backup_once_per_week(self):
        with fake_home() as home:
            made = []
            cfg = dict(self.CFG, schedule=dict(self.CFG["schedule"], enabled=False), backup={"weekly": True, "keep": 8})
            clock = {"now": self.at("2026-11-02 07:00")}
            sched = Scheduler(home, cfg, self.Store(), clock=lambda: clock["now"], log=lambda *_: None,
                              backup=lambda keep: made.append(keep) or "x")
            sched.tick()
            sched.tick()
            clock["now"] = self.at("2026-11-09 07:00")
            sched.tick()
            self.assertEqual(made, [8, 8])

    def test_the_real_store_saves_a_scheduled_brief(self):
        with fake_home() as home:
            def worker(job, draft_ready):
                draft_ready({"lens": "daily", "cards": []})
                return {"status": "ok", "claim_evidence": {"job": job["job"], "draft_sha256": job["draft_sha256"]}}
            holder = {}
            store = JobStore(home / "data", worker=worker, on_finished=lambda j: holder["s"].on_finished(j))
            sched = Scheduler(home / "data", self.CFG, store, clock=lambda: self.at("2026-11-02 07:30"),
                              log=lambda *_: None)
            holder["s"] = sched
            self.assertEqual(sched.tick(), "started")
            job = sched.state()["last_job"]
            store.wait(job, 10)
            import time
            for _ in range(100):
                if store.index()["items"]:
                    break
                time.sleep(0.02)
            self.assertEqual([i["job"] for i in store.index()["items"]], [job])


if __name__ == "__main__":
    unittest.main()
