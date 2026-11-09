"""`composer up`: the app at /, its health check, one instance per data folder, and the proxy mode the
container uses (only the proxy network, the public address in Host and Origin, its own health check allowed)."""
import http.client
import ipaddress
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from helpers import ROOT
from install_helpers import fake_home

from composer import installer, server
from composer.registry import Registry


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get(port, path, host=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", path, headers={"Host": host or f"127.0.0.1:{port}"})
    r = c.getresponse()
    body = r.read()
    c.close()
    return r.status, body, dict(r.getheaders())


@unittest.skipUnless(os.name == "posix", "the run lock and signals are POSIX here")
class UpTests(unittest.TestCase):
    def start(self, target, port, env):
        proc = subprocess.Popen([sys.executable, "-m", "composer", "up", "--home", str(target), "--port", str(port)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=ROOT,
                                env=dict(env, PYTHONFAULTHANDLER="1"))
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                if get(port, "/health")[0] == 200:
                    return proc
            except OSError:
                time.sleep(0.1)
        proc.send_signal(signal.SIGABRT)  # faulthandler is on: the child prints where it is stuck, and ends
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise AssertionError(f"/health never answered 200; the child said:\n{proc.stdout.read()}")

    def test_up_serves_the_app_and_health_and_runs_once(self):
        with fake_home() as home:
            target = home / ".lensmith-composer"
            installer.run(home=target, data=None, answers_file=None, assume_yes=True, reconfigure=[],
                          data_only=False, out=lambda *_: None, interactive=False)
            port = free_port()
            env = dict(os.environ)
            proc = self.start(target, port, env)
            try:
                status, body, _ = get(port, "/health")
                self.assertEqual(json.loads(body)["ok"], True)
                status, _, headers = get(port, "/")
                self.assertEqual((status, headers["Location"]), (302, "/app/"))
                status, body, headers = get(port, "/app/")
                self.assertEqual(status, 200)
                self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
                self.assertEqual(json.loads(get(port, "/data/options.json")[1])["voices"], [])
                second = subprocess.run([sys.executable, "-m", "composer", "up", "--home", str(target), "--port",
                                         str(free_port())], capture_output=True, text=True, timeout=30, cwd=ROOT,
                                        env=env)
                self.assertEqual(second.returncode, 2)
                self.assertIn("already running", second.stderr)
                proc.terminate()  # SIGTERM, as `docker compose stop` sends: a clean stop, the lock released
                self.assertEqual(proc.wait(10), 0)
                text = proc.stdout.read()
                self.assertIn("serving on", text)
                # the address on a line of its own, plain text (a pipe is not a terminal): Cmd+clickable on a Mac
                self.assertIn(f"Open: http://127.0.0.1:{port}/", text.splitlines())
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(10)
                proc.stdout.close()

    def test_up_without_setup_says_what_to_do(self):
        with fake_home() as home:
            run = subprocess.run([sys.executable, "-m", "composer", "up", "--home", str(home / "nothing")],
                                 capture_output=True, text=True, timeout=30, cwd=ROOT)
            self.assertEqual(run.returncode, 2)
            self.assertIn("setup", run.stderr)


class ProxyModeTests(unittest.TestCase):
    ORIGIN = "https://brief.example.com"

    def setUp(self):
        self.app = server.App(Registry.load(None), lambda: object(),
                              compose=lambda **_: (_ for _ in ()).throw(AssertionError("no compose here")))

    def handler(self, client_ip):
        cls = server.handler_for(self.app, local_only=False, trusted=ipaddress.ip_network("172.30.65.0/24"),
                                 public_origin=self.ORIGIN)
        outer = self

        class ProxyRequest(cls):
            def __init__(self, method, path, headers, body=b""):
                self.client_address = (client_ip, 50000)
                self.command, self.path, self.request_version = method, path, "HTTP/1.1"
                self.headers = headers
                self.rfile = __import__("io").BytesIO(body)
                self.wfile = __import__("io").BytesIO()
                self.requestline = f"{method} {path} HTTP/1.1"

            def log_message(self, *a):
                pass
        outer.ProxyRequest = ProxyRequest
        return ProxyRequest

    def call(self, ip, method, path, headers, body=b""):
        import email.message
        msg = email.message.Message()
        for k, v in headers.items():
            msg[k] = v
        h = self.handler(ip)(method, path, msg, body)
        getattr(h, "do_" + method)()
        raw = h.wfile.getvalue().decode("latin-1")
        return int(raw.split(" ", 2)[1])

    def test_only_the_proxy_network_and_the_public_host(self):
        self.assertEqual(self.call("172.30.65.2", "GET", "/health", {"Host": "brief.example.com"}), 200)
        self.assertEqual(self.call("10.0.0.5", "GET", "/health", {"Host": "brief.example.com"}), 403)
        self.assertEqual(self.call("172.30.65.2", "GET", "/health", {"Host": "evil.example"}), 403)
        self.assertEqual(self.call("127.0.0.1", "GET", "/health", {"Host": "127.0.0.1:8765"}), 200)  # health check
        self.assertEqual(self.call("127.0.0.1", "GET", "/health", {"Host": "brief.example.com"}), 403)

    def test_change_requests_need_the_public_origin(self):
        body = b"{}"
        base = {"Host": "brief.example.com", "Content-Type": "application/json", "X-Composer-CSRF": "same-origin",
                "Content-Length": "2"}
        self.assertEqual(self.call("172.30.65.2", "POST", "/retention", dict(base, Origin=self.ORIGIN), body), 200)
        self.assertEqual(self.call("172.30.65.2", "POST", "/retention", dict(base, Origin="https://evil.example"),
                                   body), 403)
        self.assertEqual(self.call("172.30.65.2", "POST", "/retention", dict(base, Origin=self.ORIGIN,
                                                                            **{"Sec-Fetch-Site": "cross-site"}),
                                   body), 403)

    def test_bind_and_origin_rules(self):
        with self.assertRaises(SystemExit):
            server.check_bind("0.0.0.0", "", None)
        server.check_bind("0.0.0.0", "", ipaddress.ip_network("172.30.65.0/24"))
        self.assertEqual(server.check_public_origin("https://Brief.Example.com:8443/"), "https://brief.example.com:8443")
        for bad in ("", "brief.example.com", "https://x.example/path", "ftp://x.example", "https://u@x.example"):
            with self.subTest(origin=bad), self.assertRaises(SystemExit):
                server.check_public_origin(bad)
        with self.assertRaises(SystemExit):
            server.parse_trusted("not a network")

class NoReverseLookupTests(unittest.TestCase):
    def test_binding_does_not_ask_the_resolver_for_the_fully_qualified_name(self):
        """socket.getfqdn blocked `composer up` on a macOS runner; the server must not call it (found by CI there)."""
        from unittest import mock
        from composer.httpd import LocalHTTPServer
        from http.server import BaseHTTPRequestHandler
        with mock.patch("socket.getfqdn", side_effect=AssertionError("getfqdn was called")):
            httpd = LocalHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
            try:
                self.assertEqual(httpd.server_name, "127.0.0.1")
                self.assertEqual(httpd.server_port, httpd.server_address[1])
            finally:
                httpd.server_close()


if __name__ == "__main__":
    unittest.main()
