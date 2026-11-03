"""A refusal of an --out folder names --out, the option that was used, and the kind of folder it is.

The reported inputs:
- `composer backup --out DIR`, where DIR passes its check and is then replaced by a symbolic link before the archive is
  written: the refusal came from the app folder's check and said "Give the app folder's real path instead: --home ...
  (or COMPOSER_HOME=...; ./setup.sh takes --home too)";
- `composer serve --out DIR` under a folder other accounts can write: the refusal said "put the data folder somewhere
  else: --data ... (or COMPOSER_DATA)", but serve has no --data; its option is --out."""
import contextlib
import io
import os
import unittest
from pathlib import Path
from unittest import mock

from install_helpers import fake_home
from test_lifecycle import install

from composer import cli, home as H, lifecycle as L

POSIX = os.name == "posix" and hasattr(os, "getuid")


@unittest.skipUnless(POSIX and H.CONFINED, "owners, permission bits and folders opened without following links")
class OutMessageTests(unittest.TestCase):
    def setUp(self):
        self._home = fake_home()
        self.home = self._home.__enter__()
        self.addCleanup(self._home.__exit__, None, None, None)

    def test_backup_out_swapped_for_a_link_after_its_check_names_out(self):
        target = install(self.home)
        parent = self.home / "mine"
        parent.mkdir(mode=0o700)
        out = parent / "bk"
        out.mkdir(mode=0o700)
        elsewhere = self.home / "elsewhere"
        elsewhere.mkdir(mode=0o700)
        real_check = H.check_trust
        swapped = []

        def check_then_swap(path, what="app folder"):
            result = real_check(path, what)
            if what == "backup folder" and not swapped:  # right after --out passed its check
                os.rename(out, parent / "bk.aside")
                os.symlink(elsewhere, out)
                swapped.append(path)
            return result

        with mock.patch.object(H, "check_trust", check_then_swap):
            with self.assertRaises(L.LifecycleError) as caught:
                L.backup(target / "data", out_dir=out)
        message = str(caught.exception)
        self.assertTrue(swapped)
        self.assertEqual(os.listdir(elsewhere), [])
        self.assertIn("backup folder", message)
        self.assertIn(f"--out {os.path.realpath(out)}", message)
        self.assertNotIn("--home", message)
        self.assertNotIn("app folder", message)
        self.assertNotIn("COMPOSER_HOME", message)

    def test_backup_out_in_a_shared_folder_names_out(self):
        install(self.home)
        shared = self.home / "shared"
        shared.mkdir()
        os.chmod(shared, 0o777)
        self.addCleanup(os.chmod, shared, 0o700)
        err = io.StringIO()
        with mock.patch.dict(os.environ, {"COMPOSER_HOME": str(self.home / ".lensmith-composer")}), \
                contextlib.redirect_stderr(err):
            code = cli.main(["backup", "--out", str(shared / "bk")])
        self.assertEqual(code, 2)
        self.assertIn("--out <a folder of your own>", err.getvalue())
        self.assertNotIn("--data", err.getvalue())
        self.assertNotIn("--home", err.getvalue())

    def test_serve_out_in_a_shared_folder_names_out(self):
        shared = self.home / "shared"
        shared.mkdir()
        os.chmod(shared, 0o777)
        self.addCleanup(os.chmod, shared, 0o700)
        err = io.StringIO()
        with mock.patch("composer.server.serve", lambda *a, **k: None), contextlib.redirect_stderr(err):
            code = cli.main(["serve", "--out", str(shared / "briefs"), "--port", "0"])
        self.assertEqual(code, 2)
        self.assertEqual(os.listdir(shared), [])
        message = err.getvalue()
        self.assertIn("--out <a folder of your own>", message)
        self.assertNotIn("--data", message)
        self.assertNotIn("COMPOSER_DATA", message)
        self.assertNotIn("data folder", message)

    def test_serve_out_through_a_link_names_out_and_the_real_path(self):
        real = self.home / "real-briefs"
        real.mkdir(mode=0o700)
        link = self.home / "briefs-link"
        os.symlink(real, link)
        err = io.StringIO()
        with mock.patch("composer.server.serve", lambda *a, **k: None), contextlib.redirect_stderr(err):
            code = cli.main(["serve", "--out", str(link), "--port", "0"])
        self.assertEqual(code, 2)
        self.assertEqual(os.listdir(real), [])
        self.assertIn(f"--out {Path(os.path.realpath(real))}", err.getvalue())
        self.assertNotIn("--data", err.getvalue())


if __name__ == "__main__":
    unittest.main()
