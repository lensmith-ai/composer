"""What Composer prints on a terminal: the app's address on a line of its own (plain, so a macOS Terminal makes it
Cmd+clickable; an OSC 8 link only where the terminal is known to draw one), progress while a brief is composed, and
the release checksum list under either of its names."""
import contextlib
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (temporary folders the app folder checks can trust)
from install_helpers import fake_home

from composer import cli, installer, lifecycle as L, terminal


class FakeTty(io.StringIO):
    def isatty(self):
        return True


class OpenLineTests(unittest.TestCase):
    URL = "http://127.0.0.1:8765/"

    def test_plain_address_on_its_own_line_when_not_a_terminal(self):
        line = terminal.open_line(self.URL, stream=io.StringIO(), environ={"TERM": "xterm", "TERM_PROGRAM": "iTerm.app"})
        self.assertEqual(line, "Open: http://127.0.0.1:8765/")

    def test_macos_terminal_gets_the_plain_address(self):
        env = {"TERM": "xterm-256color", "TERM_PROGRAM": "Apple_Terminal"}
        self.assertEqual(terminal.open_line(self.URL, stream=FakeTty(), environ=env), "Open: " + self.URL)

    def test_known_terminals_get_an_osc8_link_around_the_same_visible_text(self):
        for env in ({"TERM": "xterm", "TERM_PROGRAM": "iTerm.app"}, {"TERM": "xterm", "KITTY_WINDOW_ID": "1"},
                    {"TERM": "xterm", "VTE_VERSION": "6800"}):
            with self.subTest(env=env):
                line = terminal.open_line(self.URL, stream=FakeTty(), environ=env)
                self.assertEqual(line, f"Open: \x1b]8;;{self.URL}\x1b\\{self.URL}\x1b]8;;\x1b\\")
                self.assertTrue(line.startswith("Open: "))

    def test_opt_out_and_dumb_terminals(self):
        for env in ({"TERM": "xterm", "TERM_PROGRAM": "iTerm.app", "COMPOSER_NO_HYPERLINKS": "1"},
                    {"TERM": "dumb", "TERM_PROGRAM": "iTerm.app"}, {"TERM_PROGRAM": "iTerm.app"},
                    {"TERM": "xterm", "VTE_VERSION": "nonsense"}):
            with self.subTest(env=env):
                self.assertEqual(terminal.open_line(self.URL, stream=FakeTty(), environ=env), "Open: " + self.URL)

    def test_which_address_is_printed(self):
        self.assertEqual(terminal.app_url("127.0.0.1", 8765), "http://127.0.0.1:8765/")
        self.assertEqual(terminal.app_url("localhost", 9000), "http://127.0.0.1:9000/")
        self.assertEqual(terminal.app_url("::1", 9000), "http://[::1]:9000/")
        self.assertEqual(terminal.app_url("0.0.0.0", 8765), None)  # a container: the address outside is not known
        self.assertEqual(terminal.app_url("::", 8765), None)
        self.assertEqual(terminal.app_url("192.168.1.5", 8765), "http://192.168.1.5:8765/")
        self.assertEqual(terminal.app_url("fe80::1", 8765), "http://[fe80::1]:8765/")
        self.assertEqual(terminal.app_url("0.0.0.0", 8765, public_origin="https://brief.example.com"),
                         "https://brief.example.com/")


class ProgressTests(unittest.TestCase):
    def lines_for(self, events, sources=2):
        got = []
        progress = terminal.ComposeProgress(sources, write=got.append, clock=lambda: (2026, 11, 7, 10, 31, 5, 0, 0, 0))
        for kind, text in events:
            progress(kind, text)
        return got

    def test_numbered_steps_and_source_lines(self):
        got = self.lines_for([("run.started", "compose started · 2 sources · lens"),
                              ("source.started", "reading Blog A"), ("source.done", "Blog A · 5 items (ok)"),
                              ("lens.started", "writing under the lens"),
                              ("claim.verifying", "checking each claim against the articles it cites"),
                              ("claim.verified", "checked · 3 supported")])
        self.assertEqual(got[0], "[10:31:05] Step 1 of 4: reading 2 sources")
        self.assertIn("  reading Blog A", got)
        self.assertIn("  Blog A · 5 items (ok)", got)
        self.assertTrue(got[3].startswith("[10:31:05] Step 2 of 4: writing the brief"))
        self.assertEqual(got[4], "[10:31:05] Step 3 of 4: checking each claim against the articles it cites")
        self.assertEqual(got[5], "[10:31:05] Step 4 of 4: done · 3 supported")

    def test_with_progress_prints_and_still_calls_the_callers_log_and_reraises_a_failure(self):
        got, seen = [], []

        def compose(**kw):
            kw["log"]("run.started", "x")
            return {"ok": True}
        out = terminal.with_progress(compose, write=got.append)(sources=[1, 2, 3], log=lambda k, t: seen.append(k))
        self.assertEqual(out, {"ok": True})
        self.assertIn("reading 3 sources", got[0])
        self.assertEqual(seen, ["run.started"])

        def failing(**kw):
            raise RuntimeError("no source gave anything")
        got.clear()
        with self.assertRaises(RuntimeError):
            terminal.with_progress(failing, write=got.append)(sources=[1])
        self.assertIn("The brief could not be made: no source gave anything", got[-1])


