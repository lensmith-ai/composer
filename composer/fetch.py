"""One small HTTPS GET for feeds and pages, with a byte ceiling, a total time limit and a
public-address rule.

Adapters never call urllib themselves. They take a `get(url, timeout) -> Response` callable, so
tests pass bytes in and nothing touches the network.

What a fetch will not do:
  - use anything but https://, on the first request or after a redirect (no downgrade to http);
  - connect to this machine or a private network: loopback, link-local (169.254.x.x, where cloud
    servers keep their credentials), private ranges and other non-public addresses are refused.
    The name is resolved once, every address it gives must be public, and the socket connects
    to exactly those addresses (and is checked again once connected), so a name that answers
    differently later (DNS rebinding) changes nothing. To read a feed on your own network on
    purpose, set COMPOSER_ALLOW_PRIVATE_FETCH=1;
  - go through a proxy: HTTPS_PROXY and the like are ignored for feeds and pages, because a
    proxy resolves names itself and could reach what the check above refused;
  - follow more than 5 redirects;
  - read more than 2 MB, accept a body shorter than its Content-Length or a gzip stream that
    stops early, or take more than TOTAL_S seconds in all: resolving and each connection attempt
    get only the time that is left, and a watchdog shuts the connected socket when the time is
    up, so no stage (resolve, connect, TLS handshake, headers, body, redirects) can be stretched.
"""
from __future__ import annotations

import contextlib
import http.client
import ipaddress
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass

USER_AGENT = "lensmith-composer/0.1 (+https://github.com/lensmith-ai/composer)"
BYTE_CEILING = 2 * 1024 * 1024  # 2 MB; a feed or page above this is refused, never truncated
TOTAL_S = 60  # one request, from connect to the last byte; the per-read timeout is separate
MAX_REDIRECTS = 5
ALLOW_PRIVATE_ENV = "COMPOSER_ALLOW_PRIVATE_FETCH"
_CHUNK = 64 * 1024
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_6TO4 = ipaddress.ip_network("2002::/16")


class FetchError(RuntimeError):
    """The request failed, the answer was not 200, or the body was too large."""


class FetchTimeout(FetchError, TimeoutError):
    """The request timed out (also a TimeoutError, so adapters can stop asking a slow site)."""


@dataclass(frozen=True)
class Response:
    url: str
    status: int
    body: bytes


def private_allowed() -> bool:
    return os.environ.get(ALLOW_PRIVATE_ENV, "").strip() == "1"


