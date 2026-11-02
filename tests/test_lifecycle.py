"""Uninstall, backup/restore and update/rollback: what they may touch, and what they must never touch."""
import io
import json
import os
import tarfile
import unittest
from pathlib import Path
from unittest import mock

from install_helpers import fake_home, fake_model_pair, snapshot

from composer import home as H, installer, lifecycle as L, settings as S
from composer.job_store import JobStore


def install(home: Path, **answers_toml) -> Path:
    target = home / ".lensmith-composer"
    installer.run(home=target, data=None, answers_file=None, assume_yes=True, reconfigure=[], data_only=False,
                  out=lambda *_: None, interactive=False)
    return target


def saved_job(data: Path, text: str = "a brief") -> str:
    def worker(job, draft_ready):
        draft_ready({"lens": text, "cards": [], "transcript": text})
        return {"status": "ok", "claim_evidence": {"job": job["job"], "draft_sha256": job["draft_sha256"]}}
    store = JobStore(data, worker=worker)
    job = store.submit({"sources": ["google-ai"], "lens": text, "insights": 3})["job"]
    store.wait(job, 10)
    store.save(job)
    return job


class UninstallTests(unittest.TestCase):
    def test_keeps_data_without_delete_data_and_leaves_outside_unchanged(self):
        with fake_home() as home:
            target = install(home)
            outside = home / "my-kokoro"
            model, voices, _ = fake_model_pair(outside)
            doc = H.load_manifest(target)
            H.add_entry(doc, str(model), "reused", sha256="x", size=1)
            H.add_entry(doc, str(voices), "reused", sha256="y", size=1)
            H.save_manifest(target, doc)
            (home / "notes.txt").write_text("not Composer's", encoding="utf-8")
            data = target / "data"
            job = saved_job(data)
            data_before = snapshot(data)
            outside_before = snapshot(home, skip=target)
            result = L.uninstall(target, data, delete_data=False)
            self.assertEqual(snapshot(data), data_before)          # every brief, setting and byte of data kept
            self.assertEqual(snapshot(home, skip=target), outside_before)  # the reused model and the rest unchanged
            self.assertEqual(sorted(os.listdir(target)), sorted(["data", H.MARKER, H.MANIFEST]))
            self.assertIn("bin", result["removed"])
            self.assertEqual(sorted(result["reused_untouched"]), sorted([str(model), str(voices)]))
            self.assertTrue((data / "generations" / "g1" / "jobs" / job / "saved.json").is_file())
            # setup picks the kept data up again
            install(home)
            self.assertTrue((data / "generations" / "g1" / "jobs" / job / "saved.json").is_file())

    def test_delete_data_must_be_confirmed(self):
        with fake_home() as home:
            target = install(home)
            before = snapshot(target)
            with self.assertRaises(L.LifecycleError):
                L.uninstall(target, target / "data", delete_data=True, confirm=lambda q: False)
            self.assertEqual(snapshot(target), before)
            outside_before = snapshot(home, skip=target)
            L.uninstall(target, target / "data", delete_data=True, confirm=lambda q: True)
            self.assertFalse(target.exists())
            self.assertEqual(snapshot(home, skip=target), outside_before)

    def test_delete_data_refuses_data_that_is_not_this_installs(self):
        with fake_home() as home:
            target = install(home)
            elsewhere = home / "elsewhere-data"
            S.generation_dir(elsewhere)
            before = snapshot(home)
            with self.assertRaises(L.LifecycleError):
                L.uninstall(target, elsewhere, delete_data=True, confirm=lambda q: True)
            self.assertEqual(snapshot(home), before)

    def test_a_tampered_manifest_is_refused_with_nothing_removed(self):
        for bad in ({"path": "../notes", "kind": "created"}, {"path": "/etc-like", "kind": "created"},
                    {"path": "data", "kind": "created"}, {"path": "data/generations", "kind": "created"},
                    {"path": "", "kind": "created"}, {"path": "bin/../data", "kind": "created"},
                    {"path": "cache", "kind": "user-data"}):
            with self.subTest(entry=bad), fake_home() as home:
                target = install(home)
                (home / "notes").write_text("keep", encoding="utf-8")
                doc = H.load_manifest(target)
                doc["entries"].append(bad)
                H.save_manifest(target, doc)
                before = snapshot(home)
                with self.assertRaises(L.LifecycleError):
                    L.uninstall(target, target / "data", delete_data=False)
                self.assertEqual(snapshot(home), before)

    def test_a_created_path_that_is_a_link_is_removed_as_a_link(self):
        with fake_home() as home:
            target = install(home)
            precious = home / "precious"
            precious.mkdir()
            (precious / "file.txt").write_text("keep", encoding="utf-8")
            os.symlink(precious, target / "models")
            (target / "cache" / "inside-link").symlink_to(precious)
            doc = H.load_manifest(target)
            H.add_entry(doc, "models", "created")
            H.save_manifest(target, doc)
            before = snapshot(precious)
            L.uninstall(target, target / "data", delete_data=False)
            self.assertFalse(os.path.lexists(target / "models"))
            self.assertEqual(snapshot(precious), before)

    def test_a_linked_parent_cannot_lead_outside(self):
        with fake_home() as home:
            target = install(home)
            outside = home / "outside"
            (outside / "inner").mkdir(parents=True)
            os.symlink(outside, target / "tmp-link")
            doc = H.load_manifest(target)
            doc["entries"].append({"path": "tmp-link/inner", "kind": "created"})
            H.save_manifest(target, doc)
            with self.assertRaises(L.LifecycleError):
                L.uninstall(target, target / "data")
            self.assertTrue((outside / "inner").is_dir())

    def test_refused_while_the_app_runs(self):
        with fake_home() as home:
            target = install(home)
            lock = L.hold_run_lock(target / "data")
            try:
                with self.assertRaises(L.LifecycleError):
                    L.uninstall(target, target / "data")
                self.assertTrue((target / "bin").is_dir())
            finally:
                lock.close()


