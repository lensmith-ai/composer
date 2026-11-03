"""`composer setup --data` and the trust contract (SECURITY.md): the data folder is checked like the app folder.

The reported input: another account that can write the folder above --data plants a symbolic link at the name you
give (shared/cdata -> a private folder of yours). setup used to resolve --data (following the link) before any check,
never checked the data folder at all, made its data tree in the folder the link named and chmodded that folder.
Now --data is taken as written (never resolved), the data folder, every folder above it and everything in it are
checked before anything is written (and again at the write), and its mode is set through the folder as opened, so a
link in its place is refused instead of followed."""
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

from composer import cli, home as H, installer, settings as S

POSIX = os.name == "posix" and hasattr(os, "getuid")


def setup(home: Path, data: Path | None, *, data_only: bool = False) -> int:
    return installer.run(home=home, data=data, answers_file=None, assume_yes=True, reconfigure=[],
                         data_only=data_only, out=lambda *_: None, interactive=False)


class GivenPathTests(unittest.TestCase):
    def test_setup_takes_data_as_written_and_never_resolves_it(self):
        with fake_home() as home:
            real = home / "real"
            real.mkdir()
            os.symlink(real, home / "link")
            seen = {}

            def fake_run(**kwargs):
                seen.update(kwargs)
                return 0

            with mock.patch.object(installer, "run", fake_run):
                cli.main(["setup", "--home", str(home / "inst"), "--data", str(home / "link" / "x" / ".." / "cdata"),
                          "--yes", "--no-test-call"])
            self.assertEqual(seen["data"], home / "link" / "cdata")  # normalised as written, the link still on it
            cwd = os.getcwd()
            try:
                os.chdir(home)
                self.assertEqual(H.given_path("rel/./d"), home / "rel" / "d")
            finally:
                os.chdir(cwd)


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class SetupDataTests(unittest.TestCase):
    def setUp(self):
        self._home = fake_home()
        self.home = self._home.__enter__()
        self.addCleanup(self._home.__exit__, None, None, None)

    def test_a_data_folder_under_a_folder_others_can_write_is_refused_before_any_write(self):
        shared = self.home / "shared"
        shared.mkdir()
        os.chmod(shared, 0o777)
        for data_only in (False, True):
            with self.subTest(data_only=data_only):
                with self.assertRaises(installer.SetupError) as ctx:
                    setup(self.home / "inst", shared / "cdata", data_only=data_only)
                self.assertIn(f"{shared} can be written by other accounts", str(ctx.exception))
                self.assertEqual(os.listdir(shared), [])
                self.assertFalse((self.home / "inst").exists())

    def test_a_link_on_the_way_to_the_data_folder_is_refused_and_its_target_is_untouched(self):
        target = self.home / "private"
        target.mkdir(mode=0o750)
        os.chmod(target, 0o750)
        os.symlink(target, self.home / "via")
        for data in (self.home / "via", self.home / "via" / "cdata"):
            for data_only in (False, True):
                with self.subTest(data=data, data_only=data_only):
                    with self.assertRaises(installer.SetupError) as ctx:
                        setup(self.home / "inst", data, data_only=data_only)
                    self.assertIn(f"{self.home / 'via'} is a symbolic link", str(ctx.exception))
                    self.assertEqual(os.listdir(target), [])
                    self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o750)  # not chmodded through the link

    def test_an_existing_data_folder_with_something_open_to_others_is_refused(self):
        data = self.home / "mydata"
        setup(self.home / "inst", data)
        loose = data / "generations" / "g1" / "config.json"
        os.chmod(loose, 0o666)
        with self.assertRaises(installer.SetupError) as ctx:
            installer.run(home=self.home / "inst", data=data, answers_file=None, assume_yes=True,
                          reconfigure=["port"], data_only=False, out=lambda *_: None, interactive=False)
        self.assertIn(str(loose), str(ctx.exception))
        self.assertIn(f"chmod -R go-w {data}", str(ctx.exception))

    def test_a_folder_shared_by_every_account_is_refused(self):
        tmp = Path("/tmp")
        st = os.stat(tmp)
        if not (st.st_mode & stat.S_ISVTX and st.st_mode & stat.S_IWOTH):
            self.skipTest("/tmp is not a sticky folder every account can write here")
        data = tmp / ("composer-r5-" + os.urandom(6).hex())
        with self.assertRaises(installer.SetupError):
            setup(self.home / "inst", data)
        self.assertFalse(os.path.lexists(data))

    def test_a_good_data_folder_outside_still_works_and_is_private(self):
        data = self.home / "outside" / "cdata"
        self.assertEqual(setup(self.home / "inst", data), 0)
        self.assertEqual(stat.S_IMODE(os.stat(data).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.stat(self.home / "outside").st_mode), 0o700)
        self.assertEqual(H.load_manifest(self.home / "inst")["data_path"], str(data))

    def test_the_data_folder_mode_is_never_set_through_a_link(self):
        target = self.home / "elsewhere"
        target.mkdir(mode=0o755)
        os.chmod(target, 0o755)
        os.symlink(target, self.home / "data-link")
        for call in (lambda: H.private_folder(self.home / "data-link"),
                     lambda: S.write_secret(self.home / "data-link", "ANTHROPIC_API_KEY", "fake-key-for-test"),
                     lambda: S.generation_dir(self.home / "data-link")):
            with self.subTest(call=call):
                with self.assertRaises(H.HomeError):
                    call()
                self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o755)
                self.assertEqual(os.listdir(target), [])


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class AnotherAccountTests(unittest.TestCase):
    def test_another_account_cannot_choose_where_setup_writes_its_data(self):
        root = shared_root(self)
        safe = root / "safe"
        safe.mkdir(mode=0o755)
        os.chmod(safe, 0o755)
        shared = root / "shared"
        shared.mkdir()
        os.chmod(shared, 0o777)
        victim = root / "victim-private"
        victim.mkdir(mode=0o700)
        os.chmod(victim, 0o700)
        attack = as_other('ln -s "$2" "$1"', str(shared / "cdata"), str(victim / "planted-data"))
        self.assertEqual(attack.returncode, 0, attack.stderr)
        env = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSER_")}
        env.update(COMPOSER_NO_TEST_CALL="1", HOME=str(root / "nohome"))
        run = subprocess.run([sys.executable, "-m", "composer", "setup", "--home", str(safe / "inst"), "--data",
                              str(shared / "cdata"), "--yes", "--no-test-call"], cwd=str(ROOT), env=env,
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn("is a symbolic link", run.stderr)
        self.assertEqual(os.listdir(victim), [], "setup wrote into the folder another account chose")
        self.assertEqual(stat.S_IMODE(os.stat(victim).st_mode), 0o700)

    def test_another_account_cannot_plant_inside_a_data_folder_setup_admitted(self):
        root = shared_root(self)
        data = root / "cdata"
        with fake_home() as home:
            setup(home / "inst", data)
        attack = as_other('mkdir "$1/evil" || ln -s / "$1/evil"', str(data))
        self.assertNotEqual(attack.returncode, 0)
        self.assertFalse(os.path.lexists(data / "evil"))


if __name__ == "__main__":
    unittest.main()
