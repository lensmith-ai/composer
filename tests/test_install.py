"""Setup: guards before any write, an answers-file install, an interactive install on a real terminal (pty, and
an expect script when `expect` is installed), the key stored 0600 and never shown, and setup.sh's own guards."""
import faulthandler
import json
import os
import pty
import select
import signal
import shutil
import socket
import stat
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT
from install_helpers import FAKE_KEY, fake_home, snapshot

from composer import answers, home as H, installer, settings as S

POSIX = os.name == "posix"


def run_setup(home_dir, answers_file=None, **kw):
    kw.setdefault("assume_yes", answers_file is None)
    return installer.run(home=home_dir, data=None, answers_file=answers_file, reconfigure=kw.pop("reconfigure", []),
                         data_only=False, out=lambda *_: None, interactive=False, **kw)


class GuardBeforeWriteTests(unittest.TestCase):
    def assert_refused_and_untouched(self, home, target, answers_text=None, exc=(H.HomeError, installer.SetupError,
                                                                               answers.AnswersError)):
        before = snapshot(home)
        path = None
        if answers_text is not None:
            path = home.parent / "answers.toml"
            path.write_text(answers_text, encoding="utf-8")
            before = snapshot(home)
        with self.assertRaises(exc):
            run_setup(target, str(path) if path else None)
        self.assertEqual(snapshot(home), before)

    def test_a_folder_with_other_files_is_refused_with_nothing_written(self):
        with fake_home() as home:
            target = home / "stuff"
            target.mkdir()
            (target / "notes.txt").write_text("mine", encoding="utf-8")
            self.assert_refused_and_untouched(home, target)

    def test_unsafe_targets_are_refused_with_nothing_written(self):
        with fake_home() as home:
            elsewhere = home / "elsewhere"
            elsewhere.mkdir()
            link = home / "link"
            link.symlink_to(elsewhere)
            afile = home / "afile"
            afile.write_text("x", encoding="utf-8")
            for target in (home, home.parent, link, afile, home / "missing-parent" / "app"):
                with self.subTest(target=target):
                    self.assert_refused_and_untouched(home, target)

    def test_a_marker_that_is_not_ours_is_refused(self):
        with fake_home() as home:
            target = home / ".lensmith-composer"
            target.mkdir()
            (target / H.MARKER).write_text("something else\n", encoding="utf-8")
            self.assert_refused_and_untouched(home, target)

    def test_bad_answers_are_refused_before_the_folder_exists(self):
        with fake_home() as home:
            target = home / ".lensmith-composer"
            for text in ("[provider]\nkey = \"a-pasted-key\"\n",          # a key in a file is refused
                         "[provider]\nkey_from_env = \"ANTHROPIC_API_KEY\"\n",  # names a variable that is not set
                         "[nonsense]\nx = 1\n",
                         "[provider]\nkind = \"anthropic\"\nkind = \"openai\"\n",
                         "[schedule]\nenabled = maybe\n"):
                with self.subTest(text=text):
                    self.assert_refused_and_untouched(home, target, answers_text=text)
                    self.assertFalse(target.exists())

    def test_a_port_in_use_is_refused_before_any_write(self):
        with fake_home() as home, socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen(1)
            port = busy.getsockname()[1]
            target = home / ".lensmith-composer"
            self.assert_refused_and_untouched(home, target, answers_text=f"[server]\nport = {port}\n")
            self.assertFalse(target.exists())


