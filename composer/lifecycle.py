"""Backup and restore, update and rollback, uninstall: the commands that change an install as a whole.

backup    a dated .tar.gz of the current data generation (your briefs, settings, sources) in <data>/backups,
          with a list of every file's SHA-256 inside; never your key unless --include-secrets.
restore   checks the archive first (no absolute paths, no "..", no links or devices, size limits, every
          file's SHA-256), backs up what is there now, then swaps the restored generation in. The replaced
          generation is kept under <data>/recovery/replaced/.
update    installs a release file into its own app/<version>/venv (checksum first), then, journaled in the job
          store: migrates a COPY of the data if the new version needs a newer schema, switches the data pointer,
          switches app/current, runs `composer doctor` with the new version, and undoes everything if that
          fails. An update that was interrupted is finished or undone the next time Composer starts.
rollback  points the data and the code back to the pair the last update recorded, exporting every brief made
          since the update to <data>/recovery/exports/ first. Nothing is deleted.
uninstall removes only what the install manifest lists as created, and your data only with --delete-data.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import home as H
from . import settings as S
from .job_store import DATA_SCHEMA, JobStore, StoreError

BACKUP_SCHEMA = "composer-backup/v1"
BACKUP_NAME = re.compile(r"^composer-backup-\d{8}T\d{6}Z(-[a-z]+)?\.tar\.gz$")
MAX_MEMBERS = 200_000
MAX_FILE = 512 * 1024 * 1024
MAX_TOTAL = 4 * 1024 * 1024 * 1024
RUN_LOCK = "up.lock"
VERSION_NAME = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+_-]{0,63}")  # starts with a letter or digit: never "." or ".."


class LifecycleError(RuntimeError):
    pass


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ------------------------------------------------------------------------------------------------ running?

def hold_run_lock(data: Path):
    """Taken by `composer up` for as long as it runs; backup is fine meanwhile, restore/update/uninstall wait."""
    data.mkdir(parents=True, exist_ok=True)
    handle = open(data / RUN_LOCK, "a+")
    try:
        import fcntl
    except ImportError:
        return handle
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise LifecycleError("Composer is already running with this data folder (`composer up`)") from None
    return handle


def app_running(data: Path) -> bool:
    path = data / RUN_LOCK
    if not path.exists():
        return False
    try:
        import fcntl
    except ImportError:
        return False
    with open(path, "a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return False


def _refuse_if_running(data: Path, what: str) -> None:
    if app_running(data):
        raise LifecycleError(f"stop `composer up` first (Ctrl+C, or `docker compose stop composer`), then {what}")


class exclusive:
    """Hold the run lock for a whole operation, so `composer up`, an update, a restore or an uninstall never run
    at the same time on the same data (not only checked at the start)."""

    def __init__(self, data: Path, what: str):
        self.data, self.what, self.handle = data, what, None

    def __enter__(self):
        if self.data.is_dir():
            try:
                self.handle = hold_run_lock(self.data)
            except LifecycleError:
                raise LifecycleError(f"stop `composer up` first (Ctrl+C, or `docker compose stop composer`), "
                                     f"then {self.what}") from None
        return self

    def __exit__(self, *exc):
        if self.handle is not None:
            self.handle.close()
        return False


# ------------------------------------------------------------------------------------------------ backup

def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def backup(data: Path, *, include_secrets: bool = False, out_dir: Path | None = None, keep: int | None = None,
           tag: str = "") -> Path:
    """Each file is read once, hashed and added from the same bytes, so a brief that changes while the app runs
    cannot make the archive disagree with its own list. `keep` prunes only backups with the same tag."""
    gen = S.generation_dir(data, create=False)
    out_dir = out_dir or data / "backups"
    if not out_dir.exists():
        out_dir.mkdir(parents=True, mode=0o700)  # only a folder made here is set private; yours is left as it is
    if tag and not re.fullmatch(r"[a-z]+", tag):
        raise LifecycleError("a backup tag is lower-case letters")
    name = f"composer-backup-{_stamp()}{'-' + tag if tag else ''}.tar.gz"
    final = out_dir / name
    tmp = out_dir / ("." + name + "." + uuid.uuid4().hex[:8] + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    files = {}
    now_s = int(datetime.now(timezone.utc).timestamp())

    def add(tar, arcname: str, blob: bytes) -> None:
        info = tarfile.TarInfo(arcname)
        info.size, info.mode, info.mtime = len(blob), 0o600, now_s
        tar.addfile(info, io.BytesIO(blob))

    try:
        with os.fdopen(fd, "wb") as raw, tarfile.open(fileobj=raw, mode="w:gz") as tar:
            for path in sorted(gen.rglob("*")):
                if path.is_symlink() or not path.is_file():
                    continue
                rel = path.relative_to(gen).as_posix()
                if rel.endswith(".tmp"):
                    continue  # a write in progress; the finished file is what counts
                try:
                    blob = path.read_bytes()
                except FileNotFoundError:
                    continue  # removed while the backup ran (a brief moved to the trash)
                files[rel] = hashlib.sha256(blob).hexdigest()
                add(tar, "generation/" + rel, blob)
            secrets = S.secrets_path(data)
            with_secrets = include_secrets and secrets.is_file()
            if with_secrets:
                add(tar, "secrets.env", secrets.read_bytes())
            meta = {"schema": BACKUP_SCHEMA, "created_at": H.now(), "generation": gen.name,
                    "data_schema": (gen / "VERSION").read_text(encoding="utf-8").strip(), "files": files,
                    "includes_secrets": with_secrets}
            add(tar, "backup.json", json.dumps(meta, indent=1, sort_keys=True).encode("utf-8"))
        os.replace(tmp, final)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    if keep:
        suffix = f"-{tag}.tar.gz" if tag else None
        ours = sorted(p for p in out_dir.iterdir() if BACKUP_NAME.match(p.name) and suffix and p.name.endswith(suffix))
        for old in ours[:-keep]:
            old.unlink()
    return final


def _check_member_name(name: str) -> list[str]:
    if not name or "\0" in name or "\\" in name or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise LifecycleError(f"refused: the archive holds an unsafe path {name[:80]!r}")
    parts = name.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise LifecycleError(f"refused: the archive holds an unsafe path {name[:80]!r}")
    if not (name in ("backup.json", "secrets.env") or (parts[0] == "generation" and len(parts) > 1)):
        raise LifecycleError(f"refused: the archive holds a file Composer does not back up: {name[:80]!r}")
    return parts


def _stream_hash(handle) -> str:
    h = hashlib.sha256()
    for block in iter(lambda: handle.read(1 << 20), b""):
        h.update(block)
    return h.hexdigest()


def read_backup(archive: Path) -> dict:
    """Check an archive completely without writing anything: every name, type and size, and every file's SHA-256
    against the archive's own list (read as a stream, never all at once). Returns backup.json."""
    seen, hashes, total, meta = set(), {}, 0, None
    try:
        tar = tarfile.open(archive, mode="r:gz")
    except (OSError, tarfile.TarError) as exc:
        raise LifecycleError(f"refused: {archive} is not a Composer backup ({exc})") from None
    try:
        with tar:
            for count, member in enumerate(tar, 1):
                if count > MAX_MEMBERS:
                    raise LifecycleError("refused: the archive holds too many files")
                _check_member_name(member.name)
                if member.isdir():
                    continue
                if not member.isreg():
                    raise LifecycleError(f"refused: {member.name[:80]!r} is a link or a device, not a file")
                if member.size > MAX_FILE:
                    raise LifecycleError(f"refused: {member.name[:80]!r} is too large")
                total += member.size
                if total > MAX_TOTAL:
                    raise LifecycleError("refused: the archive is too large")
                if member.name in seen:
                    raise LifecycleError(f"refused: {member.name[:80]!r} appears twice")
                seen.add(member.name)
                handle = tar.extractfile(member)
                if member.name == "backup.json":
                    if member.size > 64 * 1024 * 1024:
                        raise LifecycleError("refused: backup.json is too large")
                    try:
                        meta = json.loads(handle.read().decode("utf-8"))
                    except ValueError:
                        raise LifecycleError("refused: the archive's backup.json cannot be read") from None
                elif member.name.startswith("generation/"):
                    hashes[member.name] = _stream_hash(handle)
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise LifecycleError(f"refused: the archive is damaged ({exc})") from None
    if not isinstance(meta, dict) or meta.get("schema") != BACKUP_SCHEMA or not isinstance(meta.get("files"), dict):
        raise LifecycleError("refused: this is not a Composer backup")
    if "VERSION" not in meta["files"]:
        raise LifecycleError("refused: the archive has no data schema VERSION file")
    listed = {"generation/" + k: v for k, v in meta["files"].items()}
    if set(hashes) != set(listed):
        raise LifecycleError("refused: the archive's files do not match its own list")
    for name, want in listed.items():
        if hashes[name] != want:
            raise LifecycleError(f"refused: {name[:80]!r} does not match its recorded SHA-256")
    return meta


