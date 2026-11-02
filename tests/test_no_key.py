"""With no model key, Compose on the app page gets one plain sentence before any job starts, and the recorded brief
still shows. The same sentence comes from `composer compose`, `composer doctor` and the daily brief's skip."""
import http.client
import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from install_helpers import fake_home

from composer import cli, doctor, installer, providers, server
from composer.registry import BUNDLED, Registry, read_file

MESSAGE = "Composer needs a model key to write a brief. Run ./setup.sh --reconfigure provider."


class PageComposeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patches = [mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": ""}),
                   mock.patch.object(providers, "_KEY_FILE", None)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.app = server.App(Registry(read_file(BUNDLED)), lambda: providers.from_env(env={}),
                              data_root=Path(self.tmp.name) / "data")
        quiet = type("Quiet", (server.handler_for(self.app),), {"log_message": lambda *a: None})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), quiet)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.port = self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def call(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Host": f"127.0.0.1:{self.port}"}
        if body is not None:
            headers.update({"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}",
                            server.CSRF_HEADER: server.CSRF_VALUE})
        conn.request(method, path, body=None if body is None else json.dumps(body), headers=headers)
        reply = conn.getresponse()
        data = reply.read()
        conn.close()
        return reply.status, data

    def test_compose_says_it_needs_a_key_and_starts_no_job(self):
        status, data = self.call("POST", "/compose", {"sources": ["google-ai", "deepmind"], "lens": "x",
                                                      "insights": 5, "reading_level": "standard"})
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(data), {"error": MESSAGE})
        self.assertEqual(self.app.jobs.index()["items"], [])
        self.assertEqual(self.app.jobs.health().get("active_jobs") or [], [])
        # the recorded brief still shows: the page, the latest edition, the options
        status, page = self.call("GET", "/app/")
        self.assertEqual(status, 200)
        status, latest = self.call("GET", "/api/latest")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(latest)["cards"])
        self.assertEqual(self.call("GET", "/data/options.json")[0], 200)


class CommandLineTests(unittest.TestCase):
    def test_compose_and_doctor_say_the_same(self):
        with fake_home() as home, mock.patch.object(providers, "_KEY_FILE", None):
            err = io.StringIO()
            with redirect_stderr(err):
                code = cli.main(["compose", "--sources", "google-ai", "--lens", "x", "--out", str(home / "b")])
            self.assertEqual(code, 2)
            self.assertIn(MESSAGE, err.getvalue())
            target = home / ".lensmith-composer"
            installer.run(home=target, data=None, answers_file=None, assume_yes=True, reconfigure=[],
                          data_only=False, out=lambda *_: None, interactive=False)
            lines = []
            doctor.run(target, target / "data", out=lines.append)
        key = next(ln for ln in lines if ln.startswith(("SKIP key", "FAIL key", "PASS key")))
        self.assertTrue(key.startswith(f"SKIP key: {MESSAGE}"), key)


if __name__ == "__main__":
    unittest.main()
