"""A link planted in the app folder must not lead setup, update, rollback, uninstall or narration to write or remove
anything outside it. Each test plants a symbolic link where Composer keeps one of its own folders, points it at a
folder outside holding a sentinel file, and runs the public entry point: it must refuse, and the outside folder must
be exactly as it was."""
import hashlib
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from helpers import ROOT
from install_helpers import fake_home, snapshot
from test_lifecycle import FakeRun, install, release_file

from composer import home as H, installer, lifecycle as L, narration as N

OWNED = ("bin", "app", "python", "bootstrap", "narration", "models", "cache", "tmp")  # what Composer makes there

ANSWERS = """
[provider]
kind = "none"

[narration]
enabled = false

[parser]
trafilatura = false

[schedule]
enabled = false
"""


def marked_home(home: Path) -> Path:
    """An app folder with Composer's marker and manifest, as setup leaves it before anything else."""
    target = home / ".lensmith-composer"
    target.mkdir(mode=0o700)
    H.atomic_write(target / H.MARKER, H.MARKER_TEXT, mode=0o600)
    H.save_manifest(target, H.new_manifest(target, home_created=True, version="0.2.0"))
    return target


def outside(home: Path, name: str = "external-directory") -> Path:
    folder = home / name
    folder.mkdir()
    (folder / "KEEP").write_text("not Composer's", encoding="utf-8")
    return folder


class SetupTests(unittest.TestCase):
    def test_setup_refuses_every_owned_folder_that_is_a_link(self):
        for name in OWNED:
            with self.subTest(folder=name), fake_home() as home:
                target = marked_home(home)
                ext = outside(home)
                os.symlink(ext, target / name)
                answers = home / "answers.toml"
                answers.write_text(ANSWERS, encoding="utf-8")
                before = snapshot(ext)
                try:
                    rc = installer.run(home=target, data=None, answers_file=str(answers), assume_yes=True,
                                       reconfigure=[], data_only=False, out=lambda *_: None, interactive=False)
                except H.HomeError as exc:
                    rc = str(exc)
                self.assertIn("symbolic link", str(rc))
                self.assertEqual(snapshot(ext), before)
                self.assertFalse((ext / "composer").exists())

    def test_setup_refuses_a_version_pointer_that_leaves_the_app_folder(self):
        with fake_home() as home:
            target = marked_home(home)
            ext = outside(home)
            (target / "app").mkdir()
            os.symlink(ext, target / "app" / "current")
            answers = home / "answers.toml"
            answers.write_text(ANSWERS, encoding="utf-8")
            before = snapshot(ext)
            with self.assertRaises(H.HomeError):
                installer.run(home=target, data=None, answers_file=str(answers), assume_yes=True, reconfigure=[],
                              data_only=False, out=lambda *_: None, interactive=False)
            self.assertEqual(snapshot(ext), before)

    def test_a_clean_install_still_passes(self):
        with fake_home() as home:
            target = marked_home(home)
            answers = home / "answers.toml"
            answers.write_text(ANSWERS, encoding="utf-8")
            self.assertEqual(installer.run(home=target, data=None, answers_file=str(answers), assume_yes=True,
                                           reconfigure=[], data_only=False, out=lambda *_: None, interactive=False), 0)
            self.assertTrue((target / "bin" / "composer").is_file())
            self.assertFalse(any(os.path.islink(target / n) for n in OWNED))


def wheel(folder: Path, version: str) -> Path:
    import zipfile
    path = folder / f"lensmith_composer-{version}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(f"lensmith_composer-{version}.dist-info/METADATA",
                   f"Metadata-Version: 2.1\nName: lensmith-composer\nVersion: {version}\n")
    return path


class Stop(Exception):
    pass


