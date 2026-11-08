"""scripts/release/make_installer.py: the dependency hashes it checks are written in the repository and agree with
pyproject.toml; a file with another hash is refused. (The download and the build run only in the release workflow.)"""
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MakeInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mi = load("make_installer", ROOT / "scripts" / "release" / "make_installer.py")
        cls.pinned = json.loads((ROOT / "scripts" / "install" / "pinned-extras.json").read_text(encoding="utf-8"))

    def test_the_pinned_versions_are_the_ones_pyproject_pins(self):
        facts = self.mi.bi.project_facts()
        self.assertEqual(self.pinned["certifi"]["version"], facts["certifi"])
        self.assertEqual(self.pinned["setuptools"]["version"], facts["setuptools"])
        for name in ("certifi", "setuptools"):
            row = self.pinned[name]
            self.assertEqual(row["file"], f"{name}-{row['version']}-py3-none-any.whl")
            self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")

    def test_setuptools_hash_is_one_the_release_tools_lock_lists(self):
        lock = (ROOT / "scripts" / "release" / "release-tools.txt").read_text(encoding="utf-8")
        self.assertIn(self.pinned["setuptools"]["sha256"], lock)

    def test_a_file_with_another_hash_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "x.whl"
            f.write_bytes(b"not the pinned wheel")
            with self.assertRaises(SystemExit) as cm:
                self.mi.need_sha(f, "0" * 64, "a test file")
            self.assertIn("expected " + "0" * 64, str(cm.exception))
            self.mi.need_sha(f, self.mi.bi.sha256(f), "a test file")  # the right hash passes

    def test_the_build_jobs_sums_must_agree_with_the_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "a.whl").write_bytes(b"wheel")
            (d / "SHA256SUMS").write_text(f"{self.mi.bi.sha256(d / 'a.whl')}  a.whl\n")
            self.mi.check_listed_sums(d, ("a.whl",))  # agrees
            (d / "a.whl").write_bytes(b"changed in transit")
            with self.assertRaises(SystemExit):
                self.mi.check_listed_sums(d, ("a.whl",))

    def test_the_names_it_makes_are_the_names_build_install_pins(self):
        facts = self.mi.bi.project_facts()
        v = facts["version"]
        names = [f"lensmith_composer-{v}.tar.gz", f"lensmith_composer-{v}-py3-none-any.whl",
                 self.pinned["certifi"]["file"], self.pinned["setuptools"]["file"],
                 f"claim_seal-0.2.0-py3-none-any.whl", f"claim-seal-{facts['cs_commit']}.tar.gz"]
        with tempfile.TemporaryDirectory() as tmp:
            stage, out = Path(tmp) / "stage", Path(tmp) / "out"
            stage.mkdir()
            for n in names:
                (stage / n).write_bytes(n.encode())
            pins = self.mi.bi.build(stage, out, install_url="https://example.invalid/install.sh", mirror_url="https://example.invalid/m",
                                    release_base="https://example.invalid/r", check_source=False)
            self.assertEqual({pins["KIT"], pins["COMPOSER_WHEEL"], pins["CERTIFI_WHEEL"], pins["SETUPTOOLS_WHEEL"],
                              pins["CLAIMSEAL_WHEEL"], pins["CLAIMSEAL_SRC"]}, set(names))
            self.assertTrue((out / "install.sh").is_file())

    def test_an_existing_non_empty_out_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "keep").write_text("x")
            with self.assertRaises(SystemExit):
                self.mi.main(["--dist", tmp, "--out", tmp])


if __name__ == "__main__":
    unittest.main()
