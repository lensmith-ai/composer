"""Two page-parity bugs: /health must list the running job ids (the app page's rejoin hint reads
active_jobs as a list, as the live app sends it), and HEAD must be answered like GET without a body
(audio players and link checkers ask for an audio file's size first; the server answered 501)."""
import http.client
import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from install_helpers import FakeRender, fake_home

from composer import server
from composer.registry import BUNDLED, Registry, read_file

from test_narration import ON, Served


class HealthListsRunningJobsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.release = threading.Event()

        def worker(job, draft_ready):
            draft_ready({"schema": "composer-edition/v1", "job": job["job"], "cards": []})
            self.release.wait(5)
            return {"status": "ok", "claim_evidence": {"job": job["job"], "draft_sha256": job["draft_sha256"]}}

        self.app = server.App(Registry(read_file(BUNDLED)), lambda: "model", data_root=self.tmp.name, job_worker=worker)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler_for(self.app))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.release.set)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def request(self, method, path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json"}
        if method == "POST":
            h.update({"Origin": f"http://127.0.0.1:{self.port}", "Sec-Fetch-Site": "same-origin",
                      "X-Composer-CSRF": server.CSRF_VALUE})
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        out = r.status, json.loads(r.read())
        c.close()
        return out

    def test_health_lists_the_running_job_ids_the_rejoin_link_uses(self):
        status, idle = self.request("GET", "/health")
        self.assertEqual(200, status)
        self.assertEqual([], idle["active_jobs"])
        self.assertEqual(0, idle["active_count"])
        status, accepted = self.request("POST", "/compose", json.dumps({"sources": ["google-ai"], "lens": "x"}))
        self.assertEqual(202, status)
        job = accepted["job"]
        _, busy = self.request("GET", "/health")
        self.assertIsInstance(busy["active_jobs"], list)
        self.assertEqual([job], busy["active_jobs"])
        self.assertEqual(1, busy["active_count"])
        self.assertEqual(1, busy["available"])
        # the id is one the page's brief link accepts, so the rejoin link opens that brief
        js = (Path(server.__file__).parent / "web" / "app" / "app.js").read_text(encoding="utf-8")
        self.assertIn("var active=(h&&h.active_jobs)||[]", js)
        self.release.set()
        for _ in range(200):
            if not self.request("GET", "/health")[1]["active_jobs"]:
                break
            time.sleep(0.01)
        self.assertEqual([], self.request("GET", "/health")[1]["active_jobs"])


class HeadIsAnsweredLikeGetTests(unittest.TestCase):
    def test_head_on_an_audio_file_gives_the_get_headers_and_no_body(self):
        with fake_home() as home:
            s = Served(home, ON, FakeRender())
            try:
                job = s.compose()
                name = s.job(job)["audio"]["file"]
                path = f"/data/live/{job}/{name}"
                g_status, g_body, g_headers = s.req("GET", path)
                h_status, h_body, h_headers = s.req("HEAD", path)
                self.assertEqual(200, g_status)
                self.assertEqual(200, h_status)
                self.assertEqual(b"", h_body)
                self.assertEqual(g_headers["Content-Type"], h_headers["Content-Type"])
                self.assertEqual(str(len(g_body)), h_headers["Content-Length"])
                self.assertEqual("bytes", h_headers["Accept-Ranges"])
                r_status, r_body, r_headers = s.req("HEAD", path, headers={"Range": "bytes=0-1"})
                self.assertEqual(206, r_status)
                self.assertEqual(b"", r_body)
                self.assertEqual("2", r_headers["Content-Length"])
                self.assertEqual(f"bytes 0-1/{len(g_body)}", r_headers["Content-Range"])
                # the server still answers normally after a HEAD (no body left on the connection)
                self.assertEqual(200, s.req("GET", path)[0])
            finally:
                s.close()

    def test_head_on_the_app_page_and_a_missing_file(self):
        with fake_home() as home:
            s = Served(home, ON, FakeRender())
            try:
                status, body, headers = s.req("HEAD", "/app/")
                self.assertEqual(200, status)
                self.assertEqual(b"", body)
                self.assertGreater(int(headers["Content-Length"]), 0)
                status, body, _ = s.req("HEAD", "/data/live/job-0000000000000000/none.mp3")
                self.assertEqual(404, status)
                self.assertEqual(b"", body)
            finally:
                s.close()

    def test_head_obeys_the_same_host_rule_as_get(self):
        with fake_home() as home:
            s = Served(home, ON, FakeRender())
            try:
                status, body, _ = s.req("HEAD", "/app/", headers={"Host": "evil.invalid"})
                self.assertEqual(403, status)
                self.assertEqual(b"", body)
            finally:
                s.close()


if __name__ == "__main__":
    unittest.main()
