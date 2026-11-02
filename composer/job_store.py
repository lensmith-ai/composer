"""Durable, versioned local storage for Composer P1a jobs."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import time
import uuid

from . import shelf_index


DATA_SCHEMA = "1"  # the data schema this code reads and writes; a newer generation is refused at start
AUDIO_STATES = ("off", "generating", "ready", "failed")
ARTIFACTS = ("check.json", "receipts.json")


class StoreError(RuntimeError):
    pass


class SimulatedCrash(RuntimeError):
    pass


class JobStore:
    MIGRATION_STAGES = ("pair_recorded", "migration_intent", "copy_complete", "schema_migrated", "health_checked")
    SWITCH_STAGES = ("switch_intent", "pointer_temp_written", "pointer_temp_synced", "pointer_replaced", "pointer_parent_synced", "switch_committed")
    TERMINAL = {"verified", "verification_failed", "compose_failed"}
    MEMO_CAP = 20

    def __init__(self, root: Path | str, *, worker, capacity: int = 2, wall_cap_s: float = 600,
                 on_finished=None) -> None:
        self.root = Path(root)
        self.worker = worker
        self.on_finished = on_finished  # called with the job id after a job reaches a final phase
        self.capacity = capacity
        self.wall_cap_s = wall_cap_s
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.active: set[str] = set()
        self.memo: OrderedDict[str, dict] = OrderedDict()
        self.watchdogs: dict[str, threading.Timer] = {}
        self._initialize_or_recover()

    @property
    def generations(self) -> Path:
        return self.root / "generations"

    @property
    def recovery(self) -> Path:
        return self.root / "recovery"

    @property
    def journal(self) -> Path:
        return self.recovery / "journal" / "events.jsonl"

    @property
    def pairs(self) -> Path:
        return self.recovery / "pairs.json"

    def generation_path(self, generation: str) -> Path:
        if generation not in {"g1", "g2"}:
            raise StoreError("unknown generation")
        return self.generations / generation

    def current_generation(self) -> str:
        value = (self.root / "current").read_text(encoding="utf-8").strip()
        if value not in {"g1", "g2"} or not self.generation_path(value).is_dir():
            raise StoreError("current generation is invalid")
        return value

    def job_path(self, job_id: str) -> Path:
        if not job_id.startswith("job-") or len(job_id) != 20:
            raise StoreError("invalid job id")
        return self.generation_path(self.current_generation()) / "jobs" / job_id

    def submit(self, request: dict) -> dict:
        if not isinstance(request, dict):
            raise StoreError("request must be an object")
        with self.lock:
            if len(self.active) >= self.capacity:
                raise RuntimeError("capacity full")
            job_id = "job-" + uuid.uuid4().hex[:16]
            job = {"schema": "composer-job/v1", "job": job_id, "state": "running", "phase": "queued",
                   "progress": [{"at": self._now(), "phase": "queued"}], "result": None,
                   "verification": {"status": "pending", "wall_s": None},
                   "receipts": {"verification": {"status": "pending", "wall_s": None}}, "request": request,
                   "started_at": self._now(), "finished_at": None, "error": None,
                   "commit": {"state": "unsaved", "saved_at_utc": None, "expires_at_utc": None}}
            self.active.add(job_id)
            self._write_job(job)
            self._project()  # the shelf index lists it as running, so a reopened page can rejoin it
            watchdog = threading.Timer(self.wall_cap_s, self._expire, args=(job_id,))
            watchdog.daemon = True
            self.watchdogs[job_id] = watchdog
            watchdog.start()
            threading.Thread(target=self._run, args=(job_id,), daemon=True).start()
            return {"job": job_id}

    def status(self, job_id: str) -> dict:
        with self.lock:
            return self._read_job(job_id)

    def wait(self, job_id: str, timeout: float) -> dict:
        deadline = time.monotonic() + timeout
        with self.changed:
            while True:
                job = self._read_job(job_id)
                if job["phase"] in self.TERMINAL and job_id not in self.active:
                    return job  # final, and the job's own thread has finished writing the shelf files too
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("job did not finish")
                self.changed.wait(remaining)

    def health(self) -> dict:
        with self.lock:
            # active_jobs lists the running job ids (the app page offers to rejoin the first one), as the live app does
            return {"ok": True, "active_jobs": sorted(self.active), "active_count": len(self.active),
                    "capacity": self.capacity,
                    "available": self.capacity - len(self.active), "generation": self.current_generation(),
                    "memo_jobs": self.memo_jobs()}

    def memo_jobs(self) -> int:
        return len(self.memo)

    def save(self, job_id: str) -> dict:
        with self.lock:
            job = self._read_job(job_id)
            if job["phase"] not in {"verified", "verification_failed"} or not isinstance(job.get("result"), dict):
                raise StoreError("brief is not readable")
            if job.get("commit", {}).get("state") != "saved":
                job["commit"] = {"state": "saved", "saved_at_utc": self._now(), "expires_at_utc": None}
                self._write_job(job)
            self._atomic_json(self.job_path(job_id) / "saved.json", {"job": job_id,
                                                                        "saved_at_utc": job["commit"]["saved_at_utc"]})
            self._project()
            return {"saved": True, "job": job_id, "saved_at_utc": job["commit"]["saved_at_utc"]}

    def index(self) -> dict:
        with self.lock:
            self._project()
            path = self.generation_path(self.current_generation()) / "index.json"
            return json.loads(path.read_text(encoding="utf-8"))

    def brief_index(self) -> bytes:
        """The shelf index the page reads at /data/index.json, as written by the last change to the store."""
        with self.lock:
            path = self.generation_path(self.current_generation()) / shelf_index.FILE
            if not path.is_file():
                self._project()
            return path.read_bytes()

    def latest(self) -> dict | None:
        with self.lock:
            self._project()
            path = self.generation_path(self.current_generation()) / "latest.json"
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def delete(self, job_id: str) -> None:
        with self.lock:
            source = self.job_path(job_id)
            if not source.is_dir():
                raise StoreError("no such brief")
            if not (source / "saved.json").is_file():
                raise StoreError("only saved briefs can be deleted")
            target = self.generation_path(self.current_generation()) / "trash" / job_id
            if target.exists():
                raise StoreError("brief already in trash")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
            self._atomic_json(target / "trash.json", {"job": job_id, "deleted_at": self._now(), "reason": "user-delete"})
            self._project()

    def restore(self, job_id: str) -> dict:
        with self.lock:
            generation = self.generation_path(self.current_generation())
            source = generation / "trash" / job_id
            target = generation / "jobs" / job_id
            if not source.is_dir() or not (source / "saved.json").is_file():
                raise StoreError("no such trashed brief")
            if target.exists():
                raise StoreError("brief already restored")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
            (target / "trash.json").unlink(missing_ok=True)
            self._project()
            return {"restored": job_id}

    def retention(self, *, apply: bool = False, now: datetime | None = None) -> dict:
        with self.lock:  # it moves job folders and rewrites the shelf index, like save, delete and restore
            return self._retention(apply=apply, now=now)

    def _retention(self, *, apply: bool, now: datetime | None) -> dict:
        now = now or datetime.now(timezone.utc)
        trash, purge = [], []
        live = self.generation_path(self.current_generation()) / "jobs"
        for path in sorted(live.glob("job-*/job.json")):
            job = json.loads(path.read_text(encoding="utf-8"))
            if job.get("commit", {}).get("state") == "saved" or not job.get("finished_at"):
                continue
            hours = 1 if job.get("request", {}).get("test") is True else 24
            if self._parse_time(job["finished_at"]) + timedelta(hours=hours) <= now:
                trash.append(job["job"])
        for stamp in sorted((self.generation_path(self.current_generation()) / "trash").glob("job-*/trash.json")):
            record = json.loads(stamp.read_text(encoding="utf-8"))
            if self._parse_time(record["deleted_at"]) + timedelta(days=7) <= now:
                purge.append(record["job"])
        result = {"dry_run": not apply, "would_trash": trash, "would_purge": purge, "trashed": [], "purged": []}
        if not apply:
            return result
        for job_id in trash:
            source = self.job_path(job_id)
            target = self.generation_path(self.current_generation()) / "trash" / job_id
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
            self._atomic_json(target / "trash.json", {"job": job_id, "deleted_at": self._now(), "reason": "retention"})
            result["trashed"].append(job_id)
        for job_id in purge:
            shutil.rmtree(self.generation_path(self.current_generation()) / "trash" / job_id)
            result["purged"].append(job_id)
        self._project()
        return result

    def migrate_copy(self, schema: str, *, crash_after: str | None = None) -> None:
        if self.active:
            raise StoreError("update requires no active jobs")
        if schema != "2":
            raise StoreError("only schema 2 is supported")
        source, target = self.current_generation(), "g2"
        if source != "g1" or self.generation_path(target).exists():
            raise StoreError("migration is not available")
        pairs = self._read_pairs()
        pairs.append({"old_generation": source, "new_generation": None, "old_schema": "1", "new_schema": None, "status": "copying"})
        self._atomic_json(self.pairs, pairs); self._checkpoint("migrate", "pair_recorded", crash_after, source=source, target=target)
        self._checkpoint("migrate", "migration_intent", crash_after, source=source, target=target)
        shutil.copytree(self.generation_path(source), self.generation_path(target), copy_function=shutil.copy2)
        self._checkpoint("migrate", "copy_complete", crash_after, source=source, target=target)
        self._atomic_text(self.generation_path(target) / "VERSION", "2\n")
        self._checkpoint("migrate", "schema_migrated", crash_after, source=source, target=target)
        pairs[-1].update({"new_generation": target, "new_schema": "2", "status": "ready"})
        self._atomic_json(self.pairs, pairs)
        self._checkpoint("migrate", "health_checked", crash_after, source=source, target=target)

    def switch(self, target: str, *, crash_after: str | None = None) -> None:
        if self.active:
            raise StoreError("update requires no active jobs")
        source = self.current_generation()
        if target == source or not self.generation_path(target).is_dir():
            raise StoreError("switch target is invalid")
        self._checkpoint("switch", "switch_intent", crash_after, source=source, target=target)
        tmp = self.root / "current.tmp"; self._atomic_text(tmp, target + "\n")
        self._checkpoint("switch", "pointer_temp_written", crash_after, source=source, target=target)
        self._checkpoint("switch", "pointer_temp_synced", crash_after, source=source, target=target)
        os.replace(tmp, self.root / "current")
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self._checkpoint("switch", "pointer_replaced", crash_after, source=source, target=target)
        self._checkpoint("switch", "pointer_parent_synced", crash_after, source=source, target=target)
        self._checkpoint("switch", "switch_committed", crash_after, source=source, target=target)
        with self.lock:
            self._project()  # the shelf index and latest pointer of the generation now in use

    def rollback(self) -> dict:
        if self.active:
            raise StoreError("update requires no active jobs")
        source = self.current_generation()
        pair = next((p for p in reversed(self._read_pairs()) if p.get("new_generation") == source), None)
        if not pair:
            raise StoreError("no rollback pair")
        export = self.recovery / "exports" / ("rollback-" + uuid.uuid4().hex)
        export.mkdir(parents=True)
        exported = []
        for path in sorted((self.generation_path(source) / "jobs").glob("job-*")):
            shutil.copytree(path, export / path.name)
            exported.append(path.name)
        self._replace_current(pair["old_generation"])
        self._journal("rollback", "pointer_restored", source=source, target=pair["old_generation"])
        with self.lock:
            self._project()
        return {"export_directory": str(export), "exported_jobs": exported}

    def _run(self, job_id: str) -> None:
        started = time.monotonic()
        try:
            self._transition(job_id, "fetching")
            self._transition(job_id, "synthesizing")
            job_view = self.status(job_id)
            def draft_ready(draft: dict) -> None:
                with self.lock:
                    job = self._read_job(job_id)
                    if job_id not in self.active or job["phase"] in self.TERMINAL:
                        return
                    job["result"] = draft
                    job["draft_sha256"] = self._digest(draft)
                    job["phase"] = "text_ready_checking"
                    job["progress"].append({"at": self._now(), "phase": "text_ready_checking"})
                    job["verification_started_at"] = self._now()
                    job["verification"] = {"status": "running", "wall_s": None}
                    job["receipts"]["verification"] = job["verification"]
                    job_view["draft_sha256"] = job["draft_sha256"]
                    self._write_job(job); self.changed.notify_all()
            result = self.worker(job_view, draft_ready)
            with self.lock:
                job = self._read_job(job_id)
                if job["phase"] in self.TERMINAL:
                    return
                if not isinstance(job.get("result"), dict) or not job.get("draft_sha256"):
                    raise StoreError("worker did not persist a draft before verification")
                verification = result if isinstance(result, dict) else {"status": "verifier-error"}
                bound = verification.get("claim_evidence", {})
                if not isinstance(bound, dict) or bound.get("job") != job_id or bound.get("draft_sha256") != job["draft_sha256"]:
                    raise StoreError("verification is not bound to this draft")
                status = verification.get("status", "verifier-error")
                job["phase"] = "verified" if status == "ok" else "verification_failed"
                job["state"] = "done"; job["finished_at"] = self._now()
                job["progress"].append({"at": self._now(), "phase": job["phase"]})
                job["verification"] = {"status": status, "wall_s": round(time.monotonic() - started, 3)}
                job["receipts"]["verification"] = job["verification"]
                self._write_job(job)
        except Exception as exc:
            with self.lock:
                job = self._read_job(job_id)
                if job["phase"] in self.TERMINAL:
                    return
                job["phase"] = "verification_failed" if job.get("result") else "compose_failed"
                job["state"] = "failed"; job["finished_at"] = self._now(); job["error"] = type(exc).__name__
                job["progress"].append({"at": self._now(), "phase": job["phase"]})
                job["verification"] = {"status": "timeout" if isinstance(exc, TimeoutError) else "verifier-error", "wall_s": round(time.monotonic() - started, 3)}
                job["receipts"]["verification"] = job["verification"]
                self._write_job(job)
        finally:
            with self.changed:
                watchdog = self.watchdogs.pop(job_id, None)
                if watchdog:
                    watchdog.cancel()
                self.active.discard(job_id)
                self._memoize(job_id)
                self._project()
                self.changed.notify_all()
            self._finished(job_id)

    def _expire(self, job_id: str) -> None:
        with self.changed:
            if job_id not in self.active:
                return
            job = self._read_job(job_id)
            if job["phase"] in self.TERMINAL:
                return
            job["state"] = "failed"
            job["phase"] = "compose_failed"
            job["finished_at"] = self._now()
            job["error"] = "wall-clock cap exceeded"
            job["progress"].append({"at": self._now(), "phase": "compose_failed"})
            job["verification"] = {"status": "timeout", "wall_s": self.wall_cap_s}
            job["receipts"]["verification"] = job["verification"]
            self._write_job(job)
            self.active.discard(job_id)
            self._memoize(job_id)
            self._project()
            self.changed.notify_all()
        self._finished(job_id)

    def _finished(self, job_id: str) -> None:
        if self.on_finished is None:
            return
        try:
            self.on_finished(job_id)
        except Exception:  # a follow-up (narration, auto-save) must never break the job itself
            pass

    def set_audio(self, job_id: str, audio: dict) -> dict:
        """Record the narration state of a finished brief: {"state": off|generating|ready|failed, ...}.
        The page reads `audio_state` from job.json; `audio` carries the voice, file, format and reason."""
        if audio.get("state") not in AUDIO_STATES:
            raise StoreError("unknown audio state")
        with self.lock:
            job = self._read_job(job_id)
            job["audio"] = dict(audio)
            job["audio_state"] = audio["state"]
            self._write_job(job)
            if job_id in self.memo:
                self.memo[job_id] = job
            return job

    def job_dir(self, job_id: str) -> Path:
        return self.job_path(job_id)

    def write_artifact(self, job_id: str, name: str, value: object) -> None:
        if name not in ARTIFACTS:
            raise StoreError("unknown artifact")
        with self.lock:
            self._atomic_json(self.job_path(job_id) / name, value)

    def record(self, operation: str, stage: str, **fields) -> None:
        """Append one step of a lifecycle operation (update, code switch) to the recovery journal."""
        self._journal(operation, stage, **fields)

    def last(self, operation: str) -> dict | None:
        return self._last(operation)

    def generation_schema(self, generation: str | None = None) -> str:
        path = self.generation_path(generation or self.current_generation()) / "VERSION"
        return path.read_text(encoding="utf-8").strip()

    def _memoize(self, job_id: str) -> None:
        try:
            self.memo[job_id] = self._read_job(job_id)
        except (OSError, ValueError, StoreError):
            return
        self.memo.move_to_end(job_id)
        while len(self.memo) > self.MEMO_CAP:
            self.memo.popitem(last=False)

    def _initialize_or_recover(self) -> None:
        if not (self.root / "current").exists():
            (self.generations / "g1" / "jobs").mkdir(parents=True)
            (self.recovery / "journal").mkdir(parents=True)
            (self.recovery / "exports").mkdir(parents=True)
            self._atomic_text(self.generation_path("g1") / "VERSION", "1\n")
            self._atomic_json(self.pairs, [])
            self._replace_current("g1")
            self._project()
            return
        self._recover()

    def _recover(self) -> None:
        last_migrate = self._last("migrate")
        if last_migrate and last_migrate["stage"] != "health_checked":
            target = self.generation_path(last_migrate["target"])
            if target.exists(): shutil.rmtree(target)
        last_switch = self._last("switch")
        if last_switch and last_switch["stage"] not in {"switch_committed", "pointer_replaced", "pointer_parent_synced"}:
            (self.root / "current.tmp").unlink(missing_ok=True)
        for path in self.generation_path(self.current_generation()).glob("jobs/job-*/job.json"):
            job = json.loads(path.read_text(encoding="utf-8"))
            if job.get("phase") not in self.TERMINAL:
                job.update({"state": "failed", "phase": "compose_failed", "finished_at": self._now(), "error": "interrupted restart",
                            "verification": {"status": "verifier-error", "wall_s": None}})
                job.setdefault("receipts", {})["verification"] = job["verification"]
                self._atomic_json(path, job)
            elif job.get("audio_state") == "generating":
                job["audio"] = dict(job.get("audio") or {}, state="failed", reason="interrupted by a restart")
                job["audio_state"] = "failed"
                self._atomic_json(path, job)
        self._project()

    def _transition(self, job_id: str, phase: str) -> None:
        with self.lock:
            job = self._read_job(job_id); job["phase"] = phase; job["progress"].append({"at": self._now(), "phase": phase}); self._write_job(job)

    def _project(self) -> None:
        generation = self.generation_path(self.current_generation())
        items = []
        for folder in sorted((generation / "jobs").glob("job-*")):
            marker = folder / "saved.json"
            if not marker.is_file():
                continue
            try:
                saved = json.loads(marker.read_text(encoding="utf-8"))
                job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
                items.append({"job": job["job"], "phase": job["phase"],
                              "saved_at_utc": saved["saved_at_utc"], "readable": isinstance(job.get("result"), dict)})
            except (OSError, json.JSONDecodeError, KeyError):
                items.append({"job": folder.name, "phase": "unreadable", "saved_at_utc": None, "readable": False})
        items.sort(key=lambda item: item.get("saved_at_utc") or "", reverse=True)
        self._atomic_json(generation / "index.json", {"schema": "composer-shelf/v1", "items": items})
        # the page's shelf index (/data/index.json): every brief, saved or not, with what the drawer shows
        self._atomic_json(generation / shelf_index.FILE, shelf_index.build(generation / "jobs"))
        readable = [item for item in items if item["readable"]]
        latest = {"job": readable[0]["job"], "composed_at": readable[0]["saved_at_utc"]} if readable else None
        latest_path = generation / "latest.json"
        if latest: self._atomic_json(latest_path, latest)
        else: latest_path.unlink(missing_ok=True)

    def _read_job(self, job_id: str) -> dict:
        return json.loads((self.job_path(job_id) / "job.json").read_text(encoding="utf-8"))

    def _write_job(self, job: dict) -> None:
        path = self.job_path(job["job"]) / "job.json"; path.parent.mkdir(parents=True, exist_ok=True); self._atomic_json(path, job)

    def _checkpoint(self, operation: str, stage: str, crash_after: str | None, **fields) -> None:
        self._journal(operation, stage, **fields)
        if crash_after == stage: raise SimulatedCrash(stage)

    def _journal(self, operation: str, stage: str, **fields) -> None:
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        with self.journal.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"operation": operation, "stage": stage, **fields}, sort_keys=True) + "\n"); handle.flush(); os.fsync(handle.fileno())

    def _last(self, operation: str) -> dict | None:
        if not self.journal.exists(): return None
        rows = [json.loads(line) for line in self.journal.read_text(encoding="utf-8").splitlines() if line]
        return next((row for row in reversed(rows) if row["operation"] == operation), None)

    def _read_pairs(self) -> list:
        return json.loads(self.pairs.read_text(encoding="utf-8"))

    def _replace_current(self, generation: str) -> None:
        tmp = self.root / "current.tmp"
        self._atomic_text(tmp, generation + "\n")
        os.replace(tmp, self.root / "current")
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _atomic_text(path: Path, value: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_name("." + path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle: handle.write(value); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)

    def _atomic_json(self, path: Path, value: object) -> None:
        self._atomic_text(path, json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _digest(value: dict) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_time(value: str) -> datetime:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
