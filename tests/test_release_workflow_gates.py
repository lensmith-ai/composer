"""The release workflow publishes nothing a person could take for the release before every gate is green: the image
job pushes only a candidate tag, and the version tag is put on the image only in a job that needs every gate.
(A release-note failure used to leave a pushed <version> image tag: the image job needed only the test job.)"""
import re
import unittest

from helpers import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
GATES = {"test", "build", "release-note", "image"}


def jobs(text: str) -> dict:
    """{job name: its block of text}, from the two-space-indented keys under `jobs:`."""
    body = text.split("\njobs:\n", 1)[1]
    out, name = {}, None
    for line in body.splitlines():
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if m:
            name = m.group(1)
            out[name] = ""
        elif name:
            out[name] += line + "\n"
    return out


def needs(block: str) -> set:
    m = re.search(r"(?m)^    needs:\s*(.+)$", block)
    if not m:
        return set()
    raw = m.group(1).strip()
    return {x.strip() for x in raw.strip("[]").split(",") if x.strip()}


def closure(graph: dict, job: str) -> set:
    seen, todo = set(), [job]
    while todo:
        for dep in graph[todo.pop()]:
            if dep not in seen:
                seen.add(dep)
                todo.append(dep)
    return seen


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.jobs = jobs(WORKFLOW.read_text(encoding="utf-8"))
        self.graph = {name: needs(block) for name, block in self.jobs.items()}

    def test_every_push_and_every_version_tag_waits_for_every_gate(self):
        for name, block in self.jobs.items():
            pushes = "push: true" in block or "imagetools create" in block or "gh release create" in block
            if not pushes:
                continue
            with self.subTest(job=name):
                upstream = closure(self.graph, name)
                if "imagetools create" in block or "gh release create" in block:
                    self.assertLessEqual(GATES, upstream, f"{name} needs {sorted(upstream)}")
                else:  # the image push itself: after the package and the release note are good
                    self.assertLessEqual({"test", "build", "release-note"}, upstream, f"{name} needs {sorted(upstream)}")

    def test_the_image_job_pushes_only_a_candidate_tag(self):
        image = self.jobs["image"]
        self.assertIn("push: true", image)
        tags = re.findall(r"(?m)^\s+tags:\s*(.+)$", image)
        self.assertEqual(len(tags), 1)
        self.assertIn("steps.name.outputs.candidate", tags[0])
        self.assertNotIn("outputs.version }}", tags[0])
        self.assertIn('candidate=candidate-${COMMIT}', image)  # the tag's commit, not the run's (a manual run is on main)

    def test_only_the_promote_job_tags_the_version_and_it_needs_the_attested_image(self):
        tagging = [n for n, b in self.jobs.items() if "imagetools create" in b]
        self.assertEqual(tagging, ["promote"])
        promote = self.jobs["promote"]
        self.assertLessEqual(GATES, self.graph["promote"])
        self.assertIn('"$REF@$DIGEST"', promote)  # the attested digest, not a rebuild
        image = self.jobs["image"]
        # the image's attestations come before its job ends, so promote (which needs the job) comes after them
        self.assertIn("attest-build-provenance", image)
        self.assertIn("attest-sbom", image)

    def test_the_release_itself_is_last(self):
        self.assertLessEqual(GATES | {"promote", "installer"}, closure(self.graph, "publish"))

    def test_every_job_waits_for_the_signed_tag_check(self):
        for name in self.jobs:
            if name == "verify-tag":
                continue
            with self.subTest(job=name):
                self.assertIn("verify-tag", closure(self.graph, name) | self.graph[name])

    def test_the_tag_check_verifies_the_signature_against_the_key_on_main(self):
        block = self.jobs["verify-tag"]
        self.assertIn('git cat-file -t "refs/tags/$TAG"', block)
        self.assertIn("git show refs/remotes/origin/main:.github/allowed_signers", block)
        self.assertIn('tag -v "$TAG"', block)
        self.assertIn("is not on main", block)
        self.assertIn("github.ref == 'refs/heads/main'", block)  # a manual run starts from main

    def test_every_checkout_outside_verify_tag_is_the_verified_commit(self):
        # A step is a "- " item; its text runs to the next one. Comments are dropped first.
        for name, block in self.jobs.items():
            code = "\n".join(l for l in block.splitlines() if not l.lstrip().startswith("#"))
            for step in re.split(r"(?m)^      - ", code):
                if "actions/checkout@" not in step:
                    continue
                with self.subTest(job=name):
                    want = "refs/tags/${{ steps.tag.outputs.name }}" if name == "verify-tag" else "${{ needs.verify-tag.outputs.commit }}"
                    self.assertRegex(step, r"(?m)^\s+ref: " + re.escape(want) + r"\s*$")

    def test_a_manual_run_never_reads_its_own_ref_name_outside_the_tag_check(self):
        for name, block in self.jobs.items():
            if name != "verify-tag":
                with self.subTest(job=name):
                    self.assertNotIn("GITHUB_REF_NAME", block)
                    self.assertNotIn("github.ref_name", block)
        self.assertIn("workflow_dispatch", WORKFLOW.read_text(encoding="utf-8"))

    def test_write_permissions_are_held_only_where_they_are_used(self):
        allowed = {"contents": {"publish", "installer-to-main"}, "packages": {"image", "promote"},
                   "id-token": {"image", "publish"}, "attestations": {"image", "publish"}}
        for name, block in self.jobs.items():
            for scope in re.findall(r"(?m)^      ([\w-]+): write\b", block):
                with self.subTest(job=name, scope=scope):
                    self.assertIn(name, allowed.get(scope, set()), f"{name} holds {scope}: write")

    def test_attestations_name_the_files_they_belong_to(self):
        publish = self.jobs["publish"]
        sbom = re.search(r"attest-sbom@[^\n]*\n\s+with:\n\s+subject-path: \|\n((?:\s+release/[^\n]+\n)+)", publish)
        self.assertTrue(sbom, "the SBOM attestation lists its subjects")
        subjects = [s.strip() for s in sbom.group(1).splitlines()]
        self.assertEqual(len(subjects), 2)
        self.assertTrue(all("*" not in s for s in subjects), subjects)
        self.assertTrue(any(s.endswith("-py3-none-any.whl") and "lensmith_composer" in s for s in subjects))
        self.assertTrue(any(s.endswith(".tar.gz") and "lensmith_composer" in s for s in subjects))
        prov = re.search(r"attest-build-provenance@[^\n]*\n\s+with:\n\s+subject-path: \|\n((?:\s+release/[^\n]+\n)+)", publish)
        self.assertTrue(prov, "the provenance attestation lists its subjects")
        text = prov.group(1)
        for copied in ("certifi", "setuptools", "claim-seal-"):  # upstream copies, not built here
            self.assertNotIn(copied, text)
        self.assertNotIn("release/*\n", text)

    def test_the_image_gets_its_release_tag_only_after_the_tag_is_rechecked(self):
        promote = self.jobs["promote"]
        self.assertIn("git/ref/tags/$TAG", promote)
        self.assertLess(promote.index("git/ref/tags/$TAG"), promote.index("imagetools create"))

    def test_the_installer_is_on_main_only_after_the_release_is_public(self):
        self.assertIn("publish", self.graph["installer-to-main"])
        self.assertNotIn("installer-to-main", closure(self.graph, "publish"))
        self.assertIn('--draft=false', self.jobs["publish"])  # a draft first, public when every file is attached

    def test_the_signers_file_is_one_ssh_key_for_git(self):
        lines = [l for l in (ROOT / ".github" / "allowed_signers").read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("#")]
        self.assertEqual(len(lines), 1)
        self.assertRegex(lines[0], r'^\* namespaces="git" ssh-ed25519 AAAA[0-9A-Za-z+/]{40,}$')


if __name__ == "__main__":
    unittest.main()
