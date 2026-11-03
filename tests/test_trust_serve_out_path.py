"""`composer serve --out` writes to exactly the folder it checked.

The reported input: `--out safe/hop/../sout`, where hop is a link you made into a folder inside a folder other
accounts can write, and another account has put its own sout beside hop's target. Serve admitted the path as written
and normalised (safe/sout), but handed the job store the path as typed, which the kernel resolves through the link
(shared/sout): the first folders were made in safe/sout and the first file write went to shared/sout. Now the path is
normalised once and that same path is admitted and written to."""
import os
import unittest
from pathlib import Path
from unittest import mock

from cross_account import as_other, shared_root
from install_helpers import fake_home

from composer import cli, server

POSIX = os.name == "posix" and hasattr(os, "getuid")


def files_under(root: Path) -> list:
    return sorted(str(Path(d, f).relative_to(root)) for d, _, names in os.walk(root) for f in names)


def serve(out: str) -> tuple[int, list]:
    started = []
    with mock.patch.object(server, "serve", lambda app, *a, **k: started.append(app)):
        code = cli.main(["serve", "--out", out, "--port", "0"])
    return code, started


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class SameAccountTests(unittest.TestCase):
    def setUp(self):
        self._home = fake_home()
        self.home = self._home.__enter__()
        self.addCleanup(self._home.__exit__, None, None, None)

    def test_serve_writes_where_it_checked_not_through_a_link_and_dot_dot(self):
        safe = self.home / "safe"
        safe.mkdir(mode=0o700)
        shared = self.home / "shared"
        shared.mkdir()
        os.chmod(shared, 0o777)
        self.addCleanup(os.chmod, shared, 0o700)
        (shared / "sub").mkdir(mode=0o700)
        planted = shared / "sout"  # what another account could put beside the link's target
        (planted / "generations" / "g1").mkdir(parents=True)
        os.symlink(shared / "sub", safe / "hop")
        code, started = serve(str(safe / "hop" / ".." / "sout"))
        self.assertEqual(code, 0)
        self.assertEqual(files_under(planted), [], "serve wrote outside the folder it checked")
        self.assertEqual(len(started), 1)
        self.assertEqual(started[0].jobs.root, safe / "sout")
        self.assertEqual(started[0].out_dir, safe / "sout")
        self.assertTrue((safe / "sout" / "current").is_file())
        self.assertTrue((safe / "sout" / "generations" / "g1" / "VERSION").is_file())

    def test_a_relative_out_is_made_absolute_once(self):
        safe = self.home / "safe"
        safe.mkdir(mode=0o700)
        cwd = os.getcwd()
        os.chdir(safe)
        self.addCleanup(os.chdir, cwd)
        code, started = serve("briefs")
        self.assertEqual(code, 0)
        self.assertEqual(started[0].jobs.root, safe / "briefs")
        self.assertTrue((safe / "briefs" / "current").is_file())


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class AnotherAccountTests(unittest.TestCase):
    def test_a_planted_link_beside_the_hop_target_gets_no_write(self):
        root = shared_root(self)
        safe = root / "safe"
        safe.mkdir(mode=0o755)
        os.chmod(safe, 0o755)
        shared = root / "shared"
        shared.mkdir()
        os.chmod(shared, 0o777)
        (shared / "sub").mkdir(mode=0o755)
        os.chmod(shared / "sub", 0o755)
        victim = root / "victim"
        victim.mkdir(mode=0o755)
        os.chmod(victim, 0o755)
        (victim / "KEEP").write_text("keep\n", encoding="utf-8")
        os.symlink(shared / "sub", safe / "hop")  # a link the user made
        attack = as_other('ln -s "$2" "$1"', str(shared / "sout"), str(victim))
        self.assertEqual(attack.returncode, 0, attack.stderr)
        with fake_home():
            code, started = serve(str(safe / "hop" / ".." / "sout"))
        self.assertEqual(os.listdir(victim), ["KEEP"], "serve wrote into a folder another account chose")
        self.assertEqual(code, 0)
        self.assertEqual(started[0].jobs.root, safe / "sout")
        self.assertTrue((safe / "sout" / "generations" / "g1" / "VERSION").is_file())


if __name__ == "__main__":
    unittest.main()
