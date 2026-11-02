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


def release_file(folder: Path, version: str = "0.3.0", name: str = "lensmith-composer") -> Path:
    """A small sdist-shaped release: <name>-<version>/PKG-INFO is all update() reads before installing it."""
    path = folder / f"lensmith_composer-{version.replace('/', '_')}.tar.gz"
    blob = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n".encode()
    with tarfile.open(path, "w:gz") as tar:
        info = tarfile.TarInfo(f"lensmith_composer-{version.replace('/', '_')}/PKG-INFO")
        info.size = len(blob)
        tar.addfile(info, io.BytesIO(blob))
    return path


class FakeRun:
    """Stands in for subprocess.run in update(): makes the new environment, reports a version and a data schema,
    starts the new `composer --version` (or not: `starts`), and answers the new version's doctor with `doctor_rc`
    (or raises `doctor_raises`, as a script whose interpreter is gone does)."""

    def __init__(self, version="0.3.0", schema="1", doctor_rc=0, starts=True, doctor_raises=None, parser_rc=0):
        self.version, self.schema, self.doctor_rc = version, schema, doctor_rc
        self.starts, self.doctor_raises, self.parser_rc = starts, doctor_raises, parser_rc
        self.calls = []

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        out, rc = "", 0
        if "-c" in argv and "install_trafilatura" in argv[-1]:
            rc = self.parser_rc
        elif "-m" in argv and argv[argv.index("-m") + 1] == "venv":
            venv = Path(argv[-1])
            (venv / "bin").mkdir(parents=True)
            (venv / "bin" / "python").write_text("", encoding="utf-8")
            (venv / "bin" / "composer").write_text(f"#!{venv / 'bin' / 'python'}\n", encoding="utf-8")
        elif "-c" in argv:
            out = self.version if "__version__" in argv[-1] else self.schema
        elif "--version" in argv:
            if not self.starts:
                raise FileNotFoundError(2, "No such file or directory", argv[0])
            out = f"composer {self.version}"
        elif "doctor" in argv:
            if self.doctor_raises:
                raise self.doctor_raises
            rc = self.doctor_rc
        return mock.Mock(returncode=rc, stdout=out, stderr="")


