"""A real second account for the trust-contract tests: a folder it can reach, and commands run as it.

The attacks these tests stand for come from ANOTHER account on the same machine, so where it can, the test makes the
change as a second account (uid and gid 65534, "nobody" on most systems) in a child process. That needs root, to drop
to that account; elsewhere those tests skip and say why, and the rule itself is still tested as a pure function.

The folder: the tests' usual temporary folder is under your own home (private), which a second account cannot reach.
So these tests work in a fresh folder made by root, 0755, in a system folder that passes the trust contract
(/var/lib, /opt, /srv or /usr/local; or COMPOSER_TEST_SHARED_ROOT), removed again afterwards.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from composer.home import HomeError, check_trust

OTHER = 65534
CANDIDATES = ("/var/lib", "/opt", "/srv", "/usr/local")


def can_act_as_other() -> str | None:
    """None when a child process can run as the second account; otherwise why not (the skip reason)."""
    if os.name != "posix" or not hasattr(os, "getuid"):
        return "needs POSIX owners and permission bits"
    if os.getuid() != 0:
        return f"needs root to run a child process as a second account (uid {OTHER}); this runs as uid {os.getuid()}"
    return None


def shared_root(test: unittest.TestCase) -> Path:
    """A fresh root-owned 0755 folder the second account can reach and Composer's trust check accepts; removed when
    the test ends. Skips the test when there is none."""
    why = can_act_as_other()
    if why:
        test.skipTest(why)
    places = [os.environ.get("COMPOSER_TEST_SHARED_ROOT", "")] + list(CANDIDATES)
    for place in places:
        if not place or not os.path.isdir(place):
            continue
        try:
            check_trust(Path(place) / "probe")
        except HomeError:
            continue
        root = Path(tempfile.mkdtemp(prefix="composer-xacct-", dir=place))
        os.chmod(root, 0o755)
        test.addCleanup(shutil.rmtree, root, True)
        return root
    test.skipTest("no root-owned system folder that a second account can reach passes the trust check here")
    raise AssertionError("unreachable")


def as_other(script: str, *args: str) -> subprocess.CompletedProcess:
    """Run a /bin/sh script as the second account (uid and gid 65534, no other groups): its exit code and output."""
    return subprocess.run(["/bin/sh", "-c", script, "attacker", *args], user=OTHER, group=OTHER, extra_groups=[],
                          capture_output=True, text=True, timeout=60, cwd="/")
