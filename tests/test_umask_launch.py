"""Nothing Composer starts may leave a group-writable file in its folder, whatever the umask it is started with (002 is
common): the trust contract refuses an app folder with one (home.check_owned), so a launcher that let Python write its
bytecode folders as 0775 made the next `composer up` refuse its own install. The launcher (bin/composer) and setup.sh
take the group and other write bits away before they run any program."""
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from helpers import ROOT
from install_helpers import fake_home
from test_lifecycle import install

from composer import __version__, home as H, installer

POSIX = os.name == "posix" and hasattr(os, "getuid")


@unittest.skipUnless(POSIX and shutil.which("sh"), "a POSIX shell launcher")
class LauncherUmaskTests(unittest.TestCase):
    def test_every_launcher_takes_the_write_bits_away_before_it_starts_anything(self):
        with fake_home() as home:
            for target in (installer.APP_LAUNCH.replace("__APP__", str(home / "app")), "exec python3 -m composer"):
                text = installer._launcher_text(home / ".lensmith-composer", target)
                lines = text.splitlines()
                self.assertIn(installer.UMASK_LINE, lines)
                first_run = next(i for i, ln in enumerate(lines)
                                 if not ln.startswith("#") and ("exec " in ln or "starts " in ln))
                self.assertLess(lines.index(installer.UMASK_LINE), first_run)
        for umask in ("002", "000", "077", "027"):
            out = subprocess.run(["sh", "-c", f"umask {umask}; {installer.UMASK_LINE}; umask"], capture_output=True,
                                 text=True, check=True).stdout.strip()
            self.assertEqual(int(out, 8), int(umask, 8) | 0o022, umask)

    def test_python_started_by_the_launcher_under_umask_002_leaves_the_folder_acceptable(self):
        with fake_home() as home:
            target = install(home)
            launcher = target / "bin" / "composer"
            env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
            run = subprocess.run(["sh", "-c", 'umask 002; exec "$0" --version', str(launcher)], cwd=ROOT, env=env,
                                 capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            made = [p for p in (target / "cache" / "pycache").rglob("*") if p.is_dir()]
            self.assertTrue(made, "the launched Python wrote no bytecode folders; the test proves nothing")
            H.check_owned(target)  # what `composer up` runs first


@unittest.skipUnless(POSIX and shutil.which("sh") and shutil.which("find"), "setup.sh is a POSIX shell script")
class SetupShUmaskTests(unittest.TestCase):
    def test_setup_sh_runs_nothing_under_a_group_writable_umask(self):
        with fake_home() as home:
            target = install(home)
            # the version setup.sh reads from pyproject.toml (a release candidate stamps both with its own)
            script = target / "app" / __version__ / "venv" / "bin" / "composer"
            script.parent.mkdir(parents=True)
            seen = home.parent / "umask-seen"
            script.write_text(f'#!/bin/sh\numask > "{seen}"\nexit 1\n', encoding="utf-8")
            os.chmod(script, 0o755)
            os.symlink(__version__, target / "app" / "current")
            run = subprocess.run(["sh", "-c", 'umask 002; exec sh "$0" --home "$1" --yes', str(ROOT / "setup.sh"),
                                  str(target)], capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 2, run.stdout + run.stderr)  # "the environment ... does not start"
            self.assertTrue(seen.exists(), run.stdout + run.stderr)
            self.assertEqual(int(seen.read_text().strip(), 8) & 0o022, 0o022)


if __name__ == "__main__":
    unittest.main()