def is_public_address(address: str) -> bool:
    """True only for a globally routable unicast address. Loopback, private, link-local,
    shared, multicast, reserved and unspecified addresses are not public, nor are IPv6 forms
    that carry one of those (IPv4-compatible, IPv4-mapped, NAT64, 6to4)."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if ip.version == 6:
        if int(ip) >> 32 == 0:  # ::a.b.c.d, the deprecated IPv4-compatible form (and :: and ::1)
            ip = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        elif ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif ip in _NAT64:
            ip = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        elif ip in _6TO4 and ip.sixtofour is not None:
            ip = ip.sixtofour
    return ip.is_global and not ip.is_multicast and not ip.is_unspecified


def check_address(address: str, what: str = "the site") -> None:
    if not private_allowed() and not is_public_address(address):
        raise FetchError(f"refused: {what} is on this machine or a private network ({address}); "
                         f"set {ALLOW_PRIVATE_ENV}=1 to allow it on purpose")


_RESOLVERS = threading.BoundedSemaphore(4)  # at most 4 lookups in flight, even ones given up on


def _remaining(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise FetchTimeout("the fetch ran out of time")
    return left


def _resolve(host: str, port: int, deadline: float) -> list:
    """getaddrinfo, given only the time that is left. A lookup that overruns is abandoned, but at
    most 4 can be in flight at once, so slow DNS cannot pile up threads."""
    if not _RESOLVERS.acquire(timeout=_remaining(deadline)):
        raise FetchTimeout("too many slow name lookups are still running")
    box: dict = {}

    def run():
        try:
            box["infos"] = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            box["error"] = exc
        finally:
            _RESOLVERS.release()

    t = threading.Thread(target=run, daemon=True, name="composer-resolve")
    t.start()
    t.join(_remaining(deadline))
    if t.is_alive():
        raise FetchTimeout(f"looking up {host[:80]} took longer than the time left")
    if "error" in box:
        raise FetchError(f"could not resolve {host[:80]}: {box['error']}")
    return box["infos"]


def connect_public(host: str, port: int, timeout: float, deadline: float, source_address=None) -> socket.socket:
    """A TCP socket to `host`, only on public addresses, within the deadline."""
    infos = _resolve(host, port, deadline)
    for info in infos:  # one private answer refuses the whole name
        check_address(info[4][0], str(host)[:80])
    last: Exception | None = None
    for family, socktype, proto, _, addr in infos:
        sock = socket.socket(family, socktype, proto)
        try:
            sock.settimeout(min(timeout, _remaining(deadline)))
            if source_address:
                sock.bind(source_address)
            sock.connect(addr)
            check_address(sock.getpeername()[0], str(host)[:80])
            sock.settimeout(timeout)
            return sock
        except FetchError:
            sock.close()
            raise
        except OSError as exc:
            sock.close()
            last = exc
    if last is not None:
        if time.monotonic() >= deadline:
            raise FetchTimeout("the fetch ran out of time while connecting")
        raise last
    raise FetchError(f"{host[:80]} has no address")


_local = threading.local()


class _Watchdog:
    """Shuts every socket opened for one fetch once its total time is up. It holds a duplicate
    of each socket (shutdown acts on the socket, not the descriptor), so it also cuts a TLS
    handshake in progress."""

    def __init__(self, deadline: float):
        self.deadline = deadline
        self.fired = False
        self._socks: list[socket.socket] = []
        self._lock = threading.Lock()
        self._timer = threading.Timer(max(0.0, deadline - time.monotonic()), self._fire)
        self._timer.daemon = True

    def start(self) -> None:
        self._timer.start()

    def watch(self, sock: socket.socket) -> None:
        try:
            dup = sock.dup()
        except OSError:
            return
        with self._lock:
            self._socks.append(dup)
            if self.fired:
                self._shut(dup)

    @staticmethod
    def _shut(sock: socket.socket) -> None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def _fire(self) -> None:
        with self._lock:
            self.fired = True
            for sock in self._socks:
                self._shut(sock)

    def stop(self) -> None:
        self._timer.cancel()
        with self._lock:
            for sock in self._socks:
                sock.close()
            self._socks.clear()


def _watch(sock: socket.socket) -> socket.socket:
    dog = getattr(_local, "watchdog", None)
    if dog is not None:
        dog.watch(sock)
    return sock


class _GuardedHTTPSConnection(http.client.HTTPSConnection):
    """An HTTPS connection made only by connect_public, within the fetch's deadline."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = self._guarded_create

    def _guarded_create(self, address, timeout=socket.getdefaulttimeout(), source_address=None, *args, **kwargs):
        if getattr(self, "_tunnel_host", None):
            raise FetchError("feeds are not fetched through a proxy")
        dog = getattr(_local, "watchdog", None)
        deadline = dog.deadline if dog is not None else time.monotonic() + TOTAL_S
        if not isinstance(timeout, (int, float)):
            timeout = 20
        return _watch(connect_public(address[0], address[1], timeout, deadline, source_address))


class _GuardedHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_GuardedHTTPSConnection, req, context=self._context)


@contextlib.contextmanager
def redirect_rules(rule):
    """For fetches made by this thread inside the block: `rule(new_address)` is called for every redirect, BEFORE
    anything is requested from the new address, and may raise FetchError to refuse it. Rules stack (the block's rule
    runs after those of any enclosing block). A caller uses this to hold a fetch to a scope it chose, or to count each
    hop as a request of its own; a `get` that never reaches http_get (a test's table) is not affected."""
    outer = getattr(_local, "redirect_rules", ())
    _local.redirect_rules = outer + (rule,)
    try:
        yield
    finally:
        _local.redirect_rules = outer