class BackupRestoreTests(unittest.TestCase):
    def test_round_trip(self):
        with fake_home() as home:
            target = install(home)
            data = target / "data"
            S.write_secret(data, "ANTHROPIC_API_KEY", "test-key-value-for-setup-only")
            job = saved_job(data, "first")
            gen = S.generation_dir(data)
            before = snapshot(gen)
            archive = L.backup(data)
            with tarfile.open(archive) as tar:
                names = tar.getnames()
            self.assertNotIn("secrets.env", names)
            self.assertIn(f"generation/jobs/{job}/job.json", names)
            saved_job(data, "second")  # a change after the backup, which restore must replace
            result = L.restore(data, archive)
            self.assertEqual({k: v[:2] for k, v in snapshot(gen).items() if k != "."},
                             {k: v[:2] for k, v in before.items() if k != "."})
            self.assertTrue(Path(result["safety_backup"]).is_file())
            self.assertTrue(Path(result["replaced_kept_at"]).is_dir())
            self.assertEqual(S.read_secrets(data), {"ANTHROPIC_API_KEY": "test-key-value-for-setup-only"})
            with_key = L.backup(data, include_secrets=True)
            with tarfile.open(with_key) as tar:
                self.assertIn("secrets.env", tar.getnames())

    def test_keep_prunes_only_scheduled_backups(self):
        with fake_home() as home:
            data = install(home) / "data"
            folder = data / "backups"
            folder.mkdir(parents=True, exist_ok=True)
            for n in range(5):
                (folder / f"composer-backup-2026010{n}T000000Z-weekly.tar.gz").write_bytes(b"x")
            manual = [folder / f"composer-backup-2025010{n}T000000Z.tar.gz" for n in range(3)]
            for path in manual:
                path.write_bytes(b"made by hand")
            (folder / "my-own-file.tar.gz").write_bytes(b"mine")
            L.backup(data, keep=3, tag="weekly")
            names = sorted(os.listdir(folder))
            self.assertIn("my-own-file.tar.gz", names)
            self.assertTrue(all(p.exists() for p in manual))  # backups you made yourself are never pruned
            self.assertEqual(len([n for n in names if n.endswith("-weekly.tar.gz")]), 3)

    def test_backup_out_folder_keeps_its_own_mode(self):
        with fake_home() as home:
            data = install(home) / "data"
            out = home / "shared"
            out.mkdir(mode=0o755)
            os.chmod(out, 0o755)
            L.backup(data, out_dir=out)
            self.assertEqual(os.stat(out).st_mode & 0o777, 0o755)

    def make_archive(self, members, meta_files=None):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            meta = {"schema": L.BACKUP_SCHEMA, "data_schema": "1", "generation": "g1", "files": meta_files or {}}
            blob = json.dumps(meta).encode()
            info = tarfile.TarInfo("backup.json")
            info.size = len(blob)
            tar.addfile(info, io.BytesIO(blob))
            for info, data in members:
                tar.addfile(info, io.BytesIO(data) if data is not None else None)
        return buf.getvalue()

    def test_unsafe_archives_are_refused_and_nothing_changes(self):
        def reg(name, data=b"x"):
            i = tarfile.TarInfo(name)
            i.size = len(data)
            return i, data

        def link(name, kind, target):
            i = tarfile.TarInfo(name)
            i.type, i.linkname = kind, target
            return i, None

        cases = {"absolute": [reg("/generation/x")], "dotdot": [reg("generation/../../x")],
                 "symlink": [link("generation/x", tarfile.SYMTYPE, "/elsewhere")],
                 "hardlink": [link("generation/x", tarfile.LNKTYPE, "backup.json")],
                 "unknown file": [reg("models/kokoro.onnx")], "unlisted": [reg("generation/extra.json")]}
        with fake_home() as home:
            data = install(home) / "data"
            saved_job(data)
            for name, members in cases.items():
                with self.subTest(case=name):
                    path = home.parent / f"bad-{name.replace(' ', '-')}.tar.gz"
                    path.write_bytes(self.make_archive(members))
                    before = snapshot(data)
                    with self.assertRaises(L.LifecycleError):
                        L.restore(data, path)
                    self.assertEqual(snapshot(data), before)
            path = home.parent / "tampered.tar.gz"
            path.write_bytes(self.make_archive([reg("generation/VERSION", b"1\n")], {"VERSION": "0" * 64}))
            before = snapshot(data)
            with self.assertRaises(L.LifecycleError):
                L.restore(data, path)
            self.assertEqual(snapshot(data), before)