class ProgressSafetyTests(unittest.TestCase):
    def test_control_bytes_in_a_name_or_an_error_never_reach_the_terminal(self):
        got = []
        progress = terminal.ComposeProgress(1, write=got.append)
        progress("source.done", "Evil\x1b]0;pwned\x07 blog\x1b[2J \u009b31m")
        progress.failed(RuntimeError("bad \x1b[2J" + "x" * 1000))
        for line in got:
            self.assertNotRegex(line, r"[\x00-\x1f\x7f-\x9f]")
        self.assertLess(len(got[1]), 400)

    def test_text_direction_overrides_in_a_name_cannot_reorder_a_progress_line(self):
        got = []
        progress = terminal.ComposeProgress(1, write=got.append)
        progress("source.done", "Blog \u202etxet\u202c and \u2066x\u2069")
        for line in got:
            self.assertNotRegex(line, "[\u202a-\u202e\u2066-\u2069]")

    def test_a_broken_output_never_changes_the_result_or_the_error(self):
        def broken(_text):
            raise BrokenPipeError("stdout closed")
        ok = terminal.with_progress(lambda **kw: (kw["log"]("run.started", "x"), "done")[1], write=broken)
        self.assertEqual(ok(sources=[1]), "done")

        def failing(**kw):
            raise ValueError("the real reason")
        with self.assertRaisesRegex(ValueError, "the real reason"):
            terminal.with_progress(failing, write=broken)(sources=[1])


class WiringTests(unittest.TestCase):
    """`composer up` and `composer serve` hand their app the progress-printing compose, and say where they start."""

    def started_app(self, *argv):
        captured = {}

        def fake_serve(app, host, port, **kw):
            captured["app"] = app

        def fake_compose(**kw):
            kw["log"]("run.started", "compose started")
            return {"edition": {}}
        out = io.StringIO()
        with mock.patch("composer.server.serve", fake_serve), mock.patch("composer.pipeline.compose", fake_compose), \
                mock.patch("composer.scheduler.Scheduler.start", return_value=None), contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(list(argv)), 0)
            captured["app"].compose(sources=[1, 2], log=None)
        return out.getvalue()

    def test_up_prints_progress_for_a_brief_started_from_the_page(self):
        with fake_home() as home:
            target = home / ".lensmith-composer"
            installer.run(home=target, data=None, answers_file=None, assume_yes=True, reconfigure=[], data_only=False,
                          out=lambda *_: None, interactive=False)
            text = self.started_app("up", "--home", str(target), "--port", "18999")
        self.assertIn("Starting Composer", text)
        self.assertIn("Step 1 of 4: reading 2 sources", text)

    def test_serve_prints_progress_too(self):
        with fake_home() as home:
            text = self.started_app("serve", "--out", str(home / "briefs"), "--port", "18998")
        self.assertIn("Step 1 of 4: reading 2 sources", text)


class ChecksumListNameTests(unittest.TestCase):
    def release(self, folder: Path) -> tuple[Path, str]:
        wheel = folder / "lensmith_composer-9.9.9-py3-none-any.whl"
        wheel.write_bytes(b"not really a wheel")
        return wheel, hashlib.sha256(wheel.read_bytes()).hexdigest()

    def test_sha256sums_txt_beside_the_wheel_is_read_with_a_note(self):
        with tempfile.TemporaryDirectory() as d:
            wheel, digest = self.release(Path(d))
            (Path(d) / "SHA256SUMS.txt").write_text(f"{'0' * 64}  other.file\n{digest}  {wheel.name}\n", encoding="utf-8")
            notes = []
            self.assertEqual(L.verify_file(wheel, None, log=notes.append), digest)
            self.assertEqual(len(notes), 1)
            self.assertIn("SHA256SUMS.txt", notes[0])

    def test_the_txt_is_not_a_second_chance_when_the_plain_list_does_not_name_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            wheel, digest = self.release(Path(d))
            (Path(d) / "SHA256SUMS").write_text(f"{'0' * 64}  other.file\n", encoding="utf-8")
            (Path(d) / "SHA256SUMS.txt").write_text(f"{digest}  {wheel.name}\n", encoding="utf-8")
            with self.assertRaisesRegex(L.LifecycleError, "give the release file's SHA-256"):
                L.verify_file(wheel, None)

    def test_plain_name_wins_and_says_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            wheel, digest = self.release(Path(d))
            (Path(d) / "SHA256SUMS").write_text(f"{digest} *{wheel.name}\n", encoding="utf-8")
            (Path(d) / "SHA256SUMS.txt").write_text(f"{'1' * 64}  {wheel.name}\n", encoding="utf-8")
            notes = []
            self.assertEqual(L.verify_file(wheel, None, log=notes.append), digest)
            self.assertEqual(notes, [])

    def test_a_wrong_sum_in_the_txt_still_refuses_and_none_at_all_names_both(self):
        with tempfile.TemporaryDirectory() as d:
            wheel, digest = self.release(Path(d))
            with self.assertRaisesRegex(L.LifecycleError, r"SHA256SUMS \(or SHA256SUMS\.txt\)"):
                L.verify_file(wheel, None)
            (Path(d) / "SHA256SUMS.txt").write_text(f"{'2' * 64}  {wheel.name}\n", encoding="utf-8")
            with self.assertRaisesRegex(L.LifecycleError, "does not match"):
                L.verify_file(wheel, None)


if __name__ == "__main__":
    unittest.main()
