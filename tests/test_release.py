"""The release scripts: the claim-sealed release note and the test-results file it reads. Offline: the judge's
answers are replayed from fixtures. Without claim-seal installed, the release-note tests are skipped."""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT

FIX = ROOT / "tests" / "fixtures" / "release-note"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "release" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


try:
    import claim_seal  # noqa: F401
    HAVE_SEAL = True
except ImportError:
    HAVE_SEAL = False


class ChangelogTests(unittest.TestCase):
    def setUp(self):
        self.rn = load("release_note")

    def test_section_is_this_version_only(self):
        text = self.rn.changelog_section((FIX / "CHANGELOG.md").read_text(encoding="utf-8"), "9.9.0")
        self.assertIn("A container image that runs as an unprivileged user.", text)
        self.assertIn("Fixed:", text)
        self.assertNotIn("example.org", text)

    def test_missing_section_is_refused(self):
        with self.assertRaises(self.rn.NoteError):
            self.rn.changelog_section("# Changelog\n\n## [1.0.0]\n\n- x\n", "2.0.0")

    def test_repository_changelog_has_unreleased_0_2_0_and_0_1_0(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertTrue(self.rn.changelog_section(text, "0.1.0"))
        self.assertTrue(self.rn.changelog_section(text, "0.2.0"))
        self.assertIn("\n## [Unreleased]\n", text)

    def test_the_package_version_has_a_changelog_section(self):
        import re
        version = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
                            re.M).group(1)
        base = re.match(r"\d+\.\d+\.\d+", version).group(0)  # a release candidate (0.2.0rc1) reads 0.2.0
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertTrue(self.rn.changelog_section(text, base), base)

    def test_tests_text_says_counts_and_skip_reasons(self):
        r = json.loads((FIX / "test-results.json").read_text(encoding="utf-8"))
        r = dict(r, skipped=1, passed=11, skips=[{"test": "t", "reason": "pending phase P1"}])
        text = self.rn.tests_text([r])
        self.assertIn("ran 12 tests: 11 passed, 0 failed, 0 had errors and 1 were skipped", text)
        self.assertIn("pending phase P1", text)


@unittest.skipUnless(HAVE_SEAL, "claim-seal is not installed (pip install .)")
class ReleaseNoteTests(unittest.TestCase):
    def run_note(self, answers: str, out: Path, tests: str = "test-results.json"):
        rn = load("release_note")
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = rn.main(["--version", "9.9.0", "--draft", str(FIX / "draft.json"), "--tests", str(FIX / tests),
                            "--changelog", str(FIX / "CHANGELOG.md"), "--judge", f"replay:{FIX / answers}",
                            "--out-dir", str(out)])
        return code, err.getvalue()

    def test_all_supported_writes_a_sealed_note(self):
        import claim_seal
        with tempfile.TemporaryDirectory() as tmp:
            code, err = self.run_note("answers-supported.json", Path(tmp))
            self.assertEqual(code, 0, err)
            note = (Path(tmp) / "release-note.md").read_text(encoding="utf-8")
            check = json.loads((Path(tmp) / "release-note-check.json").read_text(encoding="utf-8"))
        self.assertTrue(claim_seal.verify_seal(check["claim_evidence"]))
        seal = check["claim_evidence"]["verification"]["seal"]["value"]
        self.assertIn(seal, note)
        self.assertIn("# Lensmith Composer 9.9.0", note)
        self.assertIn("all 2 are supported", note)
        self.assertIn("REPLAYED", note)  # a replayed check never passes itself off as a fresh one
        self.assertIn("no telemetry", note)

    def test_one_unsupported_line_stops_the_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, err = self.run_note("answers-one-unsupported.json", Path(tmp))
            self.assertEqual(code, 1)
            self.assertIn("line 2 is unsupported", err)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_unknown_source_title_stops_the_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = json.loads((FIX / "draft.json").read_text(encoding="utf-8"))
            draft["items"][0]["sources"][0]["ref"] = "Roadmap for an imagined future"
            path = Path(tmp) / "draft.json"
            path.write_text(json.dumps(draft), encoding="utf-8")
            rn = load("release_note")
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                code = rn.main(["--version", "9.9.0", "--draft", str(path), "--tests", str(FIX / "test-results.json"),
                                "--changelog", str(FIX / "CHANGELOG.md"),
                                "--judge", f"replay:{FIX / 'answers-supported.json'}", "--out-dir", str(Path(tmp) / "o")])
            self.assertEqual(code, 1)
            self.assertIn("line 1", err.getvalue())
            self.assertFalse((Path(tmp) / "o").exists())

    def test_red_test_results_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            red = json.loads((FIX / "test-results.json").read_text(encoding="utf-8"))
            red.update(ok=False, failed=1, passed=11)
            path = Path(tmp) / "red.json"
            path.write_text(json.dumps(red), encoding="utf-8")
            rn = load("release_note")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = rn.main(["--version", "9.9.0", "--draft", str(FIX / "draft.json"), "--tests", str(path),
                                "--changelog", str(FIX / "CHANGELOG.md"),
                                "--judge", f"replay:{FIX / 'answers-supported.json'}", "--out-dir", str(Path(tmp) / "o")])
            self.assertEqual(code, 2)


class BuildScriptTests(unittest.TestCase):
    def test_tag_must_match_pyproject_version(self):
        build = load("build")
        version = build.project_version()
        with self.assertRaises(SystemExit) as cm:
            build.main(["--out", "unused", "--tag", f"v{version}.9"])
        self.assertIn("does not match", str(cm.exception))

    def test_optional_narration_parts_are_listed_with_licences(self):
        doc = json.loads((ROOT / "scripts" / "release" / "optional-components.json").read_text(encoding="utf-8"))
        names = {c["name"]: c for c in doc["components"]}
        for name in ("kokoro-onnx", "espeakng-loader", "espeak-ng", "onnxruntime", "soundfile",
                     "kokoro-v1.0.onnx", "voices-v1.0.bin"):
            self.assertIn(name, names)
            self.assertTrue(names[name]["licenses"], name)
        self.assertEqual(names["espeak-ng"]["licenses"][0]["license"]["id"], "GPL-3.0-or-later")

    def test_sbom_rows_are_marked_excluded(self):
        build = load("build")
        with tempfile.TemporaryDirectory() as tmp:
            sbom = Path(tmp) / "x.cdx.json"
            sbom.write_text(json.dumps({"bomFormat": "CycloneDX", "components": []}), encoding="utf-8")
            added = build.add_optional(sbom)
            rows = json.loads(sbom.read_text(encoding="utf-8"))["components"]
        self.assertEqual(added, len(rows))
        self.assertTrue(all(r["scope"] == "excluded" and r["properties"] for r in rows))

    def test_release_tools_are_hash_locked(self):
        text = (ROOT / "scripts" / "release" / "release-tools.txt").read_text(encoding="utf-8")
        pins = [ln for ln in text.splitlines() if ln and not ln[0].isspace() and not ln.startswith("#")]
        self.assertTrue(pins)
        for ln in pins:
            self.assertRegex(ln, r"^[A-Za-z0-9_.-]+==[^ ]+ \\$", ln)
        self.assertIn("--hash=sha256:", text)


if __name__ == "__main__":
    unittest.main()