class UpdateRollbackTests(unittest.TestCase):
    def native(self, home):
        target = install(home)
        (target / "app" / "0.2.0" / "venv" / "bin").mkdir(parents=True)
        (target / "app" / "0.2.0" / "venv" / "bin" / "python").write_text("", encoding="utf-8")
        os.symlink("0.2.0", target / "app" / "current")
        return target, target / "data", release_file(home.parent)

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

    def test_the_new_environment_is_made_in_its_final_folder(self):
        with fake_home() as home:
            target, data, release = self.native(home)
            run = FakeRun()
            L.update(target, data, release, sha256=self.sha(release), run=run, log=lambda *_: None)
            venvs = [argv[-1] for argv in run.calls if "-m" in argv and argv[argv.index("-m") + 1] == "venv"]
            self.assertEqual(venvs, [str(target / "app" / "0.3.0" / "venv")])  # never made elsewhere and moved
            self.assertEqual(sorted(os.listdir(target / "app")), ["0.2.0", "0.3.0", "current"])
            doctor = next(argv for argv in run.calls if "doctor" in argv)
            self.assertEqual(doctor[0], str(L._venv_script(target / "app" / "0.3.0" / "venv", "composer")))

    def parser_on(self, data):
        cfg = S.load(data)
        cfg["extraction"] = {"trafilatura": True}
        S.save(data, cfg)

    def test_the_article_parser_setup_installed_is_installed_into_the_new_version(self):
        with fake_home() as home:
            target, data, release = self.native(home)
            run = FakeRun()
            L.update(target, data, release, sha256=self.sha(release), run=run, log=lambda *_: None)
            self.assertFalse([a for a in run.calls if "install_trafilatura" in a[-1]])  # not asked for: not installed
        with fake_home() as home:
            target, data, release = self.native(home)
            self.parser_on(data)
            run = FakeRun()
            L.update(target, data, release, sha256=self.sha(release), run=run, log=lambda *_: None)
            parser = [a for a in run.calls if "install_trafilatura" in a[-1]]
            self.assertEqual(len(parser), 1)
            self.assertEqual(parser[0][0], str(L._venv_python(target / "app" / "0.3.0" / "venv")))
            doctor = next(i for i, a in enumerate(run.calls) if "doctor" in a)
            self.assertLess(run.calls.index(parser[0]), doctor)  # before the new version's doctor checks it
            self.assertEqual(os.readlink(target / "app" / "current"), "0.3.0")

    def test_a_parser_that_does_not_install_leaves_the_old_version(self):
        with fake_home() as home:
            target, data, release = self.native(home)
            self.parser_on(data)
            with self.assertRaises(L.LifecycleError) as ctx:
                L.update(target, data, release, sha256=self.sha(release), run=FakeRun(parser_rc=1),
                         log=lambda *_: None)
            self.assertIn("article parser", str(ctx.exception))
            self.assertEqual(os.readlink(target / "app" / "current"), "0.2.0")
            self.assertEqual(sorted(os.listdir(target / "app")), ["0.2.0", "current"])

    def test_a_new_version_that_does_not_start_is_never_switched_to(self):
        for run in (FakeRun(starts=False), FakeRun(version="9.9.9")):
            with self.subTest(run=run.__dict__), fake_home() as home:
                target, data, release = self.native(home)
                with self.assertRaises(L.LifecycleError):
                    L.update(target, data, release, sha256=self.sha(release), run=run, log=lambda *_: None)
                self.assertEqual(os.readlink(target / "app" / "current"), "0.2.0")
                self.assertEqual(sorted(os.listdir(target / "app")), ["0.2.0", "current"])
                self.assertIsNone(JobStore(data, worker=None).last("update"))  # nothing was journaled or switched

    def test_any_failure_after_the_switch_undoes_the_update(self):
        for run in (FakeRun(schema="2", doctor_raises=FileNotFoundError(2, "No such file or directory")),
                    FakeRun(schema="2", doctor_raises=KeyboardInterrupt())):
            with self.subTest(raises=type(run.doctor_raises).__name__), fake_home() as home:
                target, data, release = self.native(home)
                with self.assertRaises((L.LifecycleError, KeyboardInterrupt)):
                    L.update(target, data, release, sha256=self.sha(release), run=run, log=lambda *_: None)
                self.assertEqual(os.readlink(target / "app" / "current"), "0.2.0")
                self.assertEqual(JobStore(data, worker=None).current_generation(), "g1")
                self.assertEqual(JobStore(data, worker=None).last("update")["stage"], "undone")
                self.assertEqual(sorted(os.listdir(target / "app")), ["0.2.0", "current"])

    def test_a_file_that_is_not_a_composer_release_is_refused_before_anything_is_made(self):
        with fake_home() as home:
            target, data, _ = self.native(home)
            (home.parent / "other").mkdir()
            other = release_file(home.parent / "other", name="other")
            plain = home.parent / "notes.zip"
            plain.write_bytes(b"not a release")
            for release in (other, plain):
                with self.subTest(release=release.name):
                    with self.assertRaises(L.LifecycleError):
                        L.update(target, data, release, sha256=self.sha(release), run=FakeRun(), log=lambda *_: None)
                    self.assertEqual(sorted(os.listdir(target / "app")), ["0.2.0", "current"])

    def test_rollback_after_an_interrupted_update_undoes_it(self):
        with fake_home() as home:
            target, data, release = self.native(home)
            with self.assertRaises(L.Crash):
                L.update(target, data, release, sha256=self.sha(release), run=FakeRun(schema="2"),
                         crash_after="code_switched", log=lambda *_: None)
            out = L.rollback(target, data, log=lambda *_: None)
            self.assertEqual((out["code"], out.get("recovered")), ("0.2.0", True))
            self.assertEqual(os.readlink(target / "app" / "current"), "0.2.0")
            self.assertEqual(JobStore(data, worker=None).current_generation(), "g1")
            with self.assertRaises(L.LifecycleError):
                L.rollback(target, data, log=lambda *_: None)  # nothing left to roll back

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
