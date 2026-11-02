"""The trust contract all the way down (SECURITY.md): an app folder that is safe itself, with safe folders above it, is
not enough. Every folder and file Composer writes into, runs or reads as configuration inside it (tmp, cache, bin, app,
app/<version>, narration, models, data and its recovery records, the marker and the manifest) must belong to you or
root and be writable by no one else. An existing install where one of them is open to other accounts is refused with a
plain fix, never adopted; folders are checked one by one where Composer walks into them (owned_dir, Owned.child), and
the folders a started program is handed are checked again just before it starts.

The attack: an install whose own folder is 0755 but whose tmp is 0777. Another account renames the narration check
folder aside after Composer checked it and puts a link to a folder of its choosing in its place; the narration runtime,
told to write into the check folder, then writes there as you."""
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from cross_account import as_other, shared_root
from helpers import ROOT
from install_helpers import fake_home, snapshot
from test_lifecycle import FakeRun, install, release_file

from composer import home as H, lifecycle as L, narration as N

POSIX = os.name == "posix" and hasattr(os, "getuid")


def stat_of(mode: int, uid: int) -> os.stat_result:
    return os.stat_result((mode, 1, 1, 1, uid, uid, 0, 0, 0, 0))


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class TheRuleTests(unittest.TestCase):
    """The rule for one folder or file, as a pure function of its stat result."""

    def test_the_rule(self):
        me = 1000
        ok = [(stat.S_IFDIR | 0o755, me), (stat.S_IFDIR | 0o700, 0), (stat.S_IFREG | 0o644, me),
              (stat.S_IFREG | 0o600, 0), (stat.S_IFLNK | 0o777, me), (stat.S_IFREG | 0o755, me)]
        for mode, uid in ok:
            with self.subTest(mode=oct(mode), uid=uid):
                self.assertIsNone(H.trust_problem("/x", stat_of(mode, uid), me))
        bad = [(stat.S_IFDIR | 0o775, me, "can be written by other accounts"),
               (stat.S_IFDIR | 0o757, me, "can be written by other accounts"),
               (stat.S_IFREG | 0o664, me, "can be written by other accounts"),
               (stat.S_IFREG | 0o646, 0, "can be written by other accounts"),
               (stat.S_IFDIR | 0o1777, 0, "shared by every account"),
               (stat.S_IFDIR | 0o700, 65534, "belongs to another account"),
               (stat.S_IFREG | 0o600, 65534, "belongs to another account"),
               (stat.S_IFLNK | 0o777, 65534, "belongs to another account")]
        for mode, uid, word in bad:
            with self.subTest(mode=oct(mode), uid=uid):
                why = H.trust_problem("/x", stat_of(mode, uid), me)
                self.assertIsNotNone(why)
                self.assertIn(word, why)
                self.assertIn("/x", why)

    def test_composer_never_makes_group_writable_files_whatever_the_umask(self):
        from composer import cli
        old = os.umask(0o002)
        try:
            cli.no_group_write_umask()
            self.assertEqual(os.umask(0o002) & 0o022, 0o022)
            os.umask(0o007)
            cli.no_group_write_umask()
            self.assertEqual(os.umask(0o022), 0o027)  # only takes bits away
        finally:
            os.umask(old)


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class DescendantTests(unittest.TestCase):
    def setUp(self):
        self._home = fake_home()
        self.home = self._home.__enter__()
        self.addCleanup(self._home.__exit__, None, None, None)
        self.target = install(self.home)
        venv = self.target / "app" / "0.2.0" / "venv" / "bin"
        venv.mkdir(parents=True)
        (venv / "python").write_text("", encoding="utf-8")
        os.symlink("0.2.0", self.target / "app" / "current")
        (self.target / "data" / "recovery").mkdir(exist_ok=True)
        H.check_owned(self.target)  # the install as made passes

    def opened(self, rel: str, mode: int) -> Path:
        path = self.target / rel
        if not path.exists():
            path.mkdir(parents=True)
        old = stat.S_IMODE(os.lstat(path).st_mode)
        os.chmod(path, mode)
        self.addCleanup(os.chmod, path, old)
        return path

    def test_an_install_with_any_folder_open_to_others_is_refused(self):
        for rel in ("tmp", "cache", "bin", "app", "app/0.2.0", "app/0.2.0/venv/bin", "narration", "models",
                    "models/kokoro", "data", "data/recovery", "cache/pip"):
            for mode in (0o777, 0o775, 0o1777):
                with self.subTest(rel=rel, mode=oct(mode)):
                    path = self.opened(rel, mode)
                    before = snapshot(self.target)
                    with self.assertRaises(H.HomeError) as ctx:
                        H.check_owned(self.target)
                    self.assertIn(str(path), str(ctx.exception))
                    self.assertIn("chmod -R go-w", str(ctx.exception))
                    self.assertEqual(snapshot(self.target), before)
                    os.chmod(path, 0o700)

    def test_trusted_files_open_to_others_are_refused(self):
        for rel in (H.MANIFEST, H.MARKER, "bin/composer", "app/0.2.0/venv/bin/python"):
            with self.subTest(rel=rel):
                path = self.target / rel
                old = stat.S_IMODE(os.lstat(path).st_mode)
                os.chmod(path, 0o666)
                try:
                    with self.assertRaises(H.HomeError) as ctx:
                        H.check_owned(self.target)
                    self.assertIn(str(path), str(ctx.exception))
                finally:
                    os.chmod(path, old)

    def test_owned_dir_and_child_check_every_folder_on_the_way(self):
        tmp = self.opened("tmp", 0o777)
        with self.assertRaises(H.HomeError) as ctx:
            H.owned_dir(self.target, "tmp", "narration-check")
        self.assertIn(str(tmp), str(ctx.exception))
        self.assertFalse((tmp / "narration-check").exists())
        with H.open_home(self.target) as at:
            with self.assertRaises(H.HomeError):
                at.child("tmp", create=False)
        with self.assertRaises(H.HomeError):
            H.open_owned(self.target, "tmp", "narration-check")
        self.assertFalse((tmp / "narration-check").exists())
        os.chmod(tmp, 0o700)
        os.chmod(self.target, 0o777)  # the app folder itself, through its descriptor
        try:
            with self.assertRaises(H.HomeError):
                H.open_home(self.target)
        finally:
            os.chmod(self.target, 0o700)

    def test_update_rollback_narration_and_the_parser_refuse_an_open_tmp(self):
        self.opened("tmp", 0o777)
        release = release_file(self.home.parent)
        run = FakeRun()
        with self.assertRaises(L.LifecycleError) as ctx:
            L.update(self.target, self.target / "data", release,
                     sha256=hashlib.sha256(release.read_bytes()).hexdigest(), run=run, log=lambda *_: None)
        self.assertIn("tmp", str(ctx.exception))
        self.assertEqual(run.calls, [])
        self.assertFalse((self.target / "app" / "0.3.0").exists())
        with self.assertRaises(L.LifecycleError):
            L.rollback(self.target, self.target / "data", log=lambda *_: None)
        with self.assertRaises(N.NarrationError):
            N.run_worker(Path(sys.executable), {"mode": "render"}, home=self.target, timeout=5)
        with self.assertRaises(N.NarrationError):
            N.check_render(Path(sys.executable), "m", "v", home=self.target)
        self.assertFalse((self.target / "tmp" / "narration-check").exists())

    def test_a_handed_cache_folder_open_to_others_stops_a_program_before_it_starts(self):
        self.opened("cache/pip", 0o777)
        started = []
        with mock.patch.object(N.subprocess, "run", lambda *a, **k: started.append(a)):
            with self.assertRaises(N.NarrationError):
                N.run_worker(Path(sys.executable), {"mode": "render"}, home=self.target, timeout=5)
        self.assertEqual(started, [])

    @unittest.skipUnless(shutil.which("sh") and shutil.which("find"), "setup.sh is a POSIX shell script")
    def test_setup_refuses_an_existing_install_with_an_open_folder(self):
        tmp = self.opened("tmp", 0o777)
        with self.assertRaises(H.HomeError):
            H.guard(self.target)
        env = dict(os.environ, PIP_NO_INDEX="1")  # never reaches an index, whatever happens
        try:
            run = subprocess.run(["sh", str(ROOT / "setup.sh"), "--home", str(self.target), "--yes"],
                                 capture_output=True, text=True, timeout=90, env=env)
        except subprocess.TimeoutExpired:
            self.fail("setup.sh went on to install into an install with an open folder")
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn(f"{tmp} can be written by other accounts", run.stderr)
        self.assertFalse((self.target / "app" / "0.2.0" / "venv" / "pyvenv.cfg").exists())


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class AnotherAccountTests(unittest.TestCase):
    """The reported input, with the change made by a real second account (uid 65534) in a child process."""

    def test_another_account_cannot_redirect_the_narration_check_through_an_open_tmp(self):
        root = shared_root(self)
        home = root / "install"
        H.owned_dir(home, "tmp")
        os.chmod(home, 0o755)
        os.chmod(home / "tmp", 0o777)  # the install is safe; its tmp is not
        outside = root / "outside"
        outside.mkdir(mode=0o700)
        worker = root / "worker-stand-in"
        worker.write_text(f"#!{sys.executable}\n"
                          "import json, os, sys\n"
                          "req = json.load(sys.stdin)\n"
                          "with open(os.path.join(req['out_dir'], 'voice.wav'), 'wb') as f:\n"
                          "    f.write(b'RIFF')\n"
                          "print(json.dumps({'ok': True, 'rendered': [], 'missing': [], 'formats': ['wav']}))\n",
                          encoding="utf-8")
        os.chmod(worker, 0o755)
        real, attacks = N.owned_dir, []

        def checked_then_swapped(base, *parts, **kw):
            path = real(base, *parts, **kw)
            if parts == ("tmp", "narration-check"):  # after Composer's check, before the runtime writes
                attacks.append(as_other('mv "$1" "$1-aside" && ln -s "$2" "$1"', str(path), str(outside)))
            return path

        result = None
        with mock.patch.object(N, "owned_dir", checked_then_swapped):
            try:
                result = N.check_render(worker, "model", "voices", home=home)
            except N.NarrationError:
                pass
        self.assertFalse((outside / "voice.wav").exists(),
                         f"another account redirected the check audio (attacker rc {[a.returncode for a in attacks]},"
                         f" result {result})")
        self.assertIsNone(result)  # refused before anything ran


if __name__ == "__main__":
    unittest.main()