class FakeRun:
    """Stands in for subprocess.run in update(): makes the new environment, reports a version and a data schema,
    and answers the new version's doctor with `doctor_rc`."""

    def __init__(self, version="0.3.0", schema="1", doctor_rc=0):
        self.version, self.schema, self.doctor_rc = version, schema, doctor_rc
        self.calls = []

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        out, rc = "", 0
        if "-m" in argv and argv[argv.index("-m") + 1] == "venv":
            venv = Path(argv[-1])
            (venv / "bin").mkdir(parents=True)
            (venv / "bin" / "python").write_text("", encoding="utf-8")
        elif "-c" in argv:
            out = self.version if "__version__" in argv[-1] else self.schema
        elif "doctor" in argv:
            rc = self.doctor_rc
        return mock.Mock(returncode=rc, stdout=out, stderr="")


class UpdateRollbackTests(unittest.TestCase):
    def native(self, home):
        target = install(home)
        (target / "app" / "0.2.0" / "venv" / "bin").mkdir(parents=True)
        (target / "app" / "0.2.0" / "venv" / "bin" / "python").write_text("", encoding="utf-8")
        os.symlink("0.2.0", target / "app" / "current")
        release = home.parent / "lensmith_composer-0.3.0.tar.gz"
        release.write_bytes(b"a release")
        return target, target / "data", release

    def sha(self, path):
        import hashlib
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_update_needs_a_matching_checksum(self):
        with fake_home() as home:
            target, data, release = self.native(home)
            for digest in (None, "0" * 64):
                with self.assertRaises(L.LifecycleError):
                    L.update(target, data, release, sha256=digest, run=FakeRun(), log=lambda *_: None)
            self.assertEqual(os.readlink(target / "app" / "current"), "0.2.0")

    def test_update_then_rollback_with_a_data_migration(self):
        with fake_home() as home:
            target, data, release = self.native(home)
            before = saved_job(data, "before the update")
            result = L.update(target, data, release, sha256=self.sha(release), run=FakeRun(schema="2"),
                              log=lambda *_: None)
            self.assertEqual(result, {"from": "0.2.0", "to": "0.3.0", "data_migrated": True})
            self.assertEqual(os.readlink(target / "app" / "current"), "0.3.0")
            store = JobStore(data, worker=None)
            self.assertEqual((store.current_generation(), store.generation_schema()), ("g2", "2"))
            self.assertEqual(store.generation_schema("g1"), "1")  # the original is untouched
            after = saved_job(data, "made after the update")
            out = L.rollback(target, data, log=lambda *_: None)
            self.assertEqual(os.readlink(target / "app" / "current"), "0.2.0")
            self.assertEqual(JobStore(data, worker=None).current_generation(), "g1")
            self.assertIn(after, out["exported_jobs"])
            self.assertTrue((Path(out["export_directory"]) / after / "job.json").is_file())
            self.assertTrue((data / "generations" / "g1" / "jobs" / before).is_dir())
            with self.assertRaises(L.LifecycleError):
                L.rollback(target, data, log=lambda *_: None)  # nothing left to roll back

    def test_a_failing_doctor_undoes_the_update(self):
        with fake_home() as home:
            target, data, release = self.native(home)
            with self.assertRaises(L.LifecycleError):
                L.update(target, data, release, sha256=self.sha(release), run=FakeRun(schema="2", doctor_rc=1),
                         log=lambda *_: None)
            self.assertEqual(os.readlink(target / "app" / "current"), "0.2.0")
            self.assertEqual(JobStore(data, worker=None).current_generation(), "g1")
            self.assertEqual(JobStore(data, worker=None).last("update")["stage"], "undone")

    def test_an_update_stopped_at_any_step_is_undone_at_the_next_start(self):
        for stage in ("intent", "data_migrated", "data_switched", "code_switched"):
            with self.subTest(stage=stage), fake_home() as home:
                target, data, release = self.native(home)
                with self.assertRaises(L.Crash):
                    L.update(target, data, release, sha256=self.sha(release), run=FakeRun(schema="2"),
                             crash_after=stage, log=lambda *_: None)
                self.assertEqual(L.recover(target, data, log=lambda *_: None), "undone")
                self.assertEqual(os.readlink(target / "app" / "current"), "0.2.0")
                store = JobStore(data, worker=None)
                self.assertEqual(store.current_generation(), "g1")
                self.assertEqual(store.last("update")["stage"], "undone")
                self.assertIsNone(L.recover(target, data, log=lambda *_: None))  # nothing left to do

    def test_the_container_path_migrates_on_start_and_rolls_back_data_only(self):
        with fake_home() as home:
            data = home / "volume"
            S.generation_dir(data)
            saved_job(data)
            self.assertTrue(L.migrate_on_start(data, schema="2", log=lambda *_: None))
            self.assertFalse(L.migrate_on_start(data, schema="2", log=lambda *_: None))
            with self.assertRaises(L.LifecycleError):
                L.check_data_schema(data)  # this code reads schema 1: an old image refuses migrated data
            out = L.rollback(None, data, data_only=True, log=lambda *_: None)
            self.assertIsNone(out["code"])
            L.check_data_schema(data)
            self.assertEqual(JobStore(data, worker=None).current_generation(), "g1")


if __name__ == "__main__":
    unittest.main()
