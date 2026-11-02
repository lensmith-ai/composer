"""One test per finding of the independent safety review of setup, uninstall, restore, update and the server."""
import http.client
import ipaddress
import json
import os
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from helpers import ROOT
from install_helpers import FakeRender, fake_home, snapshot
from test_lifecycle import FakeRun, install, release_file, saved_job

from composer import home as H, installer, lifecycle as L, narration as N, server, settings as S
from composer.job_store import JobStore
from composer.registry import Registry


class DataIsNeverRemovableTests(unittest.TestCase):
    def test_a_data_spelling_in_another_case_is_refused(self):
        # on a case-insensitive disk "Data" IS the data folder; the name is refused whatever the disk
        for rel in ("Data", "DATA", "dAtA/generations"):
            with self.subTest(rel=rel), fake_home() as home:
                target = install(home)
                doc = H.load_manifest(target)
                doc["entries"].append({"path": rel, "kind": "created"})
                H.save_manifest(target, doc)
                before = snapshot(target)
                with self.assertRaises(L.LifecycleError):
                    L.uninstall(target, target / "data")
                self.assertEqual(snapshot(target), before)

    def test_a_data_folder_inside_the_app_folder_must_be_data(self):
        with fake_home() as home:
            target = home / ".lensmith-composer"
            for inside in (target / "cache" / "briefs", target, target / "app"):
                with self.subTest(data=inside):
                    with self.assertRaises(installer.SetupError):
                        installer.run(home=target, data=inside, answers_file=None, assume_yes=True, reconfigure=[],
                                      data_only=False, out=lambda *_: None, interactive=False)
                    self.assertFalse(target.exists())

    def test_the_recorded_data_path_is_protected_without_the_variable(self):
        with fake_home() as home:
            target = install(home)
            doc = H.load_manifest(target)
            self.assertEqual(doc["data_path"], str((target / "data").resolve()))


class BackupAndRestoreFixTests(unittest.TestCase):
    def test_an_interrupted_restore_puts_the_old_data_back(self):
        with fake_home() as home:
            data = install(home) / "data"
            job = saved_job(data, "before")
            archive = L.backup(data)
            gen = S.generation_dir(data)
            before = {k: v[:2] for k, v in snapshot(gen).items() if k != "."}
            with self.assertRaises(L.Crash):
                L.restore(data, archive, crash_after="old_moved")
            self.assertFalse(gen.exists())  # stopped between the two renames
            self.assertEqual(L.recover(None, data, log=lambda *_: None), "undone")
            self.assertEqual({k: v[:2] for k, v in snapshot(gen).items() if k != "."}, before)
            self.assertTrue((gen / "jobs" / job / "saved.json").is_file())
            self.assertIsNone(L.recover(None, data, log=lambda *_: None))

    def test_restore_and_update_wait_for_the_app(self):
        with fake_home() as home:
            data = install(home) / "data"
            archive = L.backup(data)
            lock = L.hold_run_lock(data)
            try:
                with self.assertRaises(L.LifecycleError):
                    L.restore(data, archive)
                with self.assertRaises(L.LifecycleError):
                    L.rollback(None, data, data_only=True, log=lambda *_: None)
            finally:
                lock.close()

    def test_a_backup_reads_each_file_once(self):
        with fake_home() as home:
            data = install(home) / "data"
            saved_job(data)
            real_read = Path.read_bytes
            calls = []

            def counting(path):
                calls.append(str(path))
                return real_read(path)
            with mock.patch.object(Path, "read_bytes", counting):
                archive = L.backup(data)
            gen_reads = [c for c in calls if "/generations/" in c]
            self.assertEqual(len(gen_reads), len(set(gen_reads)))
            L.read_backup(archive)  # and the archive agrees with its own list


class UpdateFixTests(unittest.TestCase):
    def test_a_release_named_dotdot_is_refused(self):
        with fake_home() as home:
            target = install(home)
            (target / "app" / "0.2.0" / "venv" / "bin").mkdir(parents=True)
            (target / "app" / "0.2.0" / "venv" / "bin" / "python").write_text("", encoding="utf-8")
            os.symlink("0.2.0", target / "app" / "current")
            import hashlib
            for name in ("..", ".", ".hidden", "a/b", "current"):
                with self.subTest(version=name):
                    release = release_file(home.parent, version=name)
                    with self.assertRaises(L.LifecycleError):
                        L.update(target, target / "data", release,
                                 sha256=hashlib.sha256(release.read_bytes()).hexdigest(),
                                 run=FakeRun(version=name), log=lambda *_: None)
                    self.assertTrue((target / "data" / "current").is_file())
                    self.assertTrue((target / "bin").is_dir())


