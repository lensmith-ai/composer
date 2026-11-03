"""`composer doctor` stops at a failed trust check: it reads no settings from those folders and makes no model,
checker or source call with them.

The reported input: an install made in a safe folder, then the folder above it opened to another account (the same
input as the update and uninstall findings). The other account moves the install aside and puts its own in its place,
whose settings name a model endpoint it controls ("https://attacker.invalid/v1"). `composer doctor --online` then
reported "FAIL trust" and went on: it called that endpoint with your key from the environment
(an "authorization: Bearer" header holding the value of OPENAI_API_KEY). Now doctor reports the refusal and stops: no settings read, no
request made, nothing written or started.

The model and checker calls go through a recording transport and the source reads through a recording get, so these
tests never touch the network: they assert that nothing was sent at all."""
import json
import os
import shutil
import unittest
from pathlib import Path
from unittest import mock

from cross_account import as_other, shared_root
from install_helpers import fake_home
from test_lifecycle import install

from composer import doctor, home as H, installer, settings as S

POSIX = os.name == "posix" and hasattr(os, "getuid")
ATTACKER = "https://attacker.invalid/v1"
USER_KEY = "sk-FAKE-user-key-0000"
CHECKER_KEY = "sk-FAKE-checker-0000"


def attacker_settings() -> dict:
    """Settings another account would write: the writer and a separate checker both at its own endpoint."""
    cfg = json.loads(json.dumps(S.DEFAULTS))
    cfg["provider"].update({"kind": "openai", "model": "m", "base_url": ATTACKER, "key": "env",
                            "key_env": "OPENAI_API_KEY"})
    cfg["checker"].update({"same": False, "kind": "openai", "model": "m", "base_url": ATTACKER, "key": "env"})
    return cfg


class Recorder:
    """Stands in for the network: records every model request and every source read, and answers none."""

    def __init__(self):
        self.sent = []
        self.read = []
        self.connected = []

    def connect(self, address, *args, **kwargs):
        self.connected.append(address)
        raise OSError("no network in this test")

    def transport(self, url, headers, body, timeout):
        self.sent.append({"url": url, "auth": headers.get("authorization") or headers.get("x-api-key")})
        return 500, b"{}"

    def get(self, url, *args, **kwargs):
        self.read.append(url)
        raise OSError("no network in this test")


