"""The trust contract and symbolic links on the way to the app folder (SECURITY.md).

Checking the folders on the path as given and on its final real path misses the folders a link leads THROUGH: with
given/first -> unsafe/second -> real, the folder `unsafe` is on neither path. If another account can write `unsafe`,
it can point `second` somewhere else after (or before) the check, and Composer writes there. So the path as given may
not go through a symbolic link at all: Composer (and setup.sh) asks for the real path instead. Writable folders on
the real path are still refused."""
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from cross_account import as_other, shared_root
from helpers import ROOT
from install_helpers import fake_home

from composer import home as H, installer

POSIX = os.name == "posix" and hasattr(os, "getuid")


def chain(root: Path) -> tuple[Path, Path, Path]:
    """root/given/first -> root/unsafe/second -> root/real (unsafe is 0777); returns (home, unsafe, real)."""
    (root / "given").mkdir()
    (root / "unsafe").mkdir()
    (root / "real").mkdir()
    os.chmod(root / "given", 0o755)
    os.chmod(root / "real", 0o755)
    os.chmod(root / "unsafe", 0o777)
    os.symlink(root / "real", root / "unsafe" / "second")
    os.symlink(root / "unsafe" / "second", root / "given" / "first")
    return root / "given" / "first" / "install", root / "unsafe", root / "real"


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class SymlinkHopTests(unittest.TestCase):
    def setUp(self):
        self._home = fake_home()
        self.home = self._home.__enter__()
        self.addCleanup(self._home.__exit__, None, None, None)

    def test_a_link_on_the_way_is_refused_and_the_real_path_is_named(self):
        home, unsafe, real = chain(self.home)
        H.owned_dir(real / "install", "bin")
        for check in (H.check_trust, H.check_owned, H.guard, lambda p: H.owned_dir(p, "bin"), H.open_home):
            with self.subTest(check=getattr(check, "__name__", "owned_dir")):
                with self.assertRaises(H.HomeError) as ctx:
                    check(home)
                self.assertIn(f"{self.home / 'given' / 'first'} is a symbolic link", str(ctx.exception))
                self.assertIn(str(real / "install"), str(ctx.exception))  # the real path to give instead
        with self.assertRaises(H.HomeError):
            installer.write_launcher(home)
        self.assertFalse((real / "install" / "bin" / "composer").exists())

    def test_a_safe_link_is_refused_too_and_a_real_path_passes(self):
        real = self.home / "real-place"
        H.owned_dir(real / "install", "bin")
        os.symlink(real, self.home / "nice-link")
        with self.assertRaises(H.HomeError):
            H.check_trust(self.home / "nice-link" / "install")
        with self.assertRaises(H.HomeError):  # a path that does not exist yet, under a link
            H.check_trust(self.home / "nice-link" / "new" / "deeper")
        H.check_trust(real / "install")
        H.check_owned(real / "install")

    def test_writable_folders_on_the_real_path_are_still_refused(self):
        real = self.home / "open"
        real.mkdir()
        os.chmod(real, 0o777)
        with self.assertRaises(H.HomeError) as ctx:
            H.check_trust(real / "install")
        self.assertIn("can be written by other accounts", str(ctx.exception))

    @unittest.skipUnless(shutil.which("sh"), "setup.sh is a POSIX shell script")
    def test_setup_sh_refuses_a_link_on_the_way_before_any_write(self):
        home, _, real = chain(self.home)
        run = subprocess.run(["sh", str(ROOT / "setup.sh"), "--home", str(home), "--yes"], capture_output=True,
                             text=True, timeout=120)
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn(f"{self.home / 'given' / 'first'} is a symbolic link; give the real path instead", run.stderr)
        self.assertIn(str(real / "install"), run.stderr)
        self.assertEqual(os.listdir(real), [])


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class AnotherAccountTests(unittest.TestCase):
    def test_another_account_cannot_redirect_the_launcher_through_a_hidden_hop(self):
        root = shared_root(self)
        home, unsafe, real = chain(root)
        H.owned_dir(real / "install", "bin")
        os.chmod(real / "install", 0o755)
        outside = root / "outside"
        H.owned_dir(outside / "install", "bin")
        os.chmod(outside, 0o755)
        os.chmod(outside / "install", 0o755)
        # the second account repoints the hop in the folder only it (and everyone) can write
        attack = as_other('rm "$1" && ln -s "$2" "$1"', str(unsafe / "second"), str(outside))
        self.assertEqual(attack.returncode, 0, attack.stderr)
        try:
            installer.write_launcher(home)
        except H.HomeError:
            pass
        self.assertFalse((outside / "install" / "bin" / "composer").exists(),
                         "the launcher was written where another account pointed the path")


if __name__ == "__main__":
    unittest.main()
