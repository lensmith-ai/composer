"""`composer doctor --online` checks the app folder again before its narration check writes in it.

The reported input: `composer doctor --online --home DIR/inst`, where DIR can be written by another account and inst
does not exist yet, with the data folder somewhere safe and narration on. The trust row checked only the data folder
(there was no app folder to check). While the model and source checks ran, the other account made inst with an
install-manifest.json (so narration works in inst, not in the data folder) and a tmp link to a folder of its choosing.
The narration check then made its scratch folder (named doctor- and eight random characters) inside that folder.
Now it checks inst first, the same way it checks every folder it writes in, refuses, and writes nothing.

No network: the source reads go through a recording get, and narration through a recording render."""
import os
import unittest
from pathlib import Path
from unittest import mock

from cross_account import as_other, shared_root
from install_helpers import fake_home

from composer import doctor, home as H, installer, settings as S

POSIX = os.name == "posix" and hasattr(os, "getuid")


def data_only_install(data: Path) -> None:
    """A data folder of its own (no app folder), with narration on."""
    installer.run(home=None, data=data, answers_file=None, assume_yes=True, reconfigure=[], data_only=True,
                  out=lambda *_: None, interactive=False)
    cfg = S.load(data)
    cfg["narration"].update({"enabled": True, "engine": "kokoro-onnx", "voices": ["af_heart"],
                             "model_path": "/nonexistent/m.onnx", "voices_path": "/nonexistent/v.bin"})
    S.save(data, cfg)


class Watch:
    """Records where doctor made scratch folders and whether it narrated; reads no source."""

    def __init__(self):
        self.made = []
        self.rendered = []
        self.read = []
        self._mkdtemp = doctor.tempfile.mkdtemp

    def mkdtemp(self, *args, **kwargs):
        path = self._mkdtemp(*args, **kwargs)
        self.made.append(os.path.realpath(path))
        return path

    def render(self, *, text, voice, out_base, timeout):
        self.rendered.append(str(out_base))
        out = Path(str(out_base) + ".wav")
        out.write_bytes(b"RIFF")
        return {"file": str(out), "format": "wav"}

    def get(self, url, *args, **kwargs):
        self.read.append(url)
        raise OSError("no network in this test")


def run_doctor(home: Path, data: Path, watch: Watch, after_trust=None) -> list:
    rows = []
    real = doctor.trust_check

    def trust_then(r, h, d):
        real(r, h, d)
        if after_trust:
            after_trust()
    with mock.patch.object(doctor, "trust_check", trust_then), \
            mock.patch.object(doctor.tempfile, "mkdtemp", watch.mkdtemp), \
            mock.patch.object(doctor.socket, "create_connection", side_effect=OSError("no network in this test")):
        doctor.run(home, data, online=True, out=rows.append, get=watch.get, render=watch.render)
    return rows


def narration_row(rows: list) -> str:
    found = [r for r in rows if r.split(":")[0].endswith("online") and "narration" in r.split(":")[1]]
    return found[0] if found else ""


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class SameAccountTests(unittest.TestCase):
    """The rule, wherever the tests run: the app folder appears, in a folder others can write, after the trust row."""

    def setUp(self):
        self._home = fake_home()
        self.home = self._home.__enter__()
        self.addCleanup(self._home.__exit__, None, None, None)
        self.data = self.home / "safe" / "data"
        data_only_install(self.data)
        self.shared = self.home / "shared"
        self.shared.mkdir()
        os.chmod(self.shared, 0o777)
        self.addCleanup(os.chmod, self.shared, 0o700)
        self.inst = self.shared / "inst"
        self.victim = self.home / "victim"
        self.victim.mkdir(mode=0o700)
        (self.victim / "KEEP").write_text("keep\n", encoding="utf-8")

    def plant(self):
        self.inst.mkdir()
        (self.inst / H.MANIFEST).write_text("{}", encoding="utf-8")
        os.symlink(self.victim, self.inst / "tmp")

    def test_an_app_folder_made_after_the_trust_row_is_checked_before_narration_writes(self):
        watch = Watch()
        rows = run_doctor(self.inst, self.data, watch, after_trust=self.plant)
        self.assertTrue(any(r.startswith("PASS trust:") for r in rows), rows)  # only the data folder existed then
        inside = [p for p in watch.made if Path(p) == self.victim or self.victim in Path(p).parents]
        self.assertEqual(inside, [], "doctor made its scratch folder in the folder a link in the app folder named")
        self.assertEqual(watch.made, [])
        self.assertEqual(watch.rendered, [])
        self.assertEqual(sorted(os.listdir(self.victim)), ["KEEP"])
        row = narration_row(rows)
        self.assertTrue(row.startswith("FAIL online: narration: refused:"), rows)
        self.assertIn(f"{self.shared} can be written by other accounts (mode 0777)", row)

    def test_narration_still_runs_when_no_app_folder_appears(self):
        watch = Watch()
        rows = run_doctor(self.inst, self.data, watch)
        self.assertEqual(len(watch.made), 1, rows)
        self.assertEqual(Path(watch.made[0]).parent, Path(os.path.realpath(self.data / "tmp")))
        self.assertEqual(len(watch.rendered), 1)
        self.assertTrue(narration_row(rows).startswith("PASS online: narration:"), rows)
        self.assertFalse(os.path.lexists(self.inst))


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class AnotherAccountTests(unittest.TestCase):
    """The reported input, with a real second account making the app folder after the trust row."""

    def test_an_app_folder_planted_by_another_account_gets_no_scratch_folder(self):
        root = shared_root(self)
        safe = root / "safe"
        safe.mkdir(mode=0o755)
        data = safe / "data"
        with fake_home():
            data_only_install(data)
        shared = root / "shared"
        shared.mkdir()
        os.chmod(shared, 0o777)
        inst = shared / "inst"
        victim = root / "victim"
        victim.mkdir(mode=0o755)
        (victim / "KEEP").write_text("keep\n", encoding="utf-8")
        planted = {}

        def plant():
            planted["result"] = as_other('set -e; mkdir "$1"; echo "{}" > "$1/install-manifest.json"; '
                                         'ln -s "$2" "$1/tmp"', str(inst), str(victim))
        watch = Watch()
        rows = run_doctor(inst, data, watch, after_trust=plant)
        self.assertEqual(planted["result"].returncode, 0, planted["result"].stderr)
        self.assertEqual(os.stat(inst).st_uid, 65534)
        self.assertTrue(any(r.startswith("PASS trust:") for r in rows), rows)
        inside = [p for p in watch.made if Path(p) == victim or victim in Path(p).parents]
        self.assertEqual(inside, [], "doctor made its scratch folder where another account's link pointed")
        self.assertEqual(watch.made, [])
        self.assertEqual(watch.rendered, [])
        self.assertEqual(sorted(os.listdir(victim)), ["KEEP"])
        row = narration_row(rows)
        self.assertTrue(row.startswith("FAIL online: narration: refused:"), rows)
        self.assertIn("belongs to another account (uid 65534)", row)


if __name__ == "__main__":
    unittest.main()
