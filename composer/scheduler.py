"""The app's own daily brief (and weekly backup): the same on a laptop and a server, no cron needed.

While `composer up` runs, a thread looks at the clock every 30 seconds. For a daily slot (say 07:00):
  - it composes once per slot, through the same job store as the page, and saves the brief to your shelf;
  - if the app was asleep or down at the slot, it still runs once if it is within 6 hours, else it skips that
    slot and logs why; missed slots never stack up;
  - the slot is recorded BEFORE the brief starts, so a crash or restart cannot run the same slot twice.
State lives in <data>/scheduler.json, outside the data generations, so updates and rollbacks keep it.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .home import atomic_write

GRACE = timedelta(hours=6)
STATE = "scheduler.json"


def slot_for(now: datetime, hhmm: str, tz: str) -> datetime:
    """The most recent slot at or before `now` (an aware datetime), in UTC."""
    hour, minute = (int(x) for x in hhmm.split(":"))
    local = now.astimezone(timezone.utc) if tz == "UTC" else now.astimezone()
    slot = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if slot > local:
        slot -= timedelta(days=1)
    return slot.astimezone(timezone.utc)


def next_slot(now: datetime, hhmm: str, tz: str) -> datetime:
    return slot_for(now, hhmm, tz) + timedelta(days=1)


class Scheduler:
    def __init__(self, data: Path, cfg: dict, store, *, backup=None, clock=None, log=print):
        self.data = data
        self.cfg = cfg
        self.store = store
        self.backup = backup  # callable(keep) -> path, for the weekly backup; None turns it off
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.log = log
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = None

    # ------------------------------------------------------------------ state

    def state(self) -> dict:
        path = self.data / STATE
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            return doc if isinstance(doc, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, doc: dict) -> None:
        atomic_write(self.data / STATE, json.dumps(doc, indent=2, sort_keys=True) + "\n", mode=0o600)

    def status(self) -> dict:
        s = self.cfg.get("schedule", {})
        st = self.state()
        out = {"enabled": bool(s.get("enabled")), "time": s.get("time"), "timezone": s.get("timezone"),
               "last_slot": st.get("last_slot"), "last_outcome": st.get("last_outcome"),
               "last_job": st.get("last_job"), "last_backup_week": st.get("last_backup_week")}
        if out["enabled"]:
            out["next_run_utc"] = next_slot(self.clock(), s["time"], s["timezone"]).strftime("%Y-%m-%dT%H:%M:%SZ")
        return out

    # ------------------------------------------------------------------ one tick

    def tick(self) -> str | None:
        """Check the clock once. Returns what happened: "started", "skipped", "busy", or None."""
        with self.lock:
            outcome = None
            s = self.cfg.get("schedule", {})
            now = self.clock()
            if s.get("enabled"):
                outcome = self._daily(now, s)
            if self.backup is not None and self.cfg.get("backup", {}).get("weekly"):
                self._weekly_backup(now)
            return outcome

    def _daily(self, now: datetime, s: dict) -> str | None:
        slot = slot_for(now, s["time"], s["timezone"])
        key = slot.strftime("%Y-%m-%dT%H:%MZ")
        st = self.state()
        if st.get("last_slot") == key:
            return None
        if now - slot > GRACE:
            st.update(last_slot=key, last_outcome=f"skipped: the app was not running within 6 hours of {key}")
            self._save(st)
            self.log(f"scheduler: skipped the {key} brief (missed by more than 6 hours)")
            return "skipped"
        st.update(last_slot=key, last_outcome="starting")
        self._save(st)  # recorded first: a crash from here on cannot run this slot twice
        try:
            started = self.store.submit({"sources": list(s["sources"]), "lens": s["lens"].strip(),
                                         "insights": int(s["insights"]), "scheduled": key})
        except RuntimeError:
            st.update(last_outcome="busy: both compose slots were in use; this slot was not run")
            self._save(st)
            self.log(f"scheduler: the {key} brief did not start (compose capacity full)")
            return "busy"
        st.update(last_outcome="started", last_job=started["job"])
        self._save(st)
        self.log(f"scheduler: started the {key} brief as {started['job']}")
        return "started"

    def _weekly_backup(self, now: datetime) -> None:
        year, week, _ = now.isocalendar()
        key = f"{year}-W{week:02d}"
        st = self.state()
        if st.get("last_backup_week") == key:
            return
        st["last_backup_week"] = key
        self._save(st)
        try:
            path = self.backup(int(self.cfg.get("backup", {}).get("keep", 8)))
            self.log(f"scheduler: weekly backup written to {path}")
        except Exception as exc:  # a failed backup is logged; it never stops the app
            self.log(f"scheduler: the weekly backup failed: {exc}")

    # ------------------------------------------------------------------ follow-up and loop

    def on_finished(self, job_id: str) -> None:
        """Save a scheduled brief to the shelf once its text is final."""
        job = self.store.status(job_id)
        key = (job.get("request") or {}).get("scheduled")
        if not key:
            return
        st = self.state()
        if job.get("phase") in ("verified", "verification_failed") and isinstance(job.get("result"), dict):
            self.store.save(job_id)
            outcome = "saved to the shelf"
        else:
            outcome = f"failed: {job.get('error') or job.get('phase')}"
        if st.get("last_job") == job_id:
            st["last_outcome"] = outcome
            self._save(st)
        self.log(f"scheduler: the {key} brief {outcome}")

    def start(self, every_s: float = 30.0) -> "Scheduler":
        def loop():
            while not self.stop.is_set():
                try:
                    self.tick()
                except Exception as exc:
                    self.log(f"scheduler: {exc}")
                self.stop.wait(every_s)
        self.thread = threading.Thread(target=loop, name="scheduler", daemon=True)
        self.thread.start()
        return self


def chain(*hooks):
    """One on_finished callback that calls each hook in turn; a failing hook does not stop the others."""
    def run(job_id: str) -> None:
        for hook in hooks:
            if hook is None:
                continue
            try:
                hook(job_id)
            except Exception:
                pass
    return run
