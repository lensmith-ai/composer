"""Uninstall, backup, doctor and `composer serve` under the trust contract (SECURITY.md): admitted, read-only, before
they take the run lock or write or remove anything; then they act inside the folders as opened.

The reported inputs (the folder above an install opened to another account after setup, as in the update finding):
- uninstall: right after the manifest check, the other account swaps the install for a link to a private folder of
  yours; uninstall then removed bin, cache and tmp there and wrote a manifest into it;
- uninstall: the other account replaces the install with its own folder whose data/up.lock is a link to a new file
  elsewhere; taking the run lock created that file (as you);
- `composer backup`: the other account replaces the install with its own folder whose data/backups is a link to a
  private folder of yours; the archive was written there.
Now each is refused at admission, the run lock is opened inside the data folder as opened and never through a link,
uninstall removes by name inside the app folder it opened, and backup writes inside the backups folder it opened."""
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from cross_account import as_other, shared_root
from helpers import ROOT
from install_helpers import fake_home
from test_lifecycle import install

from composer import cli, doctor, home as H, installer, lifecycle as L

POSIX = os.name == "posix" and hasattr(os, "getuid")


def setup_in(parent: Path) -> Path:
    home = parent / "inst"
    with fake_home():
        installer.run(home=home, data=None, answers_file=None, assume_yes=True, reconfigure=[], data_only=False,
                      out=lambda *_: None, interactive=False)
    return home