def run_doctor(home: Path, rec: Recorder) -> tuple[int, list]:
    rows = []
    env = {"OPENAI_API_KEY": USER_KEY, "COMPOSER_CHECKER_API_KEY": CHECKER_KEY}
    with mock.patch.dict(os.environ, env), \
            mock.patch.object(doctor.socket, "create_connection", rec.connect), \
            mock.patch.object(doctor.tempfile, "mkdtemp", side_effect=AssertionError("doctor wrote")):
        code = doctor.run(home, home / "data", online=True, parity=True, seals=True, out=rows.append,
                          transport=rec.transport, get=rec.get, verify=lambda *a, **k: (True, ""))
    return code, rows


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class SameAccountTests(unittest.TestCase):
    """The rule, wherever the tests run: settings naming another endpoint, in folders that fail the trust check."""

    def setUp(self):
        self._home = fake_home()
        self.home = self._home.__enter__()
        self.addCleanup(self._home.__exit__, None, None, None)
        self.parent = self.home / "parent"
        self.parent.mkdir()
        self.target = install(self.parent)
        (S.generation_dir(self.target / "data", create=False) / "config.json").write_text(
            json.dumps(attacker_settings()), encoding="utf-8")
        os.chmod(self.parent, 0o777)
        self.addCleanup(os.chmod, self.parent, 0o700)

    def test_doctor_online_sends_nothing_when_the_trust_check_fails(self):
        rec = Recorder()
        code, rows = run_doctor(self.target, rec)
        self.assertEqual(code, 1)
        self.assertEqual(rec.sent, [], "doctor called a model endpoint named by settings that failed the trust check")
        self.assertEqual(rec.read, [], "doctor read sources named by a folder that failed the trust check")
        self.assertEqual(rec.connected, [], "doctor connected to a port named by a folder that failed the trust check")
        self.assertTrue(any(r.startswith("FAIL trust:") for r in rows), rows)
        for name in doctor.ONLINE_ROWS + ("parity", "seals"):
            self.assertTrue(any(r.startswith(f"SKIP {name}: not run: the trust check failed") for r in rows),
                            (name, rows))

    def test_doctor_reads_no_settings_and_no_key_file_after_the_refusal(self):
        rec = Recorder()
        with mock.patch.object(doctor.S, "load", side_effect=AssertionError("doctor read the settings")), \
                mock.patch.object(doctor.S, "key_present", side_effect=AssertionError("doctor read the key")):
            code, rows = run_doctor(self.target, rec)
        self.assertEqual(code, 1)
        self.assertEqual(rec.sent, [])
        names = [r.split(":")[0] for r in rows]
        trust_at = next(i for i, r in enumerate(rows) if r.startswith("FAIL trust:"))
        self.assertEqual(rows[trust_at + 1].split(":")[0], "SKIP the other checks", rows)
        for name in ("settings", "key", "checker", "sources", "port", "data"):
            self.assertNotIn(f"PASS {name}", names)

    def test_a_trusted_install_still_runs_the_online_checks(self):
        os.chmod(self.parent, 0o700)
        rec, rows = Recorder(), []
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": USER_KEY, "COMPOSER_CHECKER_API_KEY": CHECKER_KEY}):
            doctor.run(self.target, self.target / "data", online=True, out=rows.append, transport=rec.transport,
                       get=rec.get)
        self.assertTrue(any(r.startswith("PASS trust:") for r in rows), rows)
        self.assertEqual({s["url"] for s in rec.sent}, {ATTACKER + "/chat/completions"})  # your own settings
        self.assertTrue(any(r.startswith("FAIL online: model") for r in rows), rows)


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class AnotherAccountTests(unittest.TestCase):
    """The reported input, with a real second account replacing the install."""

    def test_a_replaced_install_cannot_make_doctor_send_your_key_elsewhere(self):
        root = shared_root(self)
        parent = root / "parent"
        parent.mkdir(mode=0o755)
        os.chmod(parent, 0o755)
        with fake_home():
            home = parent / "inst"
            installer.run(home=home, data=None, answers_file=None, assume_yes=True, reconfigure=[], data_only=False,
                          out=lambda *_: None, interactive=False)
        gen = (home / "data" / "current").read_text(encoding="utf-8").strip()
        evil = root / "evil-settings.json"
        evil.write_text(json.dumps(attacker_settings()), encoding="utf-8")
        os.chmod(evil, 0o644)
        # so the other account can copy the layout (it builds its own install from it)
        for dirpath, dirnames, filenames in os.walk(home):
            os.chmod(dirpath, 0o755)
            for name in filenames:
                if not os.path.islink(os.path.join(dirpath, name)):
                    os.chmod(os.path.join(dirpath, name), 0o644)
        os.chmod(parent, 0o777)  # the folder above the install opened up after setup
        attack = as_other('set -e; mv "$1" "$1.aside"; mkdir -p "$1"; cp -r "$1.aside/data" "$1/data"; '
                          'cp "$2" "$1/data/generations/$3/config.json"', str(home), str(evil), gen)
        self.assertEqual(attack.returncode, 0, attack.stderr)
        self.assertEqual(os.stat(home).st_uid, 65534)
        rec = Recorder()
        code, rows = run_doctor(home, rec)
        os.chmod(parent, 0o755)
        self.assertEqual(code, 1)
        trust = [r for r in rows if r.startswith("FAIL trust:")]
        self.assertTrue(trust and "belongs to another account (uid 65534)" in trust[0], rows)
        self.assertEqual(rec.sent, [], "your key was sent to an endpoint another account named")
        self.assertEqual(rec.read, [])
        self.assertEqual(rec.connected, [])
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
