"""The CA rule (composer/tls.py): HTTPS must work on a Python that has no trusted authorities of its own.

The handshake tests run a real local HTTPS server whose certificate is signed by a throwaway authority. On a
Python with no system authorities and no certifi, the request must FAIL certificate verification (this is the
python.org-on-macOS-before-"Install Certificates" situation); with certifi's list holding that authority it must
succeed. Verification is never turned off in either case."""
from __future__ import annotations

import http.server
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from composer import tls  # noqa: E402


class _Hello(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"hello"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@unittest.skipUnless(shutil.which("openssl"), "openssl makes the throwaway authority")
class RootsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        cls.cert, cls.key = d / "cert.pem", d / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=localhost",
                        "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost", "-addext", "basicConstraints=critical,CA:TRUE",
                        "-keyout", str(cls.key), "-out", str(cls.cert)], check=True, capture_output=True)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cls.cert, cls.key)
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Hello)
        cls.httpd.socket = ctx.wrap_socket(cls.httpd.socket, server_side=True)
        cls.url = f"https://127.0.0.1:{cls.httpd.server_address[1]}/"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def setUp(self):
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("SSL_CERT_FILE", None)
        os.environ.pop("SSL_CERT_DIR", None)
        tls._cached.cache_clear()
        self.addCleanup(tls._cached.cache_clear)
        self.addCleanup(self.env.stop)

    def _fake_certifi(self):
        fake = mock.Mock()
        fake.where.return_value = str(self.cert)
        return fake

    def test_no_system_roots_and_no_certifi_fails_verification(self):
        with mock.patch.object(tls, "_system_has_roots", return_value=False), \
                mock.patch.dict(sys.modules, {"certifi": None}):  # import certifi -> ImportError
            with self.assertRaises(urllib.error.URLError) as cm:
                tls.urlopen(self.url, timeout=10)
        self.assertIsInstance(cm.exception.reason, ssl.SSLCertVerificationError)

    def test_no_system_roots_uses_certifi_and_succeeds(self):
        with mock.patch.object(tls, "_system_has_roots", return_value=False), \
                mock.patch.dict(sys.modules, {"certifi": self._fake_certifi()}):
            with tls.urlopen(self.url, timeout=10) as resp:
                self.assertEqual(resp.read(), b"hello")

    def test_system_roots_present_certifi_is_not_added(self):
        fake = self._fake_certifi()
        with mock.patch.object(tls, "_system_has_roots", return_value=True), mock.patch.dict(sys.modules, {"certifi": fake}):
            with self.assertRaises(urllib.error.URLError):
                tls.urlopen(self.url, timeout=10)  # system list does not know the throwaway authority
        fake.where.assert_not_called()

    def test_ssl_cert_file_is_the_persons_choice_and_certifi_is_not_added(self):
        os.environ["SSL_CERT_FILE"] = str(self.cert)
        tls._cached.cache_clear()
        fake = mock.Mock()
        fake.where.side_effect = AssertionError("certifi must not be loaded when SSL_CERT_FILE is set")
        with mock.patch.object(tls, "_system_has_roots", return_value=False), mock.patch.dict(sys.modules, {"certifi": fake}):
            with tls.urlopen(self.url, timeout=10) as resp:
                self.assertEqual(resp.read(), b"hello")

    def test_the_provider_and_feed_openers_use_the_same_rule(self):
        from composer import fetch, providers
        with mock.patch.object(tls, "_system_has_roots", return_value=False), \
                mock.patch.dict(sys.modules, {"certifi": self._fake_certifi()}):
            with providers._OPENER.open(self.url, timeout=10) as resp:  # same opener the model calls use
                self.assertEqual(resp.read(), b"hello")
            self.assertIs(fetch._tls, tls)  # the feed fetcher takes its context from this module too

    def test_the_real_certifi_is_installed_and_has_authorities(self):
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
        self.assertGreater(ctx.cert_store_stats()["x509_ca"], 50)


class SystemRootsTests(unittest.TestCase):
    def test_empty_default_paths_read_as_no_roots(self):
        with tempfile.TemporaryDirectory() as empty:
            paths = ssl.DefaultVerifyPaths(cafile=None, capath=empty, openssl_cafile_env="SSL_CERT_FILE",
                                           openssl_cafile=os.path.join(empty, "nope.pem"), openssl_capath_env="SSL_CERT_DIR",
                                           openssl_capath=empty)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            with mock.patch.object(ssl, "get_default_verify_paths", return_value=paths):
                self.assertFalse(tls._system_has_roots(ctx))
                Path(empty, "abc.0").write_text("x")
                self.assertTrue(tls._system_has_roots(ctx))


if __name__ == "__main__":
    unittest.main()