class UpdateTests(unittest.TestCase):
    def test_update_through_a_linked_app_folder_removes_nothing_outside(self):
        # home/app -> external-directory, holding current -> 1.0, a real 1.0, and 2.0/KEEP (an "earlier try")
        with fake_home() as home:
            target = install(home)
            ext = home / "external-directory"
            (ext / "1.0" / "venv" / "bin").mkdir(parents=True)
            (ext / "1.0" / "venv" / "bin" / "python").write_text("", encoding="utf-8")
            (ext / "2.0").mkdir()
            (ext / "2.0" / "KEEP").write_text("not Composer's", encoding="utf-8")
            os.symlink("1.0", ext / "current")
            app = target / "app"
            if app.exists():
                shutil.rmtree(app)
            os.symlink(ext, app)
            release = wheel(home.parent, "2.0")
            sha = hashlib.sha256(release.read_bytes()).hexdigest()
            before = snapshot(ext)
            calls = []

            def probe(argv, **kw):
                calls.append(argv)
                raise Stop("the update reached a subprocess")
            with self.assertRaises(L.LifecycleError) as ctx:
                L.update(target, target / "data", release, sha256=sha, run=probe, log=lambda *_: None)
            self.assertIn("symbolic link", str(ctx.exception))
            self.assertTrue((ext / "2.0" / "KEEP").is_file())
            self.assertEqual(snapshot(ext), before)
            self.assertEqual(calls, [])

    def native(self, home):
        target = install(home)
        (target / "app" / "0.2.0" / "venv" / "bin").mkdir(parents=True)
        (target / "app" / "0.2.0" / "venv" / "bin" / "python").write_text("", encoding="utf-8")
        os.symlink("0.2.0", target / "app" / "current")
        return target

    def test_update_refuses_a_linked_version_environment_or_cache(self):
        for rel in ("app/0.2.0/venv", "cache", "tmp", "bin"):
            with self.subTest(link=rel), fake_home() as home:
                target = self.native(home)
                ext = outside(home)
                path = target / rel
                if path.exists():
                    shutil.rmtree(path)
                os.symlink(ext, path)
                release = release_file(home.parent)
                before = snapshot(ext)
                with self.assertRaises(L.LifecycleError):
                    L.update(target, target / "data", release, sha256=hashlib.sha256(release.read_bytes()).hexdigest(),
                             run=FakeRun(), log=lambda *_: None)
                self.assertEqual(snapshot(ext), before)
                self.assertEqual(os.readlink(target / "app" / "current"), "0.2.0")

    def test_rollback_refuses_a_linked_app_folder(self):
        with fake_home() as home:
            target = self.native(home)
            ext = outside(home)
            shutil.rmtree(target / "bin")
            os.symlink(ext, target / "bin")
            before = snapshot(ext)
            with self.assertRaises(L.LifecycleError) as ctx:
                L.rollback(target, target / "data", log=lambda *_: None)
            self.assertIn("symbolic link", str(ctx.exception))
            self.assertEqual(snapshot(ext), before)


class NarrationTests(unittest.TestCase):
    def test_narration_never_writes_through_a_linked_folder(self):
        for rel, call in ((("models",), lambda h: N.download(h, log=lambda *_: None,
                                                             opener=lambda *a, **k: (_ for _ in ()).throw(Stop()))),
                          (("narration",), lambda h: N.install_runtime(h, log=lambda *_: None)),
                          (("tmp",), lambda h: N.check_server("http://127.0.0.1:9/", home=h,
                                                              opener=_voices_opener))):
            with self.subTest(link=rel), fake_home() as home:
                target = marked_home(home)
                ext = outside(home)
                os.symlink(ext, target.joinpath(*rel))
                before = snapshot(ext)
                with self.assertRaises(N.NarrationError):
                    call(target)
                self.assertEqual(snapshot(ext), before)


class _VoicesOpener:
    """A Kokoro server that lists the three voices (the check then tries to work in tmp/)."""

    def open(self, *a, **k):
        import io
        import json
        return io.BytesIO(json.dumps({"voices": list(N.VOICES)}).encode())


_voices_opener = _VoicesOpener()


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "setup.sh is a POSIX shell script")
class SetupShTests(unittest.TestCase):
    def test_setup_sh_refuses_a_linked_owned_folder_before_any_write(self):
        for name in ("bin", "app", "tmp", "cache", "bootstrap", "python"):
            with self.subTest(folder=name), fake_home() as home:
                target = marked_home(home)
                ext = outside(home)
                os.symlink(ext, target / name)
                before = snapshot(ext)
                run = subprocess.run(["sh", str(ROOT / "setup.sh"), "--home", str(target), "--yes"],
                                     capture_output=True, text=True, timeout=120)
                self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
                self.assertIn("symbolic link", run.stderr)
                self.assertEqual(snapshot(ext), before)


if __name__ == "__main__":
    unittest.main()