class ServerFixTests(unittest.TestCase):
    def test_an_absurd_range_is_answered_not_crashed(self):
        from test_narration import ON, Served
        with fake_home() as home:
            s = Served(home, ON, FakeRender())
            try:
                job = s.compose()
                name = s.job(job)["audio"]["file"]
                status, body, _ = s.req("GET", f"/data/live/{job}/{name}", headers={"Range": "bytes=" + "9" * 5000 + "-"})
                self.assertEqual(status, 200)
                self.assertTrue(body.startswith(b"ID3"))
            finally:
                s.close()

    def test_the_loopback_exemption_is_only_the_health_check(self):
        from test_up import ProxyModeTests
        t = ProxyModeTests()
        t.setUp()
        self.assertEqual(t.call("127.0.0.1", "GET", "/health", {"Host": "127.0.0.1:8765"}), 200)
        self.assertEqual(t.call("127.0.0.1", "GET", "/data/options.json", {"Host": "127.0.0.1:8765"}), 403)
        self.assertEqual(t.call("127.0.0.1", "GET", "/app/", {"Host": "localhost:8765"}), 403)
        self.assertEqual(t.call("127.0.0.1", "POST", "/retention", {"Host": "127.0.0.1:8765",
                                                                   "Content-Type": "application/json",
                                                                   "X-Composer-CSRF": "same-origin",
                                                                   "Content-Length": "2"}, b"{}"), 403)


class NarrationAndSecretsFixTests(unittest.TestCase):
    def test_a_failed_runtime_install_leaves_nothing_that_looks_installed(self):
        with fake_home() as home:
            def failing(argv, **kw):
                if "venv" in argv:
                    Path(argv[-1], "bin").mkdir(parents=True)
                    Path(argv[-1], "bin", "python").write_text("", encoding="utf-8")
                    return mock.Mock(returncode=0)
                raise subprocess.CalledProcessError(1, argv)
            with mock.patch.object(N.subprocess, "run", failing):
                with self.assertRaises(N.NarrationError):
                    N.install_runtime(home, log=lambda *_: None)
            self.assertFalse((home / "narration" / "venv").exists())
            with mock.patch.object(N, "has_runtime_here", return_value=False):
                self.assertIsNone(N.runtime_python(home, {}))

    def test_the_worker_lowers_its_own_priority(self):
        text = N.WORKER.read_text(encoding="utf-8")
        self.assertIn('os.nice(int(req["nice"]))', text)
        self.assertNotIn("preexec_fn", (ROOT / "composer" / "narration" / "__init__.py").read_text(encoding="utf-8"))

    @unittest.skipUnless(os.name == "posix", "file modes")
    def test_a_loose_key_file_is_refused_not_silently_rewritten(self):
        with fake_home() as home:
            data = install(home) / "data"
            S.write_secret(data, "ANTHROPIC_API_KEY", "first-key-value-for-test")
            os.chmod(S.secrets_path(data), 0o644)
            with self.assertRaises(S.SettingsError):
                S.write_secret(data, "OPENAI_API_KEY", "second-key-value-for-test")
            os.chmod(S.secrets_path(data), 0o600)
            self.assertEqual(S.read_secrets(data), {"ANTHROPIC_API_KEY": "first-key-value-for-test"})


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "setup.sh is a POSIX shell script")
class SetupShFixTests(unittest.TestCase):
    def test_a_moved_install_is_refused_before_any_write(self):
        with fake_home() as home:
            target = install(home)
            moved = home / "moved"
            target.rename(moved)
            before = snapshot(home)
            run = subprocess.run(["sh", str(ROOT / "setup.sh"), "--home", str(moved), "--yes"], capture_output=True,
                                 text=True, timeout=60)
            self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
            self.assertIn("another folder", run.stderr)
            self.assertEqual(snapshot(home), before)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root can read any folder")
    def test_an_unreadable_folder_is_refused(self):
        with fake_home() as home:
            locked = home / "locked"
            locked.mkdir()
            (locked / "keep").write_text("x", encoding="utf-8")
            os.chmod(locked, 0o300)
            try:
                run = subprocess.run(["sh", str(ROOT / "setup.sh"), "--home", str(locked), "--yes"],
                                     capture_output=True, text=True, timeout=60)
                self.assertEqual(run.returncode, 2)
            finally:
                os.chmod(locked, 0o700)
            self.assertTrue((locked / "keep").is_file())