def restore(data: Path, archive: Path, *, include_secrets: bool = False, crash_after: str | None = None) -> dict:
    with exclusive(data, "restore"):
        _recover_restore(data)
        meta = read_backup(archive)  # everything is checked before anything is written
        gen = S.generation_dir(data, create=False)
        have = (gen / "VERSION").read_text(encoding="utf-8").strip()
        if meta.get("data_schema") != have:
            raise LifecycleError(f"refused: the backup's data schema is {meta.get('data_schema')}, this data is "
                                 f"{have}; restore it with the Composer version that made it")
        safety = backup(data, tag="prerestore")
        stage = data / "tmp" / ("restore-" + uuid.uuid4().hex)
        staged = stage / "generation"
        staged.mkdir(parents=True)
        secret_blob = None
        try:
            with tarfile.open(archive, mode="r:gz") as tar:
                for member in tar:
                    parts = _check_member_name(member.name)
                    if not member.isreg():
                        continue
                    handle = tar.extractfile(member)
                    if member.name == "secrets.env":
                        secret_blob = handle.read(64 * 1024)
                        continue
                    if parts[0] != "generation":
                        continue
                    target = stage.joinpath(*parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    h = hashlib.sha256()
                    with open(target, "xb") as out:
                        for block in iter(lambda: handle.read(1 << 20), b""):
                            h.update(block)
                            out.write(block)
                    if h.hexdigest() != meta["files"].get("/".join(parts[1:])):
                        raise LifecycleError("refused: the archive changed while it was being restored")
            if (staged / "VERSION").read_text(encoding="utf-8").strip() != have:
                raise LifecycleError("refused: the archive's VERSION file does not match its own schema")
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        replaced = data / "recovery" / "replaced" / f"{_stamp()}-{gen.name}"
        replaced.parent.mkdir(parents=True, exist_ok=True)
        fields = {"generation": str(gen), "replaced": str(replaced), "staged": str(staged)}
        _journal_append(data, "restore", "intent", **fields)
        os.replace(gen, replaced)
        _journal_append(data, "restore", "old_moved", **fields)
        if crash_after == "old_moved":
            raise Crash("old_moved")
        os.replace(staged, gen)
        _journal_append(data, "restore", "done", **fields)
        shutil.rmtree(stage, ignore_errors=True)
        restored_secrets = False
        if include_secrets and secret_blob:
            for line in secret_blob.decode("utf-8").splitlines():
                if "=" in line and not line.startswith("#"):
                    name, value = line.split("=", 1)
                    if name.strip() in S.KEY_NAMES:
                        S.write_secret(data, name.strip(), value)
                        restored_secrets = True
        return {"restored_files": len(meta["files"]), "safety_backup": str(safety),
                "replaced_kept_at": str(replaced), "secrets_restored": restored_secrets}


def _journal_path(data: Path) -> Path:
    return data / "recovery" / "journal" / "events.jsonl"


def _journal_last(data: Path, operation: str) -> dict | None:
    path = _journal_path(data)
    if not path.exists():
        return None
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return next((r for r in reversed(rows) if r.get("operation") == operation), None)


def _journal_append(data: Path, operation: str, stage: str, **fields) -> None:
    """The same append-and-fsync the job store uses, for a step taken before the store can open."""
    path = _journal_path(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"operation": operation, "stage": stage, **fields}, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _recover_restore(data: Path, log=print) -> str | None:
    """A restore that stopped between its two renames: put the data that was there back. Runs before the job
    store opens, because the current generation's folder may be missing at that moment."""
    last = _journal_last(data, "restore")
    if not last or last["stage"] in ("done", "undone"):
        return None
    gen, replaced, staged = Path(last["generation"]), Path(last["replaced"]), Path(last["staged"])
    if not gen.exists() and replaced.exists():
        os.replace(replaced, gen)
        log("recovered an interrupted restore: your data from before it is back in place")
    shutil.rmtree(staged.parent, ignore_errors=True)
    _journal_append(data, "restore", "undone", **{k: last[k] for k in ("generation", "replaced", "staged")})
    return "undone"


# ------------------------------------------------------------------------------------------------ update

def _current_version(home: Path) -> str | None:
    link = home / "app" / "current"
    if not os.path.islink(link):
        return None
    return os.readlink(link).rstrip("/").split("/")[-1]


def _point_code(home: Path, version: str) -> None:
    """Atomically point app/current at app/<version>."""
    if not VERSION_NAME.fullmatch(version) or not (home / "app" / version).is_dir():
        raise LifecycleError(f"no installed version {version!r}")
    tmp = home / "app" / ".current.tmp"
    if os.path.lexists(tmp):
        os.unlink(tmp)
    os.symlink(version, tmp)
    os.replace(tmp, home / "app" / "current")


def _venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def verify_file(path: Path, sha256: str | None) -> str:
    got = _sha(path)
    want = (sha256 or "").strip().lower()
    if not want:
        sums = path.parent / "SHA256SUMS"
        if sums.is_file():
            for line in sums.read_text(encoding="utf-8").splitlines():
                bits = line.split()
                if len(bits) == 2 and bits[1].lstrip("*") == path.name:
                    want = bits[0].lower()
    if not want:
        raise LifecycleError("refused: give the release file's SHA-256 (--sha256) or put SHA256SUMS next to it")
    if got != want:
        raise LifecycleError("refused: the release file's SHA-256 does not match; nothing was installed")
    return got


def _query(python: Path, home: Path, code: str, run) -> str:
    proc = run([str(python), "-I", "-c", code], capture_output=True, text=True, env=H.private_env(home), timeout=120)
    if proc.returncode != 0:
        raise LifecycleError(f"the new version does not start: {(proc.stderr or '').strip()[-200:]}")
    return proc.stdout.strip()


class Crash(RuntimeError):
    """Raised by the crash_after test hook to stop an update between two journal steps."""


def _step(store: JobStore, stage: str, crash_after: str | None, fields: dict) -> None:
    store.record("update", stage, **fields)
    if crash_after == stage:
        raise Crash(stage)


def update(home: Path, data: Path, release: Path, *, sha256: str | None = None, run=subprocess.run,
           crash_after: str | None = None, log=print) -> dict:
    with exclusive(data, "update"):
        recover(home, data, log=log)
        return _update(home, data, release, sha256=sha256, run=run, crash_after=crash_after, log=log)


def _update(home: Path, data: Path, release: Path, *, sha256, run, crash_after, log) -> dict:
    old_version = _current_version(home)
    if old_version is None:
        raise LifecycleError("this is not a native install with app/current; in Docker, change the image tag "
                             "(docs/deploy-vps.md, updates)")
    verify_file(release, sha256)
    staging = home / "app" / (".new-" + uuid.uuid4().hex[:8])
    base = Path(os.path.realpath(_venv_python(home / "app" / old_version / "venv")))
    env = H.private_env(home)
    log("  installing the new version into its own environment")
    try:
        r = run([str(base), "-m", "venv", str(staging / "venv")], env=env, capture_output=True, text=True)
        if r.returncode != 0:
            raise LifecycleError("could not make the new environment")
        r = run([str(_venv_python(staging / "venv")), "-m", "pip", "install", "--quiet", str(release)], env=env,
                capture_output=True, text=True)
        if r.returncode != 0:
            raise LifecycleError(f"the release did not install: {(r.stderr or '').strip()[-300:]}")
        new_version = _query(_venv_python(staging / "venv"), home, "import composer; print(composer.__version__)", run)
        new_schema = _query(_venv_python(staging / "venv"), home,
                            "from composer import job_store as j; print(getattr(j, 'DATA_SCHEMA', '1'))", run)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if not VERSION_NAME.fullmatch(new_version) or new_version == old_version:
        shutil.rmtree(staging, ignore_errors=True)
        raise LifecycleError(f"refused: the release is version {new_version!r}, which is already installed")
    if (home / "app" / new_version).exists():
        shutil.rmtree(home / "app" / new_version)  # an earlier, unfinished try at this same version
    os.replace(staging, home / "app" / new_version)
    store = JobStore(data, worker=None)
    old_gen = store.current_generation()
    fields = {"old_version": old_version, "new_version": new_version, "old_generation": old_gen,
              "new_generation": old_gen}
    _step(store, "intent", crash_after, fields)
    if new_schema != store.generation_schema():
        log(f"  migrating a copy of your data to schema {new_schema} (the original stays as it is)")
        store.migrate_copy(new_schema)
        target = next(g for g in ("g1", "g2") if g != old_gen)
        _step(store, "data_migrated", crash_after, dict(fields, new_generation=target))
        store.switch(target)
        fields["new_generation"] = target
        _step(store, "data_switched", crash_after, fields)
    _point_code(home, new_version)
    _step(store, "code_switched", crash_after, fields)
    doctor = run([str(home / "app" / new_version / "venv" / "bin" / "composer"), "doctor", "--parity", "--integrity-only",
                  "--home", str(home), "--data", str(data)], env=env, capture_output=True, text=True)
    if doctor.returncode != 0:
        log("  the new version's doctor failed; undoing the update")
        _undo(home, store, fields, log)
        raise LifecycleError("the update was undone because `composer doctor` failed with the new version:\n"
                             + (doctor.stdout or "")[-1500:])
    _step(store, "committed", None, fields)
    return {"from": old_version, "to": new_version, "data_migrated": fields["new_generation"] != old_gen}


def _undo(home: Path, store: JobStore, fields: dict, log=print) -> None:
    if store.current_generation() != fields["old_generation"]:
        result = store.rollback()
        log(f"  data pointer back to {fields['old_generation']}; briefs exported to {result['export_directory']}")
    if (home / "app" / fields["old_version"]).is_dir() and _current_version(home) != fields["old_version"]:
        _point_code(home, fields["old_version"])
        log(f"  code back to {fields['old_version']}")
    store.record("update", "undone", **fields)


def recover(home: Path | None, data: Path, *, log=print) -> str | None:
    """Undo an update or a restore that stopped half way. Returns what was done, or None. Call it while holding
    the run lock (`exclusive`, or `composer up`'s own)."""
    restored = _recover_restore(data, log)
    if not (data / "current").exists():
        return restored
    store = JobStore(data, worker=None)  # the store's own recovery runs first (unfinished copies, temp pointers)
    last = store.last("update")
    if not last or last["stage"] in ("committed", "undone", "rolled_back"):
        return restored
    fields = {k: last[k] for k in ("old_version", "new_version", "old_generation", "new_generation") if k in last}
    log(f"recovering an interrupted update (stopped after {last['stage']}): undoing it")
    if home is not None:
        _undo(home, store, fields, log)
    else:
        if store.current_generation() != fields.get("old_generation"):
            store.rollback()
        store.record("update", "undone", **fields)
    return "undone"


def rollback(home: Path | None, data: Path, *, data_only: bool = False, log=print) -> dict:
    with exclusive(data, "roll back"):
        recover(home, data, log=log)
        return _rollback(home, data, data_only=data_only)


def _rollback(home: Path | None, data: Path, *, data_only: bool) -> dict:
    store = JobStore(data, worker=None)
    last = store.last("update")
    if not last or last["stage"] != "committed":
        raise LifecycleError("there is no update to roll back")
    fields = {k: last[k] for k in ("old_version", "new_version", "old_generation", "new_generation")}
    out = {"exported_jobs": [], "export_directory": None, "code": None}
    if store.current_generation() != fields["old_generation"]:
        result = store.rollback()
        out.update(exported_jobs=result["exported_jobs"], export_directory=result["export_directory"])
    if not data_only:
        if home is None or not (home / "app" / fields["old_version"]).is_dir():
            raise LifecycleError(f"version {fields['old_version']} is not installed; in Docker, set the previous "
                                 "image tag and run `docker compose up -d`")
        _point_code(home, fields["old_version"])
        out["code"] = fields["old_version"]
    store.record("update", "rolled_back", **fields)
    return out


def migrate_on_start(data: Path, *, schema: str = DATA_SCHEMA, version: str = "", crash_after: str | None = None,
                     log=print) -> bool:
    """A newer image on older data (Docker updates switch the image, not app/current): migrate a COPY, switch the
    pointer, journaled, before serving. `composer rollback --data-only` points back. True when it migrated."""
    if not (data / "current").exists():
        return False
    store = JobStore(data, worker=None)
    if int(store.generation_schema()) >= int(schema):
        return False
    from . import __version__
    old = store.current_generation()
    fields = {"old_version": "previous image", "new_version": version or __version__, "old_generation": old,
              "new_generation": old}
    _step(store, "intent", crash_after, fields)
    log(f"migrating a copy of your data to schema {schema} (the original stays as it is)")
    store.migrate_copy(schema)
    target = next(g for g in ("g1", "g2") if g != old)
    _step(store, "data_migrated", crash_after, dict(fields, new_generation=target))
    store.switch(target)
    fields["new_generation"] = target
    _step(store, "data_switched", crash_after, fields)
    _step(store, "committed", None, fields)
    return True


def check_data_schema(data: Path) -> None:
    """Refuse to serve a generation newer than this code understands (an old image on migrated data)."""
    if not (data / "current").exists():
        return
    store = JobStore(data, worker=None)
    have = store.generation_schema()
    if int(have) > int(DATA_SCHEMA):
        raise LifecycleError(f"refused: this data was migrated to schema {have} by a newer Composer; this version "
                             f"reads schema {DATA_SCHEMA}. Run `composer rollback --data-only` with the newer "
                             "version, or start the newer version again")


# ------------------------------------------------------------------------------------------------ uninstall

def uninstall(home: Path, data: Path, *, delete_data: bool = False, confirm=lambda question: False,
              log=print) -> dict:
    with exclusive(data if (data / "current").exists() else data / "nonexistent", "uninstall"):
        return _uninstall(home, data, delete_data=delete_data, confirm=confirm)


def _uninstall(home: Path, data: Path, *, delete_data: bool, confirm) -> dict:
    doc = H.load_manifest(home)
    problems = H.check_manifest(home, doc, data)
    problems += [p for p in H.check_manifest(home, doc, home / H.DATA_DIR) if p not in problems]
    if problems:
        raise LifecycleError("refused: the install manifest is not safe to act on, nothing was removed:\n  - "
                             + "\n  - ".join(problems))
    data_entry = next((e for e in doc["entries"] if e["kind"] == "user-data"), None)
    data_inside = data_entry is not None and Path(os.path.realpath(home / H.DATA_DIR)) == Path(os.path.realpath(data))
    if delete_data:
        if not data_inside:
            raise LifecycleError(f"refused: your data at {data} is not this install's data folder; "
                                 "remove it yourself if you mean to")
        if not confirm(f"Delete your data folder {data}, with every brief, setting, backup and your key? "
                       "This cannot be undone. Type DELETE to confirm: "):
            raise LifecycleError("not confirmed; nothing was removed")
    removed, kept_reused = [], []
    created = [e for e in doc["entries"] if e["kind"] == "created"]
    for entry in sorted(created, key=lambda e: e["path"].count("/"), reverse=True):
        if entry["path"] == H.MARKER and not delete_data:
            continue  # keeps the folder recognisable as a Composer install, so setup can pick your data up again
        if H.remove_entry(home, entry["path"]):
            removed.append(entry["path"])
    kept_reused = [e["path"] for e in doc["entries"] if e["kind"] == "reused"]
    if delete_data:
        if os.path.islink(home / H.DATA_DIR):
            link_to = os.readlink(home / H.DATA_DIR)
            H.remove_entry(home, H.DATA_DIR)
            removed.append(f"{H.DATA_DIR} (a link; the folder it pointed to, {link_to}, was left as it is)")
        elif H.remove_entry(home, H.DATA_DIR):
            removed.append(H.DATA_DIR)
        H.remove_entry(home, H.MARKER)
        (home / H.MANIFEST).unlink(missing_ok=True)
        left = sorted(os.listdir(home)) if home.exists() else []
        if not left and doc.get("home_created"):
            home.rmdir()
            removed.append(str(home))
    else:
        doc["entries"] = [e for e in doc["entries"] if e["kind"] == "user-data" or e["path"] == H.MARKER]
        doc["state"] = "uninstalled-data-kept"
        H.save_manifest(home, doc)
        left = sorted(os.listdir(home))
    others = [n for n in (left if home.exists() else []) if n not in (H.DATA_DIR, H.MARKER, H.MANIFEST)]
    return {"removed": removed, "kept_data": None if delete_data else str(data), "reused_untouched": kept_reused,
            "not_ours_left_alone": others}
