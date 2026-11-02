"""The release-candidate script (scripts/release/rc.py): its arguments, the checksum file it writes, the version it
stamps, and the failing tests it reports. Offline; the build itself is exercised by running the script."""
import argparse
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "release" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RCTests(unittest.TestCase):
    def setUp(self):
        self.rc = load("rc")

    def test_rc_arguments(self):
        self.assertEqual(self.rc.parse_rc("1=main"), (1, "main"))
        self.assertEqual(self.rc.parse_rc("2=24eb934"), (2, "24eb934"))
        for bad in ("main", "0=main", "1=", "x=main", "1=main;rm"):
            with self.subTest(bad=bad), self.assertRaises(argparse.ArgumentTypeError):
                self.rc.parse_rc(bad)
        self.assertEqual(self.rc.rc_version("0.2.0", 2), "0.2.0rc2")

    def test_version_and_refusals(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                self.rc.main(["--version", "0.2.0rc1", "--rc", "1=main", "--out", str(Path(d) / "out")])
            with self.assertRaises(SystemExit):
                self.rc.main(["--version", "0.2.0", "--rc", "1=main", "--rc", "1=main", "--out", str(Path(d) / "o")])
            busy = Path(d) / "busy"
            busy.mkdir()
            (busy / "x").write_text("x")
            with self.assertRaises(SystemExit):
                self.rc.main(["--version", "0.2.0", "--rc", "1=main", "--out", str(busy)])

    def test_sums_are_the_same_format_as_sha256sum_and_the_build(self):
        build = load("build")
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / "b.whl").write_bytes(b"wheel")
            (folder / "a.tar.gz").write_bytes(b"sdist")
            want = (f"{hashlib.sha256(b'sdist').hexdigest()}  a.tar.gz\n"
                    f"{hashlib.sha256(b'wheel').hexdigest()}  b.whl\n")
            self.assertEqual(self.rc.sums_text(folder), want)
            build.sha256sums(folder)
            self.assertEqual((folder / "SHA256SUMS").read_text(), want)
            self.assertEqual(self.rc.sums_text(folder), want)  # SHA256SUMS itself is never listed

    def test_stamp_writes_both_version_lines(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)
            (src / "composer").mkdir()
            (src / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.2.0"\n')
            (src / "composer" / "__init__.py").write_text('"""doc"""\n__version__ = "0.2.0"\n')
            self.assertEqual(self.rc.stamp_version(src, "0.2.0rc1"), ["pyproject.toml", "composer/__init__.py"])
            self.assertEqual(self.rc.read_version(src), "0.2.0rc1")
            self.assertIn('__version__ = "0.2.0rc1"', (src / "composer" / "__init__.py").read_text())
            self.assertEqual(self.rc.stamp_version(src, "0.2.0rc1"), [])

    def test_failing_tests_are_read_from_the_log(self):
        log = ("....\n======\nFAIL: test_a (test_x.Case.test_a)\n------\nERROR: test_b (test_y.Other.test_b)\n"
               "FAIL: test_a (test_x.Case.test_a)\n")
        self.assertEqual(self.rc.failing_tests(log), ["test_a (test_x.Case.test_a)", "test_b (test_y.Other.test_b)"])


class SourceReleaseTests(unittest.TestCase):
    def test_the_sdist_carries_what_setup_needs(self):
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        self.assertIn("include setup.sh", manifest)
        for tree in ("docs", "scripts", "tests", "examples"):
            self.assertIn(f"graft {tree}", manifest)


if __name__ == "__main__":
    unittest.main()