class LateReviewFixTests(unittest.TestCase):
    """The first reviewer's report arrived after the fixes above; these cover what it added."""

    def test_uninstall_removes_only_what_setup_creates(self):
        with fake_home() as home:
            target = install(home)
            (target / "notes.txt").write_text("mine", encoding="utf-8")
            doc = H.load_manifest(target)
            doc["entries"].append({"path": "notes.txt", "kind": "created"})
            H.save_manifest(target, doc)
            before = snapshot(target)
            with self.assertRaises(L.LifecycleError):
                L.uninstall(target, target / "data")
            self.assertEqual(snapshot(target), before)

    def test_native_setup_ignores_composer_data_from_the_shell(self):
        with fake_home() as home:
            elsewhere = home / "elsewhere"
            with mock.patch.dict(os.environ, {"COMPOSER_DATA": str(elsewhere)}):
                target = install(home)
            self.assertFalse(elsewhere.exists())
            self.assertTrue((target / "data" / "current").is_file())

    def test_no_key_reaches_a_child_process(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k1-for-test", "OPENAI_API_KEY": "k2-for-test"}):
            env = H.private_env(Path("/tmp/x"))
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("OPENAI_API_KEY", env)

    def test_a_failed_download_leaves_no_partial_file(self):
        class Broken:
            def __init__(self, *a, **k):
                self.n = 0

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def geturl(self):
                return "https://example.org/x"

            def read(self, size):
                self.n += 1
                if self.n > 1:
                    raise OSError("connection reset")
                return b"x" * 10
        with fake_home() as home:
            with self.assertRaises(OSError):
                N.download(home, log=lambda *_: None, opener=Broken)
            self.assertEqual(list((home / "models" / "kokoro").glob("*")), [])

    def test_an_archive_without_its_schema_file_is_refused(self):
        import io
        import tarfile
        with fake_home() as home:
            data = install(home) / "data"
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as tar:
                blob = b"{}"
                meta = json.dumps({"schema": L.BACKUP_SCHEMA, "data_schema": "1", "files": {
                    "index.json": __import__("hashlib").sha256(blob).hexdigest()}}).encode()
                for name, content in (("generation/index.json", blob), ("backup.json", meta)):
                    info = tarfile.TarInfo(name)
                    info.size = len(content)
                    tar.addfile(info, io.BytesIO(content))
            path = home.parent / "noversion.tar.gz"
            path.write_bytes(buf.getvalue())
            before = snapshot(data)
            with self.assertRaises(L.LifecycleError):
                L.restore(data, path)
            self.assertEqual(snapshot(data), before)

    @unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "setup.sh is a POSIX shell script")
    def test_setup_sh_runs_every_check_before_writing(self):
        with fake_home() as home:
            answers = home.parent / "bad.toml"
            answers.write_text("[provider]\nkey_from_env = \"ANTHROPIC_API_KEY\"\n", encoding="utf-8")  # unset
            before = snapshot(home)
            run = subprocess.run(["sh", str(ROOT / "setup.sh"), "--answers", str(answers)], capture_output=True,
                                 text=True, timeout=120)
            self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
            self.assertIn("nothing was written", run.stderr)
            self.assertEqual(snapshot(home), before)
            self.assertEqual(list(ROOT.rglob("__pycache__/*.cpython-*.pyc.preflight")), [])

    @unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "setup.sh is a POSIX shell script")
    def test_setup_sh_never_changes_an_installed_version(self):
        with fake_home() as home:
            target = install(home)
            (target / "app" / "0.0.9" / "venv" / "bin").mkdir(parents=True)
            os.symlink("0.0.9", target / "app" / "current")
            before = snapshot(home)
            run = subprocess.run(["sh", str(ROOT / "setup.sh"), "--home", str(target), "--yes"], capture_output=True,
                                 text=True, timeout=60)
            self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
            self.assertIn("composer update", run.stderr)
            self.assertEqual(snapshot(home), before)


if __name__ == "__main__":
    unittest.main()
