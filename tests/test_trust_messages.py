"""The trust contract's refusals say what to do (SECURITY.md), in the setups where they are most likely.

The reported cases, each refused correctly but with advice that did not help:
- a home folder reached through a symbolic link (Fedora Silverblue and Kinoite: /home -> var/home; FreeBSD: /home ->
  usr/home): the default install refused "/home is a symbolic link" and named the real path, but not how to pass
  it, and suggested the default folder, the path that had just failed;
- a data folder on a disk with no POSIX permission bits (FAT, exFAT, NTFS mounted with umask=000): the advice was
  `chmod go-w`, which has no effect there, and it called the data folder the app folder;
- under a umask of 002, the `chmod -R go-w` advice for a whole folder is right and stays."""
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT
from install_helpers import fake_home
from test_lifecycle import install

from composer import home as H, lifecycle as L

POSIX = os.name == "posix" and hasattr(os, "getuid")
MOUNTINFO = ("22 1 8:1 / / rw,relatime shared:1 - ext4 /dev/sda1 rw\n"
             "36 22 98:0 / /media/usb\\040disk rw,noatime shared:2 - vfat /dev/sdb1 rw,uid=1000,umask=000\n"
             "37 22 98:1 / /media/usb rw,noatime shared:3 - exfat /dev/sdc1 rw\n")


def dir_stat(mode: int, uid: int):
    return os.stat_result((stat.S_IFDIR | mode, 0, 0, 2, uid, 0, 0, 0, 0, 0))


