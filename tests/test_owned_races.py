"""Swaps between a check and its use. A folder that passes the owned-folder check is renamed aside and replaced by a
link to an outside folder at the last moment before Composer writes or removes in it (a deterministic hook stands in
for the race). Nothing may be written in, or removed from, the outside folder."""
import hashlib
import inspect
import os
import shutil
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from install_helpers import fake_home, snapshot
from test_lifecycle import install

from composer import home as H, installer, lifecycle as L, narration as N

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


class Stop(Exception):
    pass


def outside(root: Path) -> Path:
    folder = root / "external-directory"
    folder.mkdir()
    (folder / "KEEP").write_text("not Composer's", encoding="utf-8")
    return folder


@unittest.skipUnless(os.name == "posix", "symbolic links and folder descriptors: POSIX")
class SetupWriteRaceTests(unittest.TestCase):
    def test_bin_swapped_for_a_link_just_before_the_launcher_is_written(self):
        with fake_home() as home:
            target = home / ".lensmith-composer"
            ext = outside(home)
            answers = home / "answers.toml"
            answers.write_text(ANSWERS, encoding="utf-8")
            real = installer._launcher_text
            swapped = []

            def swap_then_text(*a, **k):  # runs after the bin folder passed its check, right before the write
                if not swapped:
                    os.rename(target / "bin", target / "bin-old")
                    os.symlink(ext, target / "bin")
                    swapped.append(True)
                return real(*a, **k)
            before = snapshot(ext)
            with mock.patch.object(installer, "_launcher_text", swap_then_text):
                try:
                    installer.run(home=target, data=None, answers_file=str(answers), assume_yes=True, reconfigure=[],
                                  data_only=False, out=lambda *_: None, interactive=False)
                except (H.HomeError, OSError):
                    pass  # refusing is fine too; writing outside is not
            self.assertTrue(swapped)
            self.assertFalse((ext / "composer").exists())
            self.assertEqual(snapshot(ext), before)


def wheel(folder: Path, version: str) -> Path:
    path = folder / f"lensmith_composer-{version}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(f"lensmith_composer-{version}.dist-info/METADATA",
                   f"Metadata-Version: 2.1\nName: lensmith-composer\nVersion: {version}\n")
    return path


@unittest.skipUnless(os.name == "posix", "symbolic links and folder descriptors: POSIX")
class VersionRemovalRaceTests(unittest.TestCase):
    def test_the_app_folder_swapped_for_a_link_just_before_a_failed_try_is_removed(self):
        with fake_home() as home:
            target = install(home)
            app = target / "app"
            (app / "1.0" / "venv" / "bin").mkdir(parents=True)
            (app / "1.0" / "venv" / "bin" / "python").write_text("", encoding="utf-8")
            os.symlink("1.0", app / "current")
            # outside: a whole app folder of its own, with a 2.0 that must survive
            ext_root = home / "external-root"
            (ext_root / "app" / "1.0").mkdir(parents=True)
            (ext_root / "app" / "2.0").mkdir()
            (ext_root / "app" / "2.0" / "KEEP").write_text("not Composer's", encoding="utf-8")
            os.symlink("1.0", ext_root / "app" / "current")
            release = wheel(home.parent, "2.0")
            sha = hashlib.sha256(release.read_bytes()).hexdigest()
            real_open = os.open
            swapped = []

            def swap_at_open(path, flags, *a, **k):  # the moment the clean-up opens the app folder
                if not swapped and str(path).endswith("app") and any(
                        f.function == "_remove_version" for f in inspect.stack()[1:6]):
                    os.rename(target, home / "aside")  # the whole app folder moves away...
                    os.symlink(ext_root, target)       # ...and a link to the outside takes its name
                    swapped.append(True)
                return real_open(path, flags, *a, **k)
            before = snapshot(ext_root)

            def probe(argv, **kw):  # makes the new environment, then the install fails: update cleans up 2.0
                if "-m" in argv and argv[argv.index("-m") + 1] == "venv":
                    Path(argv[-1]).mkdir(parents=True)
                    return mock.Mock(returncode=0, stdout="", stderr="")
                raise Stop("the install failed")
            with mock.patch("os.open", swap_at_open):
                with self.assertRaises(BaseException):
                    L.update(target, target / "data", release, sha256=sha, run=probe, log=lambda *_: None)
            self.assertTrue(swapped)
            self.assertTrue((ext_root / "app" / "2.0" / "KEEP").is_file())
            self.assertEqual(snapshot(ext_root), before)
            self.assertFalse((home / "aside" / "app" / "2.0").exists())  # the failed try was removed where it was


class ExistingVersionTests(unittest.TestCase):
    def test_an_existing_version_folder_is_never_removed_by_update(self):
        # app/current could be switched to 2.0 right after update read it, so 2.0 is not touched at all
        with fake_home() as home:
            target = install(home)
            app = target / "app"
            (app / "1.0" / "venv" / "bin").mkdir(parents=True)
            (app / "1.0" / "venv" / "bin" / "python").write_text("", encoding="utf-8")
            os.symlink("1.0", app / "current")
            (app / "2.0").mkdir()
            (app / "2.0" / "KEEP").write_text("in use, perhaps", encoding="utf-8")
            release = wheel(home.parent, "2.0")
            calls = []
            with self.assertRaises(L.LifecycleError) as ctx:
                L.update(target, target / "data", release, sha256=hashlib.sha256(release.read_bytes()).hexdigest(),
                         run=lambda argv, **kw: calls.append(argv), log=lambda *_: None)
            self.assertIn("already exists", str(ctx.exception))
            self.assertTrue((app / "2.0" / "KEEP").is_file())
            self.assertEqual(calls, [])
            self.assertEqual(os.readlink(app / "current"), "1.0")

class NarrationFallbackTests(unittest.TestCase):
    def test_without_folder_descriptors_narration_removes_nothing_by_path(self):
        with fake_home() as home:
            work = home / ".lensmith-composer" / "tmp" / "narration-check"
            work.mkdir(parents=True)
            (work / "KEEP").write_text("left in place", encoding="utf-8")
            notes = []
            with mock.patch.object(N, "CONFINED", False):
                N._remove_owned_tree(home / ".lensmith-composer", ("tmp",), "narration-check", *(
                    [notes.append] if "log" in inspect.signature(N._remove_owned_tree).parameters else []))
            self.assertTrue((work / "KEEP").is_file())


if __name__ == "__main__":
    unittest.main()
