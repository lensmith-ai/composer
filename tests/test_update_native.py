"""A real native update between two release files, through bin/composer: install version A the way setup.sh does,
update to B, roll back, update again, uninstall, set up again and delete the data. Then the same with the current
environment broken (an update that stopped half way, or a Python that went away): rollback, uninstall and
delete-data must still work.

Both release files are wheels built here from this folder (with the standard library, no network): A carries this
folder's version, B the same code with ".post1" added. Neither depends on claim-seal, so pip installs them offline.
"""
import base64
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from helpers import ROOT
from install_helpers import fake_home

from composer import __version__

try:
    import ensurepip  # noqa: F401  (python -m venv needs it to put pip in the new environment)
    HAVE_VENV = True
except ImportError:
    HAVE_VENV = False

A, B = __version__, __version__ + ".post1"
MARKER_TEXT = "lensmith-composer home v1\n"


def build_wheel(out_dir: Path, version: str) -> Path:
    """A pure-Python wheel of this folder's `composer` package at `version` (no dependencies)."""
    dist = f"lensmith_composer-{version}.dist-info"
    files = {}
    for path in sorted((ROOT / "composer").rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        rel = path.relative_to(ROOT).as_posix()
        blob = path.read_bytes()
        if rel == "composer/__init__.py":
            blob = blob.replace(f'__version__ = "{__version__}"'.encode(), f'__version__ = "{version}"'.encode())
            assert f'"{version}"'.encode() in blob
        files[rel] = blob
    files[f"{dist}/METADATA"] = (f"Metadata-Version: 2.1\nName: lensmith-composer\nVersion: {version}\n"
                                 "Requires-Python: >=3.10\n").encode()
    files[f"{dist}/WHEEL"] = (b"Wheel-Version: 1.0\nGenerator: composer-tests\nRoot-Is-Purelib: true\n"
                              b"Tag: py3-none-any\n")
    files[f"{dist}/entry_points.txt"] = b"[console_scripts]\ncomposer = composer.cli:main\n"
    record = []
    for name, blob in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(blob).digest()).rstrip(b"=").decode()
        record.append(f"{name},sha256={digest},{len(blob)}")
    record.append(f"{dist}/RECORD,,")
    files[f"{dist}/RECORD"] = ("\n".join(record) + "\n").encode()
    wheel = out_dir / f"lensmith_composer-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as z:
        for name, blob in files.items():
            z.writestr(name, blob)
    return wheel


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(os.name == "posix" and HAVE_VENV, "a native install: POSIX with python -m venv")
class NativeUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dist = Path(tempfile.mkdtemp(prefix="composer-dist-"))
        cls.wheel_a, cls.wheel_b = build_wheel(cls.dist, A), build_wheel(cls.dist, B)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dist, ignore_errors=True)

    def sh(self, *argv, ok=True, timeout=300, cwd=None):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}  # the installed code only
        proc = subprocess.run([str(a) for a in argv], capture_output=True, text=True, timeout=timeout,
                              cwd=str(cwd or self.home), env=dict(env, HOME=str(self.home)))
        if ok:
            self.assertEqual(proc.returncode, 0, f"{argv}: {proc.stdout[-1500:]}{proc.stderr[-2500:]}")
        return proc

    def install_a(self):
        """What setup.sh does: the marker, app/<version>/venv with the release in it, app/current, then setup."""
        h = self.target
        created = not h.exists()
        h.mkdir(mode=0o700, exist_ok=True)
        if not (h / ".composer-home").exists():
            (h / ".composer-home").write_text(MARKER_TEXT, encoding="utf-8")
        for name in ("cache", "tmp", "app"):
            (h / name).mkdir(mode=0o700, exist_ok=True)
        venv = h / "app" / A / "venv"
        self.sh(sys.executable, "-m", "venv", venv)
        self.sh(venv / "bin" / "python", "-m", "pip", "install", "--quiet", "--no-index", "--no-deps",
                "--disable-pip-version-check", self.wheel_a)
        os.symlink(A, h / "app" / "current")
        self.sh(h / "app" / "current" / "venv" / "bin" / "composer", "setup", "--home", h, "--yes",
                *(["--home-created"] if created else []))

    def composer(self, *args, ok=True):
        return self.sh(self.target / "bin" / "composer", *args, ok=ok)

    def version(self) -> str:
        return self.composer("--version").stdout.strip()

    def update_b(self):
        return self.composer("update", "--from-file", self.wheel_b, "--sha256", sha(self.wheel_b))

    def current(self) -> str:
        return os.readlink(self.target / "app" / "current")

    def data_files(self) -> dict:
        data = self.target / "data"
        return {p.relative_to(data).as_posix(): sha(p) for p in sorted(data.rglob("*"))
                if p.is_file() and "generations" in p.parts and "recovery" not in p.parts}

    def assert_data_kept(self, before: dict):
        now = self.data_files()
        self.assertEqual({k: now.get(k) for k in before}, before)  # every file there before, unchanged

    def test_install_update_rollback_update_uninstall_setup_again_delete_data(self):
        with fake_home() as home:
            self.home, self.target = home, home / ".lensmith-composer"
            self.install_a()
            self.assertEqual(self.version(), f"composer {A}")
            settings = self.data_files()
            self.update_b()
            self.assertEqual((self.current(), self.version()), (B, f"composer {B}"))
            self.assert_data_kept(settings)
            # run from a folder holding another `composer` package (this checkout): the installed code still runs
            self.assertEqual(self.sh(self.target / "bin" / "composer", "--version", cwd=ROOT).stdout.strip(),
                             f"composer {B}")
            for script in ("composer", "pip"):  # every script in the new environment starts from where it lives
                first = (self.target / "app" / B / "venv" / "bin" / script).read_text(encoding="utf-8").splitlines()[0]
                interpreter = Path(first[2:].split()[0])
                self.assertEqual(interpreter.parent, self.target / "app" / B / "venv" / "bin", first)
                self.assertTrue(interpreter.exists(), first)
            self.assertEqual(sorted(n for n in os.listdir(self.target / "app")), sorted([A, B, "current"]))
            self.composer("doctor")
            self.composer("rollback")
            self.assertEqual((self.current(), self.version()), (A, f"composer {A}"))
            self.assertEqual(sorted(os.listdir(self.target / "app")), [A, "current"])  # rollback removes B
            self.update_b()
            self.assertEqual((self.current(), self.version()), (B, f"composer {B}"))
            self.composer("uninstall")
            self.assertFalse((self.target / "app").exists())
            self.assertFalse((self.target / "bin").exists())
            self.assert_data_kept(settings)
            self.install_a()  # setup again picks the kept data up
            self.assert_data_kept(settings)
            self.composer("uninstall", "--delete-data", "--yes")
            self.assertFalse(self.target.exists())

    def test_a_failed_update_leaves_the_old_version_current_and_working(self):
        with fake_home() as home:
            self.home, self.target = home, home / ".lensmith-composer"
            self.install_a()
            broken = self.dist / f"lensmith_composer-{B}-py3-none-any.whl"
            bad = self.dist / "bad" / broken.name
            bad.parent.mkdir(exist_ok=True)
            with zipfile.ZipFile(broken) as src, zipfile.ZipFile(bad, "w") as dst:
                for item in src.infolist():
                    blob = src.read(item)
                    if item.filename == "composer/cli.py":
                        blob = b"raise ImportError('a release that does not start')\n"
                    dst.writestr(item, blob)
            got = self.composer("update", "--from-file", bad, "--sha256", sha(bad), ok=False)
            self.assertNotEqual(got.returncode, 0)
            self.assertNotIn("Traceback", got.stderr)
            self.assertEqual((self.current(), self.version()), (A, f"composer {A}"))
            self.assertFalse((self.target / "app" / B).exists())
            self.assertEqual(sorted(os.listdir(self.target / "app")), [A, "current"])
            self.update_b()  # and the next, good update goes through
            self.assertEqual(self.version(), f"composer {B}")
            self.composer("uninstall", "--delete-data", "--yes")
            self.assertFalse(self.target.exists())

    def test_an_interrupted_update_on_a_broken_environment_still_rolls_back_and_uninstalls(self):
        with fake_home() as home:
            self.home, self.target = home, home / ".lensmith-composer"
            self.install_a()
            settings = self.data_files()
            # stop an update right after it switched app/current (as if the computer went off), then break the
            # new environment: neither its scripts nor its python can start
            code = ("import sys; from pathlib import Path; from composer import lifecycle as L\n"
                    "h = Path(sys.argv[1])\n"
                    "try:\n"
                    "    L.update(h, h / 'data', Path(sys.argv[2]), sha256=sys.argv[3], crash_after='code_switched')\n"
                    "except L.Crash:\n"
                    "    sys.exit(0)\n"
                    "sys.exit(1)\n")
            self.sh(self.target / "app" / A / "venv" / "bin" / "python", "-I", "-c", code, self.target, self.wheel_b,
                    sha(self.wheel_b))
            self.assertEqual(self.current(), B)
            for name in os.listdir(self.target / "app" / B / "venv" / "bin"):
                if name.startswith("python"):
                    os.unlink(self.target / "app" / B / "venv" / "bin" / name)
            refused = self.composer("up", ok=False)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("rollback", refused.stderr)
            self.composer("rollback")
            self.assertEqual((self.current(), self.version()), (A, f"composer {A}"))
            self.assert_data_kept(settings)
            self.composer("uninstall", "--delete-data", "--yes")
            self.assertFalse(self.target.exists())

    def test_uninstall_and_delete_data_work_when_no_environment_starts(self):
        python3 = shutil.which("python3")
        if not python3 or subprocess.run([python3, "-c", "import sys; sys.exit(sys.version_info < (3, 10))"]
                                         ).returncode != 0:
            self.skipTest("needs a python3 3.10+ on PATH")
        with fake_home() as home:
            self.home, self.target = home, home / ".lensmith-composer"
            self.install_a()
            self.update_b()
            for version in (A, B):  # the Python every environment was made from went away (a system upgrade)
                for name in os.listdir(self.target / "app" / version / "venv" / "bin"):
                    if name.startswith("python"):
                        os.unlink(self.target / "app" / version / "venv" / "bin" / name)
            self.assertIn("python3", self.composer("doctor", ok=False).stderr)  # says what it runs with
            self.composer("uninstall", "--delete-data", "--yes")
            self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
