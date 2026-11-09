"""The release scripts: the claim-sealed release note (sealed once on the maintainer's server, re-verified offline by the
workflow) and the test-results file. Offline: the judge's answers are replayed from fixtures. Without claim-seal installed, the release-note tests are skipped."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
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


@unittest.skipUnless(HAVE_SEAL, "claim-seal is not installed (pip install .)")
class ReleaseNoteTests(unittest.TestCase):
    """seal (the maintainer's one model call, replayed here) and verify (the workflow's offline re-check)."""

    def setUp(self):
        self.rn = load("release_note")
        self.tmp = Path(tempfile.mkdtemp(prefix="composer-note-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.draft = self.tmp / "draft.json"
        self.changelog = self.tmp / "CHANGELOG.md"
        shutil.copy(FIX / "draft.json", self.draft)
        shutil.copy(FIX / "CHANGELOG.md", self.changelog)
        self.sealed = self.tmp / "sealed.json"

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = self.rn.main([str(a) for a in argv])
        return code, out.getvalue(), err.getvalue()

    def seal(self, answers="answers-supported.json"):
        return self.run_main("seal", "--version", "9.9.0", "--draft", self.draft, "--changelog", self.changelog,
                             "--judge", f"replay:{FIX / answers}", "--out", self.sealed)

    def verify(self, *extra, out=None):
        return self.run_main("verify", "--version", "9.9.0", "--draft", self.draft, "--changelog", self.changelog,
                             "--sealed", self.sealed, "--out-dir", out or self.tmp / "note", "--allow-replay", *extra)

    def test_a_sealed_note_verifies_offline_and_writes_the_note(self):
        import claim_seal
        code, out, err = self.seal()
        self.assertEqual(code, 0, err)
        code, out, err = self.verify()
        self.assertEqual(code, 0, err)
        note = (self.tmp / "note" / "release-note.md").read_text(encoding="utf-8")
        check = json.loads((self.tmp / "note" / "release-note-check.json").read_text(encoding="utf-8"))
        self.assertTrue(claim_seal.verify_seal(check["claim_evidence"]))
        self.assertIn(check["claim_evidence"]["verification"]["seal"]["value"], note)
        self.assertIn("# Lensmith Composer 9.9.0", note)
        self.assertIn("all 2 are supported", note)
        self.assertIn("no telemetry", note)

    def test_verify_needs_no_model_and_no_secret(self):
        self.seal()
        env = {k: v for k, v in os.environ.items() if "KEY" not in k and "TOKEN" not in k and "SECRET" not in k}
        run = subprocess.run([sys.executable, str(ROOT / "scripts" / "release" / "release_note.py"), "verify", "--version", "9.9.0",
                              "--draft", str(self.draft), "--changelog", str(self.changelog), "--sealed", str(self.sealed),
                              "--out-dir", str(self.tmp / "n2"), "--allow-replay"], capture_output=True, text=True, env=env,
                             cwd=self.tmp)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_a_replayed_seal_is_refused_unless_a_test_allows_it(self):
        self.seal()
        code, out, err = self.run_main("verify", "--version", "9.9.0", "--draft", self.draft, "--changelog", self.changelog,
                                       "--sealed", self.sealed, "--out-dir", self.tmp / "n3")
        self.assertEqual(code, 1)
        self.assertIn("replayed answers", err)

    def test_an_edited_note_fails(self):
        self.seal()
        d = json.loads(self.draft.read_text(encoding="utf-8"))
        d["items"][0]["insight"] += " (and faster)"
        self.draft.write_text(json.dumps(d), encoding="utf-8")
        code, out, err = self.verify()
        self.assertEqual(code, 1)
        self.assertIn("changed after it was sealed", err)
        self.assertIn("not the lines that were checked", err)
        self.assertFalse((self.tmp / "note").exists())

    def test_an_edited_lede_fails_too(self):
        self.seal()
        d = json.loads(self.draft.read_text(encoding="utf-8"))
        d["lede"] = "Something the check never saw."
        self.draft.write_text(json.dumps(d), encoding="utf-8")
        code, _, err = self.verify()
        self.assertEqual(code, 1)
        self.assertIn("changed after it was sealed", err)

    def test_an_edited_changelog_entry_fails(self):
        self.seal()
        self.changelog.write_text(self.changelog.read_text(encoding="utf-8").replace("unprivileged user", "root user"),
                                  encoding="utf-8")
        code, _, err = self.verify()
        self.assertEqual(code, 1)
        self.assertIn("changelog entry for 9.9.0 changed", err)

    def test_changes_outside_the_checked_entry_do_not_matter(self):
        self.seal()
        self.changelog.write_text(self.changelog.read_text(encoding="utf-8").replace("## [Unreleased]\n", "## [Unreleased]\n\n- Later work.\n"),
                                  encoding="utf-8")
        self.assertEqual(self.verify()[0], 0)

    def test_a_tampered_seal_or_verdict_fails(self):
        self.seal()
        sealed = json.loads(self.sealed.read_text(encoding="utf-8"))
        sealed["result"]["claim_evidence"]["outcomes"][0]["strength"] = 5
        self.sealed.write_text(json.dumps(sealed), encoding="utf-8")
        code, _, err = self.verify()
        self.assertEqual(code, 1)
        self.assertIn("does not recompute", err)
        sealed = json.loads(self.sealed.read_text(encoding="utf-8"))
        sealed["result"]["brief"]["items"][0]["verification"]["verdict"] = "unsupported"
        self.sealed.write_text(json.dumps(sealed), encoding="utf-8")
        code, _, err = self.verify()
        self.assertIn("is unsupported", err)

    def test_the_wrong_version_fails(self):
        self.seal()
        code, _, err = self.run_main("verify", "--version", "9.9.1", "--draft", self.draft, "--changelog", self.changelog,
                                     "--sealed", self.sealed, "--out-dir", self.tmp / "n4", "--allow-replay")
        self.assertNotEqual(code, 0)

    def test_one_unsupported_line_stops_the_sealing(self):
        code, out, err = self.seal("answers-one-unsupported.json")
        self.assertEqual(code, 1)
        self.assertIn("line 2 is unsupported", err)
        self.assertFalse(self.sealed.exists())

    def test_unknown_source_title_stops_the_sealing(self):
        d = json.loads(self.draft.read_text(encoding="utf-8"))
        d["items"][0]["sources"][0]["ref"] = "Roadmap for an imagined future"
        self.draft.write_text(json.dumps(d), encoding="utf-8")
        code, _, err = self.seal()
        self.assertEqual(code, 1)
        self.assertIn("line 1", err)
        self.assertFalse(self.sealed.exists())

    def test_the_committed_note_is_sealed_for_this_changelog(self):
        """The real note for this version: it verifies against the repository's own draft and changelog (the release
        workflow's re-check, here at test time), so an edit to either after sealing fails the suite, not just the release."""
        sealed = ROOT / "release-notes" / "0.2.0.sealed.json"
        self.assertTrue(sealed.is_file(), "release-notes/0.2.0.sealed.json is missing: run scripts/seal-release-note.sh")
        code, _, err = self.run_main("verify", "--version", "0.2.0", "--draft", ROOT / "release-notes" / "0.2.0.json",
                                     "--changelog", ROOT / "CHANGELOG.md", "--sealed", sealed, "--out-dir", self.tmp / "real")
        self.assertEqual(code, 0, err)


class TestResultsCommitTests(unittest.TestCase):
    def test_the_checked_out_commit_wins_over_github_sha(self):
        # on a manual workflow run GITHUB_SHA is main's head, not the commit being released
        import os
        from unittest import mock
        tr = load("test_results")
        with mock.patch.dict(os.environ, {"GITHUB_SHA": "f" * 40}):
            got = tr.commit()
        self.assertNotEqual(got, "f" * 40)
        self.assertRegex(got or "", r"^[0-9a-f]{40}$")


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
