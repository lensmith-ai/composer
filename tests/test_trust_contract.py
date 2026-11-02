"""The trust contract (SECURITY.md): Composer works only in a folder that no other account can change. The app folder
and every folder above it must belong to you or root and be writable by no one else; otherwise setup (Python and
setup.sh), update, rollback and narration refuse before they write anything, and say which folder and how to fix it."""
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT
from install_helpers import fake_home, snapshot
from test_lifecycle import install, release_file

from composer import home as H, installer, lifecycle as L, narration as N

ANSWERS = """
[provider]
kind = "none"

[narration]
enabled = false

[parser]
trafilatura = false

[schedule]
enabled = false
"""

POSIX = os.name == "posix" and hasattr(os, "getuid")


def setup(target: Path, answers: Path):
    return installer.run(home=target, data=None, answers_file=str(answers), assume_yes=True, reconfigure=[],
                         data_only=False, out=lambda *_: None, interactive=False)


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class TrustContractTests(unittest.TestCase):
    def setUp(self):
        self._home = fake_home()
        self.home = self._home.__enter__()
        self.addCleanup(self._home.__exit__, None, None, None)
        self.answers = self.home.parent / "answers.toml"
        self.answers.write_text(ANSWERS, encoding="utf-8")

    def test_setup_refuses_a_folder_others_can_write_above_it(self):
        for mode, word in ((0o775, "written by other accounts"), (0o757, "written by other accounts"),
                           (0o1777, "shared by every account")):
            with self.subTest(mode=oct(mode)):
                parent = self.home / f"open-{mode:o}"
                parent.mkdir()
                os.chmod(parent, mode)
                before = snapshot(self.home)
                with self.assertRaises(H.HomeError) as ctx:
                    setup(parent / "composer-app", self.answers)
                self.assertIn(str(parent), str(ctx.exception))
                self.assertIn(word, str(ctx.exception))
                self.assertEqual(snapshot(self.home), before)  # nothing written

    def test_setup_refuses_an_app_folder_others_can_write(self):
        target = self.home / "app-folder"
        target.mkdir()
        os.chmod(target, 0o777)
        with self.assertRaises(H.HomeError):
            setup(target, self.answers)
        self.assertEqual(os.listdir(target), [])

    def test_a_folder_owned_by_another_account_is_refused(self):
        foreign = self.home / "someone-elses"
        foreign.mkdir()
        target = foreign / ".lensmith-composer"
        if os.getuid() == 0:  # root may hand a folder to another account; root itself is always trusted
            os.chown(foreign, 65534, 65534)
            os.chmod(foreign, 0o755)
            refuse = mock.patch("os.getuid", return_value=0)
        else:  # as if this account were someone else
            refuse = mock.patch("os.getuid", return_value=os.getuid() + 4242)
        with refuse:
            with self.assertRaises(H.HomeError) as ctx:
                setup(target, self.answers)
        self.assertIn("belongs to another account", str(ctx.exception))
        self.assertFalse(target.exists())

    def test_the_system_temporary_folder_is_refused_where_it_is_shared(self):
        shared = Path("/tmp")
        if not (shared.is_dir() and shared.stat().st_mode & 0o002):
            self.skipTest("/tmp is not shared on this system")
        with self.assertRaises(H.HomeError):
            H.guard(shared / f"composer-trust-{os.getpid()}")

    def test_a_private_folder_passes(self):
        self.assertEqual(setup(self.home / ".lensmith-composer", self.answers), 0)

    def test_update_rollback_and_narration_refuse_once_a_folder_above_is_opened_up(self):
        target = install(self.home)
        (target / "app" / "0.2.0" / "venv" / "bin").mkdir(parents=True)
        (target / "app" / "0.2.0" / "venv" / "bin" / "python").write_text("", encoding="utf-8")
        os.symlink("0.2.0", target / "app" / "current")
        os.chmod(self.home, 0o777)  # the folder above the app folder can now be changed by anyone
        self.addCleanup(os.chmod, self.home, 0o700)
        release = release_file(self.home.parent)
        calls = []
        with self.assertRaises(L.LifecycleError) as ctx:
            L.update(target, target / "data", release, sha256=hashlib.sha256(release.read_bytes()).hexdigest(),
                     run=lambda argv, **kw: calls.append(argv), log=lambda *_: None)
        self.assertIn(str(self.home), str(ctx.exception))
        self.assertEqual(calls, [])
        with self.assertRaises(L.LifecycleError):
            L.rollback(target, target / "data", log=lambda *_: None)
        with self.assertRaises(N.NarrationError):
            N.download(target, log=lambda *_: None, opener=lambda *a, **k: self.fail("downloaded"))
        self.assertFalse((target / "models").exists())


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class UpdateUnderAPermissiveUmaskTests(unittest.TestCase):
    def test_the_new_version_folder_is_private_and_the_app_still_passes_its_own_check(self):
        # a umask of 002 (common with per-user groups) made app/<version> 0775 through `python -m venv`, and then the
        # trust check refused the app's own folder: composer up, rollback and doctor stopped working after an update
        from test_lifecycle import FakeRun
        with fake_home() as home:
            target = install(home)
            (target / "app" / "0.2.0" / "venv" / "bin").mkdir(parents=True)
            (target / "app" / "0.2.0" / "venv" / "bin" / "python").write_text("", encoding="utf-8")
            os.symlink("0.2.0", target / "app" / "current")
            release = release_file(home.parent)
            old = os.umask(0o002)
            try:
                L.update(target, target / "data", release, sha256=hashlib.sha256(release.read_bytes()).hexdigest(),
                         run=FakeRun(), log=lambda *_: None)
            finally:
                os.umask(old)
            self.assertEqual(os.readlink(target / "app" / "current"), "0.3.0")
            self.assertEqual((target / "app" / "0.3.0").stat().st_mode & 0o777, 0o700)
            H.check_owned(target)  # what composer up, rollback and doctor run first
            L.rollback(target, target / "data", log=lambda *_: None)


@unittest.skipUnless(POSIX and shutil.which("sh"), "setup.sh is a POSIX shell script")
class SetupShTrustTests(unittest.TestCase):
    def test_setup_sh_refuses_before_any_write(self):
        with fake_home() as home:
            for mode, word in ((0o775, "can be written by other accounts"), (0o1777, "shared by every account")):
                with self.subTest(mode=oct(mode)):
                    parent = home / f"open-{mode:o}"
                    parent.mkdir()
                    os.chmod(parent, mode)
                    run = subprocess.run(["sh", str(ROOT / "setup.sh"), "--home", str(parent / "app"), "--yes"],
                                         capture_output=True, text=True, timeout=120)
                    self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
                    self.assertIn(word, run.stderr)
                    self.assertFalse((parent / "app").exists())


if __name__ == "__main__":
    unittest.main()