class _HttpsOnlyRedirects(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise FetchError(f"refused a redirect to a non-https address ({code})")
        for rule in getattr(_local, "redirect_rules", ()):
            rule(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _NoPlainHTTP(urllib.request.HTTPHandler):
    def http_open(self, req):
        raise FetchError("only https addresses are fetched")


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _HttpsOnlyRedirects(), _GuardedHTTPSHandler(),
                                      _NoPlainHTTP())


def _read_capped(resp, deadline: float, total_s: float = TOTAL_S) -> bytes:
    """Read up to BYTE_CEILING + 1 bytes, giving up once the total time limit has passed.

    read1 returns whatever one socket read brings (a plain read(n) would wait for all n bytes,
    and a server sending a byte at a time could keep it waiting far past the deadline)."""
    read = getattr(resp, "read1", None) or resp.read
    parts: list[bytes] = []
    size = 0
    while size <= BYTE_CEILING:
        if time.monotonic() > deadline:
            raise FetchTimeout(f"the answer took longer than {total_s:g} s in total; refused")
        chunk = read(min(_CHUNK, BYTE_CEILING + 1 - size))
        if not chunk:
            break
        parts.append(chunk)
        size += len(chunk)
    left = getattr(resp, "length", None)
    if size <= BYTE_CEILING and isinstance(left, int) and left > 0:
        raise FetchError(f"the answer ended {left} bytes before its Content-Length; refused")
    return b"".join(parts)


def http_get(url: str, timeout: float, user_agent: str = USER_AGENT, *, opener=None,
             total_s: float = TOTAL_S) -> Response:
    """GET `url` and return its body, or raise FetchError. Only public https addresses are fetched."""
    if urllib.parse.urlsplit(url).scheme != "https":
        raise FetchError("only https addresses are fetched")
    req = urllib.request.Request(url, headers={"User-Agent": user_agent,
                                               "Accept": "application/rss+xml, application/atom+xml, "
                                                         "application/xml, text/xml, text/html, application/json, */*"})
    deadline = time.monotonic() + total_s
    too_long = f"the answer took longer than {total_s:g} s in total; refused"
    dog = _Watchdog(deadline)
    _local.watchdog = dog
    dog.start()
    try:
        with (opener or _OPENER).open(req, timeout=timeout) as resp:
            body = _read_capped(resp, deadline, total_s)
            status = resp.status
            final = resp.geturl()
            encoding = (resp.headers.get("Content-Encoding") or "").strip().lower()
        if dog.fired:  # the socket was cut: what was read may be a truncated body
            raise FetchTimeout(too_long)
    except FetchError:
        if dog.fired and not isinstance(sys.exc_info()[1], FetchTimeout):
            raise FetchTimeout(too_long) from None
        raise
    except Exception as exc:
        if dog.fired:
            raise FetchTimeout(too_long) from None
        raise _fetch_error(exc, timeout) from None
    finally:
        _local.watchdog = None
        dog.stop()
    if len(body) > BYTE_CEILING:
        raise FetchError(f"body over the {BYTE_CEILING}-byte ceiling; refused, not truncated")
    return Response(final, status, decode_body(body, encoding))


def _fetch_error(exc: Exception, timeout: float) -> FetchError:
    """The FetchError (or FetchTimeout) that says what went wrong, without a traceback."""
    if isinstance(exc, urllib.error.HTTPError):
        return FetchError(f"HTTP {exc.code}: {exc.reason}")
    if isinstance(exc, TimeoutError):
        return FetchTimeout(f"timed out after {timeout} s")
    if isinstance(exc, urllib.error.URLError):
        if isinstance(exc.reason, FetchError):
            return exc.reason
        if isinstance(exc.reason, TimeoutError):
            return FetchTimeout(f"timed out after {timeout} s")
        return FetchError(f"URLError: {exc.reason}")
    if isinstance(exc, (OSError, http.client.HTTPException)):
        return FetchError(f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}")
    return FetchError(f"{type(exc).__name__}: {str(exc)[:200]}")


def decode_body(body: bytes, encoding: str = "") -> bytes:
    """Undo gzip when the server compressed the body without being asked (some feed hosts do,
    now and then). The unpacked size is held to the same ceiling, so a small compressed body
    cannot expand into a huge one."""
    if encoding not in ("", "identity", "gzip", "x-gzip"):
        raise FetchError(f"unsupported content encoding {encoding[:30]!r}; refused")
    if encoding not in ("gzip", "x-gzip") and not body.startswith(b"\x1f\x8b"):
        return body
    unpack = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = unpack.decompress(body, BYTE_CEILING + 1)
    except zlib.error:
        raise FetchError("the body says it is gzip but could not be unpacked") from None
    if len(out) > BYTE_CEILING or unpack.unconsumed_tail:
        raise FetchError(f"the unpacked body is over the {BYTE_CEILING}-byte ceiling; refused")
    if not unpack.eof:
        raise FetchError("the gzip body stops before its end (no checksum); refused")
    return out
