"""One small HTTP GET for feeds and pages, with a byte ceiling.

Adapters never call urllib themselves. They take a `get(url, timeout) -> Response` callable, so
tests pass bytes in and nothing touches the network.
"""
from __future__ import annotations

import urllib.error
import zlib
import urllib.parse
import urllib.request
from dataclasses import dataclass

USER_AGENT = "lensmith-composer/0.1 (+https://github.com/lensmith-ai/composer)"
BYTE_CEILING = 2 * 1024 * 1024  # 2 MB; a feed or page above this is refused, never truncated


class FetchError(RuntimeError):
    """The request failed, the answer was not 200, or the body was too large."""


class FetchTimeout(FetchError, TimeoutError):
    """The request timed out (also a TimeoutError, so adapters can stop asking a slow site)."""


@dataclass(frozen=True)
class Response:
    url: str
    status: int
    body: bytes


class _NoRedirectToOtherSchemes(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme not in ("http", "https"):
            raise FetchError(f"refused a redirect to a non-web address ({code})")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_NoRedirectToOtherSchemes())


def http_get(url: str, timeout: float, user_agent: str = USER_AGENT) -> Response:
    """GET `url` and return its body, or raise FetchError. Only http(s) addresses are fetched."""
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise FetchError("only http(s) addresses are fetched")
    req = urllib.request.Request(url, headers={"User-Agent": user_agent,
                                               "Accept": "application/rss+xml, application/atom+xml, "
                                                         "application/xml, text/xml, text/html, application/json, */*"})
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            body = resp.read(BYTE_CEILING + 1)
            status = resp.status
            final = resp.geturl()
            encoding = (resp.headers.get("Content-Encoding") or "").strip().lower()
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code}: {exc.reason}") from None
    except TimeoutError:
        raise FetchTimeout(f"timed out after {timeout} s") from None
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise FetchTimeout(f"timed out after {timeout} s") from None
        raise FetchError(f"URLError: {exc.reason}") from None
    except OSError as exc:
        raise FetchError(f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}") from None
    if len(body) > BYTE_CEILING:
        raise FetchError(f"body over the {BYTE_CEILING}-byte ceiling; refused, not truncated")
    return Response(final, status, decode_body(body, encoding))


def decode_body(body: bytes, encoding: str = "") -> bytes:
    """Undo gzip when the server compressed the body without being asked (some feed hosts do,
    now and then). The unpacked size is held to the same ceiling, so a small compressed body
    cannot expand into a huge one."""
    if encoding not in ("gzip", "x-gzip") and not body.startswith(b"\x1f\x8b"):
        return body
    unpack = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = unpack.decompress(body, BYTE_CEILING + 1)
    except zlib.error:
        raise FetchError("the body says it is gzip but could not be unpacked") from None
    if len(out) > BYTE_CEILING or unpack.unconsumed_tail:
        raise FetchError(f"the unpacked body is over the {BYTE_CEILING}-byte ceiling; refused")
    return out