def private_home_like(where: Path) -> Path:
    """A private folder of yours holding bin, app, cache and tmp, each with a KEEP file."""
    folder = where / "victim-home"
    folder.mkdir(mode=0o700)
    for name in ("bin", "app", "cache", "tmp"):
        (folder / name).mkdir()
        (folder / name / "KEEP").write_text("keep\n", encoding="utf-8")
    return folder


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class SameAccountTests(unittest.TestCase):
    def setUp(self):
        self._home = fake_home()
        self.home = self._home.__enter__()
        self.addCleanup(self._home.__exit__, None, None, None)

    def opened_parent(self) -> tuple[Path, Path]:
        parent = self.home / "parent"
        parent.mkdir()
        target = install(parent)
        os.chmod(parent, 0o777)
        self.addCleanup(os.chmod, parent, 0o755)
        return parent, target

    def test_uninstall_and_backup_are_admitted_before_the_lock_or_any_write(self):
        parent, target = self.opened_parent()
        os.unlink(target / "data" / L.RUN_LOCK)
        for call in (lambda: L.uninstall(target, target / "data"),
                     lambda: L.uninstall(target, target / "data", delete_data=True, confirm=lambda q: True),
                     lambda: L.backup(target / "data")):
            with self.subTest(call=call):
                with self.assertRaises(L.LifecycleError) as ctx:
                    call()
                self.assertIn(f"{parent} can be written by other accounts", str(ctx.exception))
                self.assertTrue((target / "bin").is_dir())
                self.assertFalse((target / "data" / L.RUN_LOCK).exists())  # no lock taken
                self.assertFalse((target / "data" / "backups").exists())

    def test_the_run_lock_is_never_opened_through_a_link(self):
        target = install(self.home)
        outside = self.home / "outside"
        outside.mkdir()
        os.unlink(target / "data" / L.RUN_LOCK)
        os.symlink(outside / "CREATED-BY-COMPOSER", target / "data" / L.RUN_LOCK)
        for call in (lambda: L.uninstall(target, target / "data"), lambda: L.hold_run_lock(target / "data"),
                     lambda: L.app_running(target / "data")):
            with self.subTest(call=call):
                with self.assertRaises(L.LifecycleError) as ctx:
                    call()
                self.assertIn("run lock", str(ctx.exception))
                self.assertEqual(os.listdir(outside), [])
        self.assertTrue((target / "bin").is_dir())

    def test_uninstall_removes_inside_the_app_folder_it_opened(self):
        # the same swap the other account made, done here by this account (the race needs a writable parent, which
        # admission refuses): removals go through the folder opened at the start, so a swap after it changes nothing
        parent = self.home / "parent"
        parent.mkdir()
        target = install(parent)
        victim = private_home_like(self.home)
        real_check = H.check_manifest

        def swapped(home, doc, data):
            problems = real_check(home, doc, data)
            if not os.path.islink(target):
                os.rename(target, parent / "inst-aside")
                os.symlink(victim, target)
            return problems

        with mock.patch.object(H, "check_manifest", swapped):
            try:
                L.uninstall(target, target / "data")
            except (L.LifecycleError, H.HomeError):
                pass
        for name in ("bin", "app", "cache", "tmp"):
            self.assertTrue((victim / name / "KEEP").is_file(), f"uninstall removed {name} in another folder")
        self.assertFalse((victim / H.MANIFEST).exists(), "uninstall wrote a manifest into another folder")
        aside = parent / "inst-aside"
        self.assertFalse((aside / "bin").exists())  # the install it opened was the one uninstalled
        self.assertTrue((aside / "data" / "current").is_file())

    def test_backup_never_writes_through_a_linked_backups_folder(self):
        target = install(self.home)
        elsewhere = self.home / "elsewhere"
        elsewhere.mkdir(mode=0o700)
        os.symlink(elsewhere, target / "data" / "backups")
        with self.assertRaises(L.LifecycleError) as ctx:
            L.backup(target / "data")
        self.assertIn("backups", str(ctx.exception))
        self.assertEqual(os.listdir(elsewhere), [])

    def test_backup_out_must_be_a_folder_no_other_account_can_change(self):
        target = install(self.home)
        shared = self.home / "shared"
        shared.mkdir()
        os.chmod(shared, 0o777)
        with self.assertRaises(L.LifecycleError) as ctx:
            L.backup(target / "data", out_dir=shared)
        self.assertIn("Pick a folder of your own for --out", str(ctx.exception))
        self.assertEqual(os.listdir(shared), [])
        mine = self.home / "mine" / "backups"
        archive = L.backup(target / "data", out_dir=mine)
        self.assertEqual(archive.parent, mine)
        self.assertEqual(stat.S_IMODE(os.stat(mine).st_mode), 0o700)
        L.read_backup(archive)

    def test_doctor_reports_the_trust_check_and_then_writes_and_starts_nothing(self):
        target = install(self.home)
        os.chmod(target / "tmp", 0o777)
        self.addCleanup(os.chmod, target / "tmp", 0o700)
        rows = []
        with mock.patch.object(doctor.tempfile, "mkdtemp", side_effect=AssertionError("doctor wrote")):
            code = doctor.run(target, target / "data", parity=True, out=rows.append, integrity_only=True)
        self.assertEqual(code, 1)
        trust = [r for r in rows if r.startswith("FAIL trust:")]
        self.assertTrue(trust and str(target / "tmp") in trust[0], rows)
        self.assertTrue(any(r.startswith("SKIP parity:") for r in rows), rows)

    def test_serve_admits_its_data_folder_before_the_store_writes(self):
        shared = self.home / "shared"
        shared.mkdir()
        os.chmod(shared, 0o777)
        with mock.patch("composer.server.serve", lambda *a, **k: None):
            code = cli.main(["serve", "--out", str(shared / "briefs")])
        self.assertEqual(code, 2)
        self.assertEqual(os.listdir(shared), [])


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class AnotherAccountTests(unittest.TestCase):
    def setUp(self):
        self.root = shared_root(self)
        self.parent = self.root / "parent"
        self.parent.mkdir(mode=0o755)
        os.chmod(self.parent, 0o755)
        self.home = setup_in(self.parent)
        os.chmod(self.home, 0o755)
        os.chmod(self.parent, 0o777)  # the folder above the install opened up after setup

    def test_a_swap_after_the_manifest_check_cannot_make_uninstall_remove_elsewhere(self):
        victim = private_home_like(self.root)
        real_check = H.check_manifest
        attacks = []

        def hooked(home, doc, data):
            problems = real_check(home, doc, data)
            if not attacks:
                attacks.append(as_other('mv "$1" "$1.aside" && ln -s "$2" "$1"', str(self.home), str(victim)))
            return problems

        with mock.patch.object(H, "check_manifest", hooked):
            with self.assertRaises(L.LifecycleError):
                L.uninstall(self.home, self.home / "data")
        self.assertEqual(sorted(os.listdir(victim)), ["app", "bin", "cache", "tmp"])
        for name in ("bin", "app", "cache", "tmp"):
            self.assertTrue((victim / name / "KEEP").is_file())

    def test_a_replaced_install_cannot_make_uninstall_create_a_file_elsewhere(self):
        victim = self.root / "victim2"
        victim.mkdir(mode=0o700)
        attack = as_other('set -e; mv "$1" "$1.aside"; mkdir -p "$1/data"; echo g1 > "$1/data/current"; '
                          'ln -s "$2/CREATED-BY-COMPOSER" "$1/data/up.lock"', str(self.home), str(victim))
        self.assertEqual(attack.returncode, 0, attack.stderr)
        with self.assertRaises((L.LifecycleError, H.HomeError)):
            L.uninstall(self.home, self.home / "data")
        self.assertEqual(os.listdir(victim), [])

    def test_a_replaced_install_cannot_make_backup_write_elsewhere(self):
        victim = self.root / "victim3"
        victim.mkdir(mode=0o700)
        gen = sorted((self.home / "data" / "generations").iterdir())[0].name
        attack = as_other(
            'set -e; mv "$1" "$1.aside"; mkdir -p "$1/data/generations/$3"; echo "$3" > "$1/data/current"; '
            'echo 1 > "$1/data/generations/$3/VERSION"; ln -s "$2" "$1/data/backups"', str(self.home), str(victim), gen)
        self.assertEqual(attack.returncode, 0, attack.stderr)
        env = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSER_")}
        env.update(COMPOSER_HOME=str(self.home), HOME=str(self.root / "nohome"))
        run = subprocess.run([sys.executable, "-m", "composer", "backup"], cwd=str(ROOT), env=env,
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn("belongs to another account (uid 65534)", run.stderr)
        self.assertEqual(os.listdir(victim), [], "the backup was written into a folder another account chose")


if __name__ == "__main__":
    unittest.main()
