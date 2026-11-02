"""Trust admission before anything changes (SECURITY.md): update, rollback, restore and the recovery `composer up` runs
first check, read-only, the app folder all the way down, the data folder (with every folder above it and everything in
it) and the folders an unfinished restore record names, BEFORE they take the run lock or recover anything. A refusal
changes nothing.

The reported input: another account that can write the folder above an install renames the install aside and puts a
replacement in its place, whose recovery journal holds an unfinished restore naming a protected folder elsewhere. The
update used to take the lock, run recovery (which removed that folder) and only then refuse the replacement. Recovery
also no longer acts on the journal's paths at all: it rebuilds them inside the data folder from checked names, and
refuses a record that names anything else."""
import hashlib
import json
import os
import unittest
import uuid
from pathlib import Path

from cross_account import as_other, shared_root
from install_helpers import fake_home
from test_lifecycle import FakeRun, install, release_file

from composer import home as H, installer, lifecycle as L

POSIX = os.name == "posix" and hasattr(os, "getuid")


def restore_record(data: Path, staged: Path, stage: str = "old_moved") -> str:
    return json.dumps({"operation": "restore", "stage": stage, "generation": str(data / "generations" / "g1"),
                       "replaced": str(data / "recovery" / "replaced" / "20261102T000000Z-g1"),
                       "staged": str(staged)}, sort_keys=True)


def victim(root: Path) -> Path:
    """A protected folder outside the data folder (0700) holding KEEP."""
    folder = root / "protected-victim"
    folder.mkdir(mode=0o700)
    (folder / "staged").mkdir()
    (folder / "KEEP").write_text("keep me\n", encoding="utf-8")
    return folder