class AnswersFileSetupTests(unittest.TestCase):
    ANSWERS = """
# a full answers file
[provider]
kind = "anthropic"
model = "claude-sonnet-5-5"
key_from_env = "ANTHROPIC_API_KEY"

[sources]
hacker_news = true

[narration]
enabled = false

[schedule]
enabled = true
time = "06:30"
timezone = "UTC"
lens = "what a small team should try next"

[server]
port = {port}
"""

    def setup_once(self, home):
        port = installer.next_free_port(18765)
        path = home.parent / "answers.toml"
        path.write_text(self.ANSWERS.replace("{port}", str(port)), encoding="utf-8")
        target = home / ".lensmith-composer"
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": FAKE_KEY}):
            self.assertEqual(run_setup(target, str(path)), 0)
        return target, port, path

    def test_everything_lands_in_the_app_folder_with_the_key_private(self):
        with fake_home() as home:
            outside_before = snapshot(home, skip=home / ".lensmith-composer")
            target, port, _ = self.setup_once(home)
            self.assertEqual(snapshot(home, skip=home / ".lensmith-composer"), outside_before)
            data = target / "data"
            cfg = S.load(data)
            self.assertEqual(cfg["provider"], {"kind": "anthropic", "model": "claude-sonnet-5-5", "base_url": "",
                                               "key": "stored", "key_env": "ANTHROPIC_API_KEY"})
            self.assertEqual((cfg["schedule"]["enabled"], cfg["schedule"]["time"], cfg["schedule"]["timezone"]),
                             (True, "06:30", "UTC"))
            self.assertEqual(cfg["server"]["port"], port)
            self.assertFalse(cfg["narration"]["enabled"])
            if POSIX:
                self.assertEqual(stat.S_IMODE(os.stat(data).st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(os.stat(S.secrets_path(data)).st_mode), 0o600)
            self.assertEqual(S.read_secrets(data), {"ANTHROPIC_API_KEY": FAKE_KEY})
            for path in target.rglob("*"):
                if path.is_file() and path.name != "secrets.env":
                    self.assertNotIn(FAKE_KEY.encode(), path.read_bytes(), path)
            sources = json.loads(S.sources_file(data).read_text(encoding="utf-8"))
            self.assertEqual([s["id"] for s in sources["sources"]], ["hn"])
            doc = H.load_manifest(target)
            kinds = {e["path"]: e["kind"] for e in doc["entries"]}
            self.assertEqual(kinds["data"], "user-data")
            self.assertEqual(kinds["bin"], "created")
            self.assertEqual(H.check_manifest(target, doc, data), [])
            launcher = (target / "bin" / "composer").read_text(encoding="utf-8")
            self.assertIn("PIP_REQUIRE_VIRTUALENV=1", launcher)
            self.assertNotIn(FAKE_KEY, launcher)

    def test_running_setup_again_keeps_the_key_sources_and_schedule(self):
        with fake_home() as home:
            target, port, path = self.setup_once(home)
            data = target / "data"
            before = (S.secrets_path(data).read_bytes(), S.sources_file(data).read_bytes(), S.load(data))
            other = home.parent / "other.toml"
            other.write_text("[provider]\nkind = \"openai\"\nbase_url = \"https://api.openai.com/v1\"\n"
                             "model = \"m\"\nkey = \"env\"\n[schedule]\nenabled = false\n", encoding="utf-8")
            self.assertEqual(run_setup(target, str(other)), 0)
            self.assertEqual((S.secrets_path(data).read_bytes(), S.sources_file(data).read_bytes(), S.load(data)),
                             before)
            # one part, on request
            self.assertEqual(run_setup(target, str(other), reconfigure=["schedule"]), 0)
            self.assertFalse(S.load(data)["schedule"]["enabled"])
            self.assertEqual(S.load(data)["provider"]["kind"], "anthropic")

    def test_toml_subset(self):
        doc = answers.parse_toml('[a]\nx = "q # not a comment" # a comment\ny = ["one", "two"]\nz = 3\nw = true\n')
        self.assertEqual(doc, {"a": {"x": "q # not a comment", "y": ["one", "two"], "z": 3, "w": True}})
        with self.assertRaises(answers.AnswersError):
            answers.parse_toml("x = 1\n")


@unittest.skipUnless(POSIX, "a terminal session needs a POSIX pty")
class InteractiveSetupTests(unittest.TestCase):
    """The real `composer setup` on a terminal: questions one at a time, the key read without echo."""

    STEPS = [("choose 1-3 [1]:", "1"), ("choose 1-4 [1]:", ""), ("key:", FAKE_KEY),
             ("Check claims with the same model? [Y/n]:", ""),
             ("Add Hacker News as a source too? [y/N]:", "n"),
             ("Add your own feed? Paste its address, or press Enter to skip []:", ""),
             ("Install the optional article parser? [y/N]:", "n"),
             ("Add narration? [y/N]:", "n"),
             ("Compose a daily brief automatically (while Composer runs)? [y/N]:", "y"),
             ("At what time (24-hour HH:MM) [07:00]:", "07:15"), ("In which time zone: local or UTC [local]:", "UTC"),
             ("Through which lens [", ""), ("Port on this computer [", "")]

    def test_interactive_setup_on_a_pty(self):
        # a hang here (seen on a macOS runner) must show where it is and end the run, not hold a job to its time limit
        faulthandler.dump_traceback_later(150, exit=True)
        self.addCleanup(faulthandler.cancel_dump_traceback_later)
        with fake_home() as home:
            target = home / ".lensmith-composer"
            pid, fd = pty.fork()
            if pid == 0:  # child: the real command, on the terminal
                os.chdir(ROOT)
                os.execv(sys.executable, [sys.executable, "-m", "composer", "setup", "--home", str(target)])
            transcript = b""
            try:
                for prompt, reply in self.STEPS:
                    transcript = self._wait_for(fd, prompt.encode(), transcript)
                    os.write(fd, reply.encode() + b"\n")
                transcript = self._wait_for(fd, b"Check it:", transcript)
                transcript = self._drain(fd, transcript)  # a Mac's pty holds about 1 KB: a child that still has lines to print blocks until they are read
            except BaseException:
                os.kill(pid, signal.SIGKILL)  # a child still waiting at a prompt would hang waitpid below, and the job with it
                raise
            finally:
                _, status = os.waitpid(pid, 0)
                os.close(fd)
            self.assertEqual(os.waitstatus_to_exitcode(status), 0, transcript[-2000:])
            self.assertNotIn(FAKE_KEY.encode(), transcript)  # never echoed, never printed
            data = target / "data"
            self.assertEqual(S.read_secrets(data), {"ANTHROPIC_API_KEY": FAKE_KEY})
            cfg = S.load(data)
            self.assertEqual((cfg["schedule"]["enabled"], cfg["schedule"]["time"], cfg["schedule"]["timezone"]),
                             (True, "07:15", "UTC"))

    @staticmethod
    def _drain(fd, seen, timeout=30):
        """Read what the child still prints until it closes the terminal (end of file or an I/O error)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([fd], [], [], 0.5)
            if ready:
                try:
                    chunk = os.read(fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                seen += chunk
        return seen

    @staticmethod
    def _wait_for(fd, needle, seen, timeout=30):
        deadline = time.monotonic() + timeout
        start = len(seen)
        while needle not in seen[start - 200 if start > 200 else 0:]:
            if time.monotonic() > deadline:
                raise AssertionError(f"no {needle!r} in {seen[-800:]!r}")
            ready, _, _ = select.select([fd], [], [], 0.5)
            if ready:
                try:
                    seen += os.read(fd, 4096)
                except OSError:
                    break
        return seen

    @unittest.skipUnless(shutil.which("expect"), "expect is not installed")
    def test_the_expect_script(self):
        with fake_home() as home:
            target = home / ".lensmith-composer"
            run = subprocess.run(["expect", str(ROOT / "tests" / "setup" / "interactive.exp"), sys.executable,
                                  str(target), FAKE_KEY], capture_output=True, text=True, timeout=120, cwd=ROOT)
            self.assertEqual(run.returncode, 0, run.stdout[-2000:] + run.stderr[-1000:])
            self.assertNotIn(FAKE_KEY, run.stdout.replace(f"send_key {FAKE_KEY}", ""))
            self.assertEqual(S.read_secrets(target / "data"), {"ANTHROPIC_API_KEY": FAKE_KEY})


@unittest.skipUnless(POSIX and shutil.which("sh"), "setup.sh is a POSIX shell script")
class SetupShGuardTests(unittest.TestCase):
    def run_sh(self, *args, env=None):
        return subprocess.run(["sh", str(ROOT / "setup.sh"), *args], capture_output=True, text=True, timeout=60,
                              env=env or os.environ.copy())

    def test_refuses_before_writing(self):
        with fake_home() as home:
            foreign = home / "foreign"
            foreign.mkdir()
            (foreign / "keep.txt").write_text("mine", encoding="utf-8")
            link = home / "link"
            link.symlink_to(foreign)
            before = snapshot(home)
            for target in (str(foreign), str(link), str(home), "relative/path", "/"):
                with self.subTest(target=target):
                    run = self.run_sh("--home", target, "--yes")
                    self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
                    self.assertIn("setup.sh:", run.stderr)
                    self.assertEqual(snapshot(home), before)

    def test_help(self):
        run = self.run_sh("--help")
        self.assertEqual(run.returncode, 0)
        self.assertIn("never does", run.stdout)

    @unittest.skipUnless(os.environ.get("COMPOSER_SETUP_E2E") == "1", "full setup.sh install: set COMPOSER_SETUP_E2E=1 "
                         "(it installs this folder and claim-seal into a private environment; needs the network)")
    def test_full_install_and_uninstall_leave_the_rest_unchanged(self):
        with fake_home() as home:
            answers_file = home.parent / "answers.toml"
            answers_file.write_text("[provider]\nkind = \"none\"\n[narration]\nenabled = false\n", encoding="utf-8")
            before = snapshot(home)
            run = self.run_sh("--answers", str(answers_file))
            self.assertEqual(run.returncode, 0, run.stdout[-2000:] + run.stderr[-2000:])
            target = home / ".lensmith-composer"
            self.assertEqual(snapshot(home, skip=target), {k: v for k, v in before.items() if k != "."})
            doctor = subprocess.run([str(target / "bin" / "composer"), "doctor", "--parity"], capture_output=True,
                                    text=True, timeout=120)
            self.assertEqual(doctor.returncode, 0, doctor.stdout[-2000:])
            un = subprocess.run([str(target / "bin" / "composer"), "uninstall", "--delete-data", "--yes"],
                                capture_output=True, text=True, timeout=120)
            self.assertEqual(un.returncode, 0, un.stdout + un.stderr)
            self.assertFalse(target.exists())
            after = snapshot(home)
            self.assertEqual({k: v[:2] for k, v in after.items()}, {k: v[:2] for k, v in before.items()})


if __name__ == "__main__":
    unittest.main()
