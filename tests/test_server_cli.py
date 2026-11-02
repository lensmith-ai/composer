import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from composer import cli, server
from composer.registry import BUNDLED, Registry, read_file


def app(compose=None, passphrase=""):
    def ok(**kw):
        return {"edition": {"schema": "composer-edition/v1", "lens": kw["lens"], "cards": [],
                            "sources": [{"label": s.label} for s in kw["sources"]]}}
    return server.App(Registry(read_file(BUNDLED)), lambda: "model", passphrase=passphrase,
                      compose=compose or ok)


class ServerTests(unittest.TestCase):
    def post(self, a, body, headers=None):
        return a.handle_compose(headers or {}, json.dumps(body).encode())

    def test_good_request(self):
        status, obj = self.post(app(), {"sources": ["google-ai"], "lens": "small teams"})
        self.assertEqual(status, 200)
        self.assertEqual(obj["lens"], "small teams")

    def test_bad_requests_are_refused_before_any_fetch(self):
        calls = []
        a = app(compose=lambda **kw: calls.append(kw))
        for body in ({"sources": ["nope"], "lens": "x"}, {"sources": [], "lens": "x"},
                     {"sources": ["google-ai"], "lens": ""}, {"sources": ["google-ai"], "lens": "x" * 301},
                     {"sources": ["google-ai"], "lens": "x", "extra": 1},
                     {"sources": ["google-ai"], "lens": "x", "insights": 99}):
            with self.subTest(body=body):
                self.assertEqual(self.post(a, body)[0], 400)
        self.assertEqual(a.handle_compose({}, b"{not json")[0], 400)
        self.assertEqual(calls, [])

    def test_pass_phrase(self):
        a = app(passphrase="open sesame")
        self.assertEqual(self.post(a, {"sources": ["google-ai"], "lens": "x"})[0], 403)
        self.assertEqual(self.post(a, {"sources": ["google-ai"], "lens": "x"},
                                   {"X-Composer-Pass": "wrong"})[0], 403)
        self.assertEqual(self.post(a, {"sources": ["google-ai"], "lens": "x"},
                                   {"X-Composer-Pass": "open sesame"})[0], 200)

    def test_one_brief_at_a_time(self):
        a = app()
        a.lock.acquire()
        try:
            self.assertEqual(self.post(a, {"sources": ["google-ai"], "lens": "x"})[0], 429)
        finally:
            a.lock.release()

    def test_non_local_bind_needs_a_pass_phrase(self):
        server.check_bind("127.0.0.1", "")
        with self.assertRaises(SystemExit):
            server.check_bind("0.0.0.0", "")
        server.check_bind("0.0.0.0", "set")

    def test_no_key_is_reported_before_any_fetch(self):
        from composer.providers import Anthropic
        calls = []
        a = server.App(Registry(read_file(BUNDLED)), lambda: Anthropic(api_key_env="COMPOSER_TEST_UNSET_KEY"),
                       compose=lambda **kw: calls.append(kw))
        status, obj = self.post(a, {"sources": ["google-ai"], "lens": "x"})
        self.assertEqual(status, 503)
        self.assertEqual(obj["error"],
                         "Composer needs a model key to write a brief. Run ./setup.sh --reconfigure provider.")
        self.assertEqual(calls, [])

    def test_page_starts_with_the_recorded_brief(self):
        html = app().page().decode()
        self.assertIn("Model capability and safety need paired release tracks", html)


class CliTests(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_demo_and_page(self):
        code, out, _ = self.run_cli("demo", "--fast")
        self.assertEqual(code, 0)
        self.assertIn("Replaying a recorded brief", out)
        with tempfile.TemporaryDirectory() as d:
            code, out, _ = self.run_cli("demo", "--page", str(Path(d) / "p.html"))
            self.assertEqual(code, 0)
            self.assertTrue((Path(d) / "p.html").read_text().startswith("<!doctype html>"))

    def test_sources_add_and_list(self):
        with tempfile.TemporaryDirectory() as d:
            f = str(Path(d) / "mine.json")
            code, out, _ = self.run_cli("sources", "add", "--id", "my-feed", "--label", "My feed",
                                        "--url", "https://example.org/feed.xml", "--file", f)
            self.assertEqual(code, 0)
            code, out, _ = self.run_cli("sources", "list", "--sources-file", f)
            self.assertIn("my-feed", out)
            code, _, err = self.run_cli("sources", "add", "--id", "Bad Id", "--label", "x",
                                        "--url", "https://example.org/f", "--file", f)
            self.assertEqual(code, 2)
            code, _, err = self.run_cli("sources", "add", "--id", "idx", "--label", "x", "--kind", "html-index",
                                        "--url", "https://example.org/news/", "--file", f)
            self.assertEqual(code, 2)
            self.assertIn("--allow-host", err)

    def test_compose_without_a_key_fails_cleanly_and_reads_nothing(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}), \
                mock.patch("composer.fetch.urllib.request.OpenerDirector.open",
                           side_effect=AssertionError("network")):
            code, _, err = self.run_cli("compose", "--sources", "google-ai", "--lens", "x",
                                        "--out", str(Path(d) / "b"))
        self.assertEqual(code, 2)
        self.assertIn("Composer needs a model key to write a brief. Run ./setup.sh --reconfigure provider.", err)

    def test_compose_unknown_source(self):
        code, _, err = self.run_cli("compose", "--sources", "nope", "--lens", "x")
        self.assertEqual(code, 2)
        self.assertIn("unknown source", err)


if __name__ == "__main__":
    unittest.main()
