"""One TLS context for every HTTPS request Composer makes (feeds, model providers, the narration model download).

Python takes its trusted certificate authorities from the operating system's OpenSSL setup. That is empty on some
Pythons: python.org's macOS Python has none until its "Install Certificates.command" has been run, and a private
Python (uv's) on a computer without the ca-certificates package has none either. Without them every HTTPS request
fails with CERTIFICATE_VERIFY_FAILED, so a stranger's first brief would fail on the first feed.

The rule, in order:
  1. SSL_CERT_FILE or SSL_CERT_DIR set: the person chose, use exactly what OpenSSL does with them.
  2. The system has authorities (a CA file, a CA folder with files in it, or any already loaded): use those, so a
     company's own root, installed in the system, keeps working.
  3. Otherwise: the authorities in the pinned `certifi` package, which Composer depends on.
Verification is never switched off.
"""
from __future__ import annotations

import functools
import http.client
import os
import ssl
import urllib.request


def _system_has_roots(ctx: ssl.SSLContext) -> bool:
    if ctx.cert_store_stats().get("x509_ca", 0) > 0:
        return True
    paths = ssl.get_default_verify_paths()
    for name in (paths.cafile, paths.openssl_cafile):
        if name and os.path.isfile(name):
            return True
    for name in (paths.capath, paths.openssl_capath):
        try:
            if name and os.path.isdir(name) and os.listdir(name):
                return True
        except OSError:
            continue
    return False


def build_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR") or _system_has_roots(ctx):
        return ctx
    try:
        import certifi
    except ImportError:
        return ctx  # nothing to add; the request will fail with a clear certificate error, never run unverified
    ctx.load_verify_locations(cafile=certifi.where())
    return ctx


@functools.lru_cache(maxsize=4)
def _cached(cert_file: str, cert_dir: str) -> ssl.SSLContext:
    return build_context()


def ssl_context() -> ssl.SSLContext:
    """The context, built on first use (and again if SSL_CERT_FILE or SSL_CERT_DIR change), never at import."""
    return _cached(os.environ.get("SSL_CERT_FILE", ""), os.environ.get("SSL_CERT_DIR", ""))


class HTTPSHandler(urllib.request.HTTPSHandler):
    """urllib's HTTPS handler with this module's context, taken when a request is made."""

    def https_open(self, req):
        return self.do_open(http.client.HTTPSConnection, req, context=ssl_context())


def urlopen(url, *, timeout: float = 60):
    """urllib.request.urlopen with this context."""
    return urllib.request.urlopen(url, timeout=timeout, context=ssl_context())