class AdviceRuleTests(unittest.TestCase):
    """The advice as a pure function of the folder's stat result and the mount table."""

    def test_the_mount_table_names_the_filesystem_of_the_longest_mount_point(self):
        self.assertEqual(H.filesystem_type("/media/usb disk/cdata", MOUNTINFO), "vfat")
        self.assertEqual(H.filesystem_type("/media/usb/cdata", MOUNTINFO), "exfat")
        self.assertEqual(H.filesystem_type("/media/usbstick/cdata", MOUNTINFO), "ext4")
        self.assertIsNone(H.filesystem_type("/x", ""))

    def test_a_disk_without_permission_bits_gets_advice_that_can_work(self):
        st = dir_stat(0o777, 1000)
        with mock.patch.object(H, "filesystem_type", lambda path: "vfat"):
            why = H.trust_problem(Path("/media/usb/cdata"), st, 1000, "data folder")
        self.assertIn("vfat filesystem", why)
        self.assertIn("chmod has no effect", why)
        self.assertIn("dmask=077,fmask=177", why)
        self.assertIn("data folder", why)
        self.assertIn("--data", why)
        self.assertNotIn("app folder", why)
        self.assertNotIn("chmod go-w", why)

    def test_a_posix_disk_keeps_the_chmod_advice_and_names_the_folder(self):
        st = dir_stat(0o775, 1000)
        with mock.patch.object(H, "filesystem_type", lambda path: "ext4"):
            for what, flag in (("app folder", "--home"), ("data folder", "--data")):
                with self.subTest(what=what):
                    why = H.trust_problem(Path("/somewhere/x"), st, 1000, what)
                    self.assertIn("Fix: chmod go-w /somewhere/x", why)
                    self.assertIn(f"put the {what} somewhere else: {flag}", why)
                    self.assertNotIn("the default is", why)  # the default may be the path that just failed
        why = H.trust_problem(Path("/somewhere/x"), dir_stat(0o755, 4242), 1000, "data folder")
        self.assertIn("belongs to another account (uid 4242)", why)
        self.assertIn("--data", why)


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class LinkedHomeTests(unittest.TestCase):
    """A home folder reached through a link, like /home -> var/home, in a private copy of that layout."""

    def setUp(self):
        self._home = fake_home()
        self.base = self._home.__enter__().parent / "sys"
        self.addCleanup(self._home.__exit__, None, None, None)
        (self.base / "var" / "home" / "u").mkdir(parents=True)
        for folder in (self.base, self.base / "var", self.base / "var" / "home"):
            os.chmod(folder, 0o755)
        os.chmod(self.base / "var" / "home" / "u", 0o700)
        os.symlink("var/home", self.base / "home")
        self.user_home = self.base / "home" / "u"
        self.real = self.base / "var" / "home" / "u" / ".lensmith-composer"

    def test_the_refusal_says_how_to_pass_the_real_path(self):
        target = self.user_home / ".lensmith-composer"
        with self.assertRaises(H.HomeError) as ctx:
            H.check_trust(target)
        text = str(ctx.exception)
        self.assertIn(f"{self.base / 'home'} is a symbolic link (to var/home)", text)
        self.assertIn(f"--home {self.real}", text)
        self.assertIn(f"COMPOSER_HOME={self.real}", text)
        with self.assertRaises(H.HomeError) as ctx:
            H.check_trust(self.user_home / "data", "data folder")
        self.assertIn(f"--data {self.base / 'var' / 'home' / 'u' / 'data'}", str(ctx.exception))

    def test_default_setup_and_setup_sh_name_the_option_to_use(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSER_")}
        env.update(HOME=str(self.user_home), COMPOSER_NO_TEST_CALL="1")
        run = subprocess.run([sys.executable, "-m", "composer", "setup", "--yes", "--no-test-call"], cwd=str(ROOT),
                             env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn(f"--home {self.real}", run.stderr)
        if shutil.which("sh"):
            run = subprocess.run(["sh", str(ROOT / "setup.sh"), "--yes"], env=env, capture_output=True, text=True,
                                 timeout=120)
            self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
            self.assertIn(f"./setup.sh --home {self.real}", run.stderr)
        self.assertEqual(os.listdir(self.base / "var" / "home" / "u"), [])


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class FolderNameTests(unittest.TestCase):
    def test_a_data_folder_refusal_says_data_folder_and_keeps_the_umask_fix(self):
        with fake_home() as home:
            target = install(home)
            data = target / "data"
            loose = data / "generations" / "g1" / "config.json"
            os.chmod(loose, 0o664)
            with self.assertRaises(L.LifecycleError) as ctx:
                L.admit(None, data)
            text = str(ctx.exception)
            self.assertIn("put the data folder somewhere else: --data", text)
            self.assertIn("Every folder and file in the data folder", text)
            self.assertIn(f"To fix a data folder made under a permissive umask: chmod -R go-w {data}", text)
            self.assertNotIn("app folder", text)
            os.chmod(loose, 0o600)
            os.chmod(target / "cache", 0o775)
            with self.assertRaises(H.HomeError) as ctx:
                H.check_owned(target)
            self.assertIn(f"To fix a whole install made under a permissive umask: chmod -R go-w {target}",
                          str(ctx.exception))
            self.assertIn("app folder", str(ctx.exception))


@unittest.skipUnless(POSIX and os.geteuid() == 0 and shutil.which("mkfs.vfat") and shutil.which("unshare"),
                     "a real FAT disk needs root, mkfs.vfat and unshare (a private mount namespace)")
class RealFatDiskTests(unittest.TestCase):
    def test_a_data_folder_on_a_fat_disk_is_refused_with_advice_that_can_work(self):
        work = Path(tempfile.mkdtemp(prefix="composer-fat-"))
        self.addCleanup(shutil.rmtree, work, True)
        image, mount = work / "fat.img", work / "mnt"
        mount.mkdir()
        with open(image, "wb") as handle:
            handle.truncate(4 * 1024 * 1024)
        made = subprocess.run(["mkfs.vfat", str(image)], capture_output=True, text=True)
        if made.returncode != 0:
            self.skipTest("mkfs.vfat failed: " + made.stderr[-200:])
        check = ("import sys; sys.path.insert(0, sys.argv[2]); from composer import lifecycle as L; "
                 "import os; d = os.path.join(sys.argv[1], 'cdata'); os.mkdir(d)\n"
                 "try:\n L.admit(None, d)\nexcept L.LifecycleError as e:\n print(e)")
        script = (f'mount -o loop,uid=0,umask=000 "$1" "$2" || exit 77; '
                  f'"$3" -I -c "$4" "$2" "$5"; status=$?; umount "$2"; exit $status')
        run = subprocess.run(["unshare", "-m", "--propagation", "private", "sh", "-c", script, "fat", str(image),
                              str(mount), sys.executable, check, str(ROOT)], capture_output=True, text=True,
                             timeout=120)
        if run.returncode == 77:
            self.skipTest("cannot mount a loop device here: " + run.stderr[-200:])
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("vfat filesystem", run.stdout)
        self.assertIn("chmod has no effect", run.stdout)
        self.assertIn("data folder", run.stdout)
        self.assertNotIn("app folder", run.stdout)


if __name__ == "__main__":
    unittest.main()
