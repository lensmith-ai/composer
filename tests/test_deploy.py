"""The always-on files and the workflows, read as text (no Docker, no YAML library needed).

What these tests hold in place: the app publishes no port and runs read-only as an unprivileged user; Caddy asks for
the login on every path and never forwards it; every base image is pinned by digest and every action by commit;
the model key is never a container environment variable; narration is never in the default image.
The live proof (build, compose up, HTTPS through Caddy, backup and restore) is tests/deploy/proof.sh; it runs in
the nightly workflow, and here only when COMPOSER_DOCKER_PROOF=1 is set.
"""
import os
import re
import shutil
import subprocess
import sys
import unittest

from helpers import ROOT

from composer import cli


def compose_services() -> dict:
    """{service name: its block of compose.yaml as text}."""
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    body = text.split("\nservices:\n", 1)[1].split("\nnetworks:\n", 1)[0]
    out, name = {}, None
    for line in body.splitlines():
        m = re.match(r"^  ([a-z][\w-]*):\s*$", line)
        if m:
            name = m.group(1)
            out[name] = ""
        elif name:
            out[name] += line + "\n"
    return out


def workflows() -> dict:
    d = ROOT / ".github" / "workflows"
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(d.glob("*.yml"))}


class ComposeTests(unittest.TestCase):
    def setUp(self):
        self.s = compose_services()

    def test_two_services(self):
        self.assertEqual(set(self.s), {"composer", "caddy"})

    def test_only_caddy_publishes_ports(self):
        self.assertNotRegex(self.s["composer"], r"(?m)^    ports:")
        self.assertRegex(self.s["caddy"], r"(?m)^    ports:")

    def test_app_is_hardened(self):
        app = self.s["composer"]
        for needle in ("read_only: true", "cap_drop: [ALL]", "no-new-privileges:true", "- composer-data:/data",
                       "restart: unless-stopped"):
            self.assertIn(needle, app)
        self.assertIn('command: ["up", "--host", "0.0.0.0", "--port", "8765"]', app)

    def test_no_model_key_in_container_environment(self):
        text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            self.assertNotIn(name, text)

    def test_trusted_proxy_is_the_front_subnet(self):
        text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        default = "${COMPOSER_FRONT_SUBNET:-172.30.65.0/24}"
        self.assertIn(f"COMPOSER_TRUSTED_PROXY: {default}", text)
        self.assertIn(f"- subnet: {default}", text)

    def test_env_file_is_ignored_by_git_and_docker(self):
        self.assertIn(".env", (ROOT / ".gitignore").read_text(encoding="utf-8").split())
        self.assertIn(".env", (ROOT / ".dockerignore").read_text(encoding="utf-8").split())


class CaddyfileTests(unittest.TestCase):
    def setUp(self):
        text = (ROOT / "Caddyfile").read_text(encoding="utf-8")
        self.conf = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))

    def test_login_on_every_path(self):
        self.assertRegex(self.conf, r"\{\$COMPOSER_DOMAIN\} \{\n\ttls \{\$COMPOSER_TLS\}\n\n\tbasic_auth \{")
        self.assertNotRegex(self.conf, r"(?m)^\s*(handle|route|@)\S*")  # no path that could skip the login

    def test_proxy_to_the_app_without_the_login_header(self):
        self.assertIn("reverse_proxy composer:8765 {\n\t\theader_up -Authorization", self.conf)

    def test_security_headers(self):
        for h in ("Strict-Transport-Security", "X-Content-Type-Options", "-Server"):
            self.assertIn(h, self.conf)


class DockerfileTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    def test_base_pinned_by_digest(self):
        self.assertRegex(self.text, r"(?m)^ARG PYTHON_IMAGE=python:[\w.-]+@sha256:[0-9a-f]{64}$")
        for line in re.findall(r"(?m)^FROM .*$", self.text):
            self.assertRegex(line, r"^FROM (\$\{PYTHON_IMAGE\}|runtime) AS \w+$")

    def test_unprivileged_and_data_volume(self):
        self.assertIn("USER composer", self.text)
        self.assertIn('VOLUME ["/data"]', self.text)

    def test_default_image_is_the_last_stage_and_has_no_narration(self):
        stages = re.findall(r"(?m)^FROM \S+ AS (\w+)$", self.text)
        self.assertEqual(stages[-1], "default")
        install = self.text.split("FROM ${PYTHON_IMAGE} AS runtime", 1)[0]
        for name in ("kokoro", "espeak", "onnxruntime"):
            self.assertNotIn(name, install.lower().split("#")[0])
        narration = self.text.split("FROM runtime AS narration", 1)[1].split("FROM runtime AS default", 1)[0]
        self.assertIn("exit 1", narration)

    def test_compose_caddy_image_pinned_by_digest(self):
        self.assertRegex(compose_services()["caddy"], r"image: caddy:[\w.-]+@sha256:[0-9a-f]{64}\n")


class WorkflowTests(unittest.TestCase):
    def test_every_action_pinned_by_full_commit(self):
        uses = []
        for name, text in workflows().items():
            for m in re.finditer(r"(?m)^\s*-?\s*uses:\s*(\S+)(.*)$", text):
                uses.append((name, m.group(1), m.group(2)))
        self.assertTrue(uses)
        for name, ref, comment in uses:
            self.assertRegex(ref, r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$", f"{name}: {ref}")
            self.assertRegex(comment, r"# v\d", f"{name}: {ref} has no version comment")

    def test_default_permissions_are_read_only_or_none(self):
        for name, text in workflows().items():
            top = text.split("\njobs:\n", 1)[0]
            self.assertRegex(top, r"(?m)^permissions:( \{\}|\n  contents: read)$", name)

    def test_write_permissions_only_in_the_release_workflow(self):
        for name, text in workflows().items():
            if name != "release.yml":
                self.assertNotRegex(text, r":\s*write\b", name)

    def test_ci_matrix_is_the_claimed_platforms_and_pythons(self):
        ci = workflows()["ci.yml"]
        self.assertIn("os: [ubuntu-latest, macos-14, windows-latest]", ci)
        self.assertIn('python: ["3.10", "3.13"]', ci)

    def test_downloaded_tools_are_checked(self):
        for name, text in workflows().items():
            for m in re.finditer(r"curl [^\n]*-o \"\$RUNNER_TEMP/([\w.-]+)\"", text):
                self.assertIn(f'$RUNNER_TEMP/{m.group(1)}" | sha256sum -c -', text, f"{name}: {m.group(1)}")


class PendingTests(unittest.TestCase):
    """Parts of the guide that wait for later phases. Each skips with its reason until that phase lands; then it
    checks that the command the guide and compose.yaml use parses."""

    def commands(self) -> set:
        sub = next(a for a in cli.parser()._actions if a.dest == "command")
        return set(sub.choices)

    def test_composer_up(self):
        if "up" not in self.commands():
            self.skipTest("pending phase P1: `composer up` (the compose.yaml command); the proof uses `serve`")
        # It exists: the exact command compose.yaml runs must parse.
        args = cli.parser().parse_args(["up", "--host", "0.0.0.0", "--port", "8765"])
        self.assertEqual(args.command, "up")

    def test_composer_backup_and_restore(self):
        if not {"backup", "restore"} & self.commands():
            self.skipTest("pending phases P1/P3: `composer backup` / `composer restore` (deploy guide step 9)")
        # They exist: the guide's commands must parse.
        self.assertEqual(cli.parser().parse_args(["backup"]).command, "backup")


@unittest.skipUnless(os.environ.get("COMPOSER_DOCKER_PROOF") == "1" and shutil.which("docker")
                     and sys.platform.startswith("linux"),
                     "live Docker proof: set COMPOSER_DOCKER_PROOF=1 on Linux with Docker (runs nightly in CI)")
class LiveProofTests(unittest.TestCase):
    def test_proof_script(self):
        run = subprocess.run(["bash", str(ROOT / "tests" / "deploy" / "proof.sh")], capture_output=True, text=True,
                             timeout=1800)
        self.assertEqual(run.returncode, 0, run.stdout[-4000:] + run.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