class TheJournalRuleTests(unittest.TestCase):
    """_restore_paths as a pure check of a record against a data folder."""

    def test_only_the_three_places_inside_the_data_folder_pass(self):
        data = Path("/somewhere/data")
        hexid = uuid.uuid4().hex
        good = {"generation": str(data / "generations" / "g2"),
                "replaced": str(data / "recovery" / "replaced" / "20261102T101010Z-g2"),
                "staged": str(data / "tmp" / f"restore-{hexid}" / "generation")}
        self.assertEqual(L._restore_paths(data, good),
                         (data / "generations" / "g2", data / "recovery" / "replaced" / "20261102T101010Z-g2",
                          data / "tmp" / f"restore-{hexid}" / "generation"))
        bad = [("staged", "/protected-victim/staged"), ("staged", str(data / "tmp" / "restore-x" / "generation")),
               ("staged", str(data / "tmp" / f"restore-{hexid}" / "elsewhere")),
               ("staged", str(data / "tmp" / f"restore-{hexid}" / ".." / ".." / ".." / "victim" / "generation")),
               ("generation", "/etc"), ("generation", str(data / "generations" / "g3")),
               ("generation", str(data / "g1")), ("replaced", str(data / "recovery" / "replaced" / "..")),
               ("replaced", "/tmp/20261102T101010Z-g2"), ("replaced", "relative/20261102T101010Z-g2"),
               ("staged", None), ("generation", 7)]
        for key, value in bad:
            with self.subTest(key=key, value=value):
                with self.assertRaises(L.LifecycleError) as ctx:
                    L._restore_paths(data, dict(good, **{key: value}))
                self.assertIn("nothing was moved or removed", str(ctx.exception))


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self._home = fake_home()
        self.home = self._home.__enter__()
        self.addCleanup(self._home.__exit__, None, None, None)
        self.target = install(self.home)
        venv = self.target / "app" / "0.2.0" / "venv" / "bin"
        venv.mkdir(parents=True)
        (venv / "python").write_text("", encoding="utf-8")
        os.symlink("0.2.0", self.target / "app" / "current")
        self.data = self.target / "data"
        self.release = release_file(self.home.parent)
        self.sha = hashlib.sha256(self.release.read_bytes()).hexdigest()

    def journal(self, line: str) -> None:
        path = self.data / "recovery" / "journal" / "events.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def test_a_journal_that_names_a_folder_elsewhere_is_refused_before_anything_is_removed(self):
        protected = victim(self.home)
        self.journal(restore_record(self.data, protected / "staged"))
        run = FakeRun()
        calls = [lambda: L.update(self.target, self.data, self.release, sha256=self.sha, run=run, log=lambda *_: None),
                 lambda: L.rollback(self.target, self.data, log=lambda *_: None),
                 lambda: L.recover(self.target, self.data, log=lambda *_: None),
                 lambda: L.recover(None, self.data, log=lambda *_: None),
                 lambda: L.restore(self.data, self.release),
                 lambda: L._recover_restore(self.data)]
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(L.LifecycleError) as ctx:
                    call()
                self.assertIn("recovery journal", str(ctx.exception))
                self.assertTrue((protected / "KEEP").exists())
        self.assertEqual(run.calls, [])

    def test_admission_comes_before_the_lock_and_before_recovery_even_with_no_current_data(self):
        # an unfinished restore whose staged copy is in the data folder: recovery would remove it. With tmp open to
        # other accounts, nothing may run, including the early return when data/current is absent.
        hexid = uuid.uuid4().hex
        staged = self.data / "tmp" / f"restore-{hexid}" / "generation"
        staged.mkdir(parents=True)
        self.journal(restore_record(self.data, staged))
        os.unlink(self.data / "current")
        os.unlink(self.data / L.RUN_LOCK)
        os.chmod(self.target / "tmp", 0o777)
        for call in (lambda: L.recover(self.target, self.data, log=lambda *_: None),
                     lambda: L.update(self.target, self.data, self.release, sha256=self.sha, run=FakeRun(),
                                      log=lambda *_: None),
                     lambda: L.rollback(self.target, self.data, log=lambda *_: None)):
            with self.subTest(call=call):
                with self.assertRaises(L.LifecycleError) as ctx:
                    call()
                self.assertIn(str(self.target / "tmp"), str(ctx.exception))
                self.assertTrue(staged.is_dir())  # recovery did not run
                self.assertFalse((self.data / L.RUN_LOCK).exists())  # the lock was not taken

    def test_a_data_folder_open_to_others_is_refused_before_the_lock(self):
        (self.data / "recovery" / "journal" / "events.jsonl").touch()
        for rel in ("", "recovery", "recovery/journal", "recovery/journal/events.jsonl", "generations"):
            with self.subTest(rel=rel):
                path = self.data / rel if rel else self.data
                old = os.lstat(path).st_mode & 0o7777
                os.chmod(path, old | 0o022)
                try:
                    for call in (lambda: L.restore(self.data, self.release),
                                 lambda: L.rollback(None, self.data, data_only=True, log=lambda *_: None),
                                 lambda: L.recover(None, self.data, log=lambda *_: None)):
                        with self.assertRaises(L.LifecycleError) as ctx:
                            call()
                        self.assertIn(str(path), str(ctx.exception))
                finally:
                    os.chmod(path, old)

    def test_a_real_unfinished_restore_is_still_recovered(self):
        hexid = uuid.uuid4().hex
        gen = self.data / "generations" / "g1"
        replaced = self.data / "recovery" / "replaced" / "20261102T000000Z-g1"
        replaced.parent.mkdir(parents=True, exist_ok=True)
        os.replace(gen, replaced)
        staged = self.data / "tmp" / f"restore-{hexid}" / "generation"
        staged.mkdir(parents=True)
        self.journal(restore_record(self.data, staged))
        self.assertEqual(L.recover(self.target, self.data, log=lambda *_: None), "undone")
        self.assertTrue(gen.is_dir())
        self.assertFalse(staged.parent.exists())


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class AnotherAccountTests(unittest.TestCase):
    def test_a_replaced_install_cannot_make_update_remove_a_protected_folder(self):
        root = shared_root(self)
        parent = root / "parent"
        parent.mkdir(mode=0o755)
        home = parent / "install"
        with fake_home():
            installer.run(home=home, data=None, answers_file=None, assume_yes=True, reconfigure=[],
                          data_only=False, out=lambda *_: None, interactive=False)
        venv = home / "app" / "0.2.0" / "venv" / "bin"
        venv.mkdir(parents=True)
        (venv / "python").write_text("", encoding="utf-8")
        os.symlink("0.2.0", home / "app" / "current")
        os.chmod(home, 0o755)
        protected = victim(root)
        os.chmod(parent, 0o777)  # the folder above the install opened up
        record = restore_record(home / "data", protected / "staged")
        attack = as_other('mv "$1/install" "$1/install-aside" && mkdir -p "$1/install/data/recovery/journal" && '
                          'printf "%s\\n" "$2" > "$1/install/data/recovery/journal/events.jsonl"', str(parent), record)
        self.assertEqual(attack.returncode, 0, attack.stderr)
        release = release_file(root)
        run = FakeRun()
        with self.assertRaises(L.LifecycleError):
            L.update(home, home / "data", release, sha256=hashlib.sha256(release.read_bytes()).hexdigest(), run=run,
                     log=lambda *_: None)
        self.assertTrue((protected / "KEEP").exists(), "recovery removed a protected folder before the refusal")
        self.assertEqual(run.calls, [])
        self.assertFalse((home / "data" / L.RUN_LOCK).exists())  # no lock taken in the replacement either


if __name__ == "__main__":
    unittest.main()
