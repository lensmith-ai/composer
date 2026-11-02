"""setup.sh must not hand model keys or the server pass phrase to the programs it starts to install Composer (Python
discovery, venv, pip and the build backends pip runs, version checks); only Composer's own setup step gets them.

A stand-in python3 on PATH writes, for every start, whether each secret variable reached it, makes a fake
environment when asked for a venv, and stops pip with exit 42: nothing is downloaded or installed."""
import os
import shutil
import stat
import subprocess
import unittest
from pathlib import Path

from helpers import ROOT
from install_helpers import fake_home

SECRETS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "COMPOSER_CHECKER_API_KEY", "COMPOSER_SERVER_PASS")

STAND_IN = r"""#!/bin/sh
log=__LOG__
# the names of every variable in this program's environment whose value is one of the test's secrets
seen=$(env | sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=FAKE-.*-0308$/\1/p' | sort | tr '\n' ' ')
printf '%s|%s\n' "$*" "$seen" >> "$log"
case "$*" in
  *"-m venv "*)
    for last in "$@"; do :; done
    mkdir -p "$last/bin" && cp "$0" "$last/bin/python" && chmod 755 "$last/bin/python"; exit 0 ;;
  *"-m pip"*) exit 42 ;;
  *"print("*) echo "Python 3.12.0"; exit 0 ;;
  *) exit 0 ;;
esac
"""


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "setup.sh is a POSIX shell script")
class SetupShKeysTests(unittest.TestCase):
    def test_only_composer_setup_gets_the_keys(self):
        self.check(extra={})

    def test_a_holding_name_handed_in_by_the_caller_does_not_carry_a_key_to_pip(self):
        # setup.sh holds each key in held_<NAME>; if the caller already exported that name, it must not stay exported
        for name in SECRETS:
            with self.subTest(holding=name):
                self.check(extra={f"held_{name}": "preexisting-variable"})

    def check(self, extra):
        with fake_home() as home:
            bindir = home.parent / "stand-in-bin"
            bindir.mkdir()
            log = home.parent / "starts.log"
            fake = bindir / "python3"
            fake.write_text(STAND_IN.replace("__LOG__", str(log)), encoding="utf-8")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = dict(os.environ, PATH=f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                       **{k: f"FAKE-{k}-0308" for k in SECRETS}, **extra)
            run = subprocess.run(["sh", str(ROOT / "setup.sh"), "--home", str(home / "shellhome"), "--yes",
                                  "--no-test-call"], capture_output=True, text=True, timeout=120, env=env)
            self.assertNotEqual(run.returncode, 0)  # the stand-in pip stops it
            starts = [line.rsplit("|", 1) for line in log.read_text(encoding="utf-8").splitlines()]
            pip = [s for s in starts if "-m pip" in s[0]]
            self.assertTrue(pip, starts)  # it got as far as pip
            self.assertTrue([s for s in starts if "-m composer setup" in s[0]], starts)  # and checked with Composer
            for argv, seen in starts:
                with self.subTest(start=argv[:80]):
                    if "-m composer setup" in argv:
                        self.assertEqual(sorted(seen.split()), sorted(SECRETS))  # Composer's own step keeps them
                    else:
                        self.assertEqual(seen.strip(), "", f"{argv[:80]} saw {seen}")
            self.assertFalse((home / "shellhome").exists() and any((home / "shellhome").iterdir())
                             and (home / "shellhome" / "data").exists())


if __name__ == "__main__":
    unittest.main()
