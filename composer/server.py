"""`composer serve`: the always-on tier. A small web server that shows the latest brief and,
with a key in its environment, composes new ones from a form.

Safe defaults:
  - It listens on 127.0.0.1 only, unless you pass --host.
  - On any other address it refuses to start without COMPOSER_SERVER_PASS set; every compose
    request must then send that phrase in the X-Composer-Pass header. Anyone who can compose
    spends your API credit, so do not skip this.
  - On this machine (the default), it answers only requests addressed to this machine by name
    (Host 127.0.0.1, localhost or [::1]), so a web site that points its own name at 127.0.0.1
    (DNS rebinding) is refused. A compose request must be sent as application/json from the
    page's own origin: a browser cannot send that from another site without asking first, and
    this server never says yes, so another site you visit cannot compose and spend your credit.
  - One brief at a time; a second request while one runs gets 429.
  - Request bodies over 16 KB, unknown sources and long lenses are refused before any fetch.
  - It is a plain standard-library server: put a TLS-terminating proxy in front of it before
    you expose it to the internet.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import threading
import tempfile
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import demo, page, pipeline
from .job_store import JobStore, StoreError
from .prompt import DEFAULT_INSIGHTS, LENS_MAX_CHARS
from .providers import ProviderError
from .registry import RegistryError

MAX_BODY = 16 * 1024
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
LOOPBACK_NAMES = {"127.0.0.1", "localhost", "::1"}
CSRF_HEADER = "X-Composer-CSRF"
CSRF_VALUE = "same-origin"


_PORT = re.compile(r"[0-9]{1,5}")


def host_name(host_header: str) -> str:
    """The name part of a Host header (no port, no brackets, lower case), or "" when the header
    is not exactly one authority: name[:port] or [ipv6][:port], nothing before or after."""
    value = (host_header or "").strip().lower()
    if value.startswith("["):
        close = value.find("]")
        if close < 0:
            return ""
        name, rest = value[1:close], value[close + 1:]
    elif value.count(":") == 1:
        name, rest = value.split(":", 1)
        rest = ":" + rest
    elif ":" in value:
        return ""  # an IPv6 address must be in brackets
    else:
        name, rest = value, ""
    if rest and not (rest.startswith(":") and _PORT.fullmatch(rest[1:]) and 1 <= int(rest[1:]) <= 65535):
        return ""
    return name


def request_problem(method: str, headers, *, local_only: bool) -> str | None:
    """Why a request must be refused before it is handled, or None.

    A compose POST must always declare its body as JSON (a cross-site page cannot send that
    without a CORS preflight, which this server never answers). When the server listens on this
    machine (local_only), the Host must also name this machine, and a POST's Origin (if sent) must
    be this server's own and a browser's Sec-Fetch-Site (if sent) same-origin. Beyond this machine
    the pass phrase header does that job (a custom header also needs a preflight), and a TLS
    proxy in front may rewrite Host, so those two checks are not made there."""
    get_all = getattr(headers, "get_all", None)
    if get_all is not None:
        for name in ("Host", "Origin", "Content-Type", "Sec-Fetch-Site"):
            if len(get_all(name) or []) > 1:
                return f"send one {name} header"
    host = headers.get("Host", "")
    if local_only and host_name(host) not in LOOPBACK_NAMES:
        return "this server only answers requests addressed to 127.0.0.1 or localhost"
    if method != "POST":
        return None
    ctype = (headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    if ctype != "application/json":
        return "send the request as application/json"
    if not hmac.compare_digest(headers.get(CSRF_HEADER, ""), CSRF_VALUE):
        return "send the same-origin anti-forgery header"
    if not local_only:
        return None
    origin = headers.get("Origin")
    if origin is not None:
        o = urlsplit(origin)
        if origin == "null" or o.scheme not in ("http", "https") or o.netloc.lower() != host.strip().lower():
            return "compose requests are only accepted from this server's own page"
    site = (headers.get("Sec-Fetch-Site") or "").strip().lower()
    if site and site not in ("same-origin", "none"):
        return "compose requests are only accepted from this server's own page"
    return None


class App:
    def __init__(self, registry, make_model, *, out_dir: Path | None = None, passphrase: str = "",
                 compose=pipeline.compose, data_root: Path | str | None = None, job_worker=None):
        self.registry = registry
        self.make_model = make_model
        self.out_dir = out_dir
        self.passphrase = passphrase
        self.compose = compose
        self.lock = threading.Lock()
        self.latest = demo.load()
        root = Path(data_root) if data_root is not None else ((out_dir or Path(tempfile.mkdtemp(prefix="composer-data-"))) / "composer-data")
        self.jobs = JobStore(root, worker=job_worker or self._job_worker)

    def _job_worker(self, job: dict, draft_ready) -> dict:
        request = job["request"]
        sources = self.registry.pick(request["sources"])
        model = self.make_model()
        if hasattr(model, "ready"):
            model.ready()
        run = self.compose(lens=request["lens"], sources=sources, model=model,
                           count=request.get("insights", DEFAULT_INSIGHTS))
        draft_ready(run["edition"])
        return {"status": "ok", "claim_evidence": {"job": job["job"],
                                                        "draft_sha256": job["draft_sha256"]}}

    def submit_job(self, headers, body: bytes) -> tuple[int, dict]:
        if self.passphrase:
            sent = headers.get("X-Composer-Pass", "")
            if not hmac.compare_digest(sent.encode("utf-8"), self.passphrase.encode("utf-8")):
                return 403, {"error": "wrong or missing pass phrase"}
        try:
            req = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return 400, {"error": "send a JSON object"}
        if not isinstance(req, dict) or set(req) - {"sources", "lens", "insights"}:
            return 400, {"error": "send {\"sources\": [...], \"lens\": \"...\"}"}
        lens, ids = req.get("lens"), req.get("sources")
        count = req.get("insights", DEFAULT_INSIGHTS)
        if not isinstance(lens, str) or not lens.strip() or len(lens) > LENS_MAX_CHARS:
            return 400, {"error": f"the lens must be 1 to {LENS_MAX_CHARS} characters"}
        if not isinstance(ids, list) or not ids or len(ids) > 8 or not all(isinstance(x, str) for x in ids):
            return 400, {"error": "name 1 to 8 sources"}
        if not isinstance(count, int) or isinstance(count, bool) or not 3 <= count <= 8:
            return 400, {"error": "insights must be from 3 to 8"}
        try:
            self.registry.pick(ids)
            return 202, self.jobs.submit({"sources": ids, "lens": lens.strip(), "insights": count})
        except RegistryError as exc:
            return 400, {"error": str(exc)}
        except RuntimeError:
            return 409, {"error": "compose capacity is full"}

    def change_job(self, headers, path: str, request: object) -> tuple[int, dict]:
        if self.passphrase:
            sent = headers.get("X-Composer-Pass", "")
            if not hmac.compare_digest(sent.encode("utf-8"), self.passphrase.encode("utf-8")):
                return 403, {"error": "wrong or missing pass phrase"}
        if not isinstance(request, dict):
            return 400, {"error": "send a JSON object"}
        try:
            if path.startswith("/save/") and request == {}:
                return 200, self.jobs.save(path.removeprefix("/save/"))
            if path.startswith("/delete/") and request == {}:
                self.jobs.delete(path.removeprefix("/delete/"))
                return 200, {"deleted": path.removeprefix("/delete/")}
            if path.startswith("/restore/") and request == {}:
                return 200, self.jobs.restore(path.removeprefix("/restore/"))
            if path == "/retention" and set(request) <= {"apply"} and isinstance(request.get("apply", False), bool):
                return 200, self.jobs.retention(apply=request.get("apply", False))
            if path == "/update/migrate" and request == {"schema": "2"}:
                self.jobs.migrate_copy("2")
                return 200, {"generation": self.jobs.current_generation(), "migration": "ready"}
            if path == "/update/switch" and set(request) == {"target"} and isinstance(request["target"], str):
                self.jobs.switch(request["target"])
                return 200, {"generation": self.jobs.current_generation()}
            if path == "/update/rollback" and request == {}:
                result = self.jobs.rollback()
                return 200, {"exported_jobs": result["exported_jobs"]}
        except StoreError as exc:
            return 409 if "active jobs" in str(exc) else 400, {"error": str(exc)}
        return 400, {"error": "request does not match this change route"}

    def page(self) -> bytes:
        return page.build(self.latest, live=True, sources=self.registry.entries(),
                          needs_pass=bool(self.passphrase)).encode("utf-8")

    def handle_compose(self, headers, body: bytes) -> tuple[int, dict]:
        if self.passphrase:
            sent = headers.get("X-Composer-Pass", "")
            if not hmac.compare_digest(sent.encode("utf-8"), self.passphrase.encode("utf-8")):
                return 403, {"error": "wrong or missing pass phrase"}
        try:
            req = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return 400, {"error": "send a JSON object"}
        if not isinstance(req, dict) or set(req) - {"sources", "lens", "insights"}:
            return 400, {"error": "send {\"sources\": [...], \"lens\": \"...\"}"}
        lens = req.get("lens")
        ids = req.get("sources")
        count = req.get("insights", DEFAULT_INSIGHTS)
        if not isinstance(lens, str) or not lens.strip() or len(lens) > LENS_MAX_CHARS:
            return 400, {"error": f"the lens must be 1 to {LENS_MAX_CHARS} characters"}
        if not isinstance(ids, list) or not ids or len(ids) > 8 or not all(isinstance(x, str) for x in ids):
            return 400, {"error": "name 1 to 8 sources"}
        if not isinstance(count, int) or isinstance(count, bool) or not 3 <= count <= 8:
            return 400, {"error": "insights must be from 3 to 8"}
        try:
            sources = self.registry.pick(ids)
        except RegistryError as exc:
            return 400, {"error": str(exc)}
        try:
            model = self.make_model()
            if hasattr(model, "ready"):
                model.ready()  # no key: say so before any feed is fetched
        except ProviderError as exc:
            return 503, {"error": str(exc)[:300]}
        if not self.lock.acquire(blocking=False):
            return 429, {"error": "a brief is already being composed; try again in a minute"}
        try:
            run = self.compose(lens=lens.strip(), sources=sources, model=model, count=count)
        except (pipeline.ComposeError, ProviderError, ValueError) as exc:
            return 502, {"error": str(exc)[:300]}
        finally:
            self.lock.release()
        self.latest = run["edition"]
        if self.out_dir is not None:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            (self.out_dir / "latest-edition.json").write_text(
                json.dumps(self.latest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return 200, self.latest


def handler_for(app: App, *, local_only: bool = True):
    class Handler(BaseHTTPRequestHandler):
        server_version = "composer"
        sys_version = ""
        timeout = 30  # a client that stops sending is dropped, not waited on forever

        def _refused(self, method: str) -> bool:
            problem = request_problem(method, self.headers, local_only=local_only)
            if problem:
                self._json(403, {"error": problem})
                return True
            return False

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, obj: dict) -> None:
            self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json")

        def do_GET(self):  # noqa: N802
            if self._refused("GET"):
                return
            if self.path in ("/", "/index.html"):
                self._send(200, app.page(), "text/html; charset=utf-8")
            elif self.path == "/api/latest":
                self._json(200, app.latest)
            elif self.path == "/health":
                self._json(200, app.jobs.health())
            elif self.path == "/shelf":
                self._json(200, app.jobs.index())
            elif self.path == "/latest":
                latest = app.jobs.latest()
                self._json(200, latest) if latest else self._json(404, {"error": "not found"})
            elif self.path.startswith("/status/"):
                try:
                    self._json(200, app.jobs.status(self.path.removeprefix("/status/")))
                except (OSError, ValueError, StoreError):
                    self._json(404, {"error": "not found"})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):  # noqa: N802
            if self._refused("POST"):
                return
            routes = {"/api/compose", "/compose", "/retention", "/update/migrate", "/update/switch", "/update/rollback"}
            if self.path not in routes and not any(self.path.startswith(prefix) for prefix in ("/save/", "/delete/", "/restore/")):
                return self._json(404, {"error": "not found"})
            if self.path == "/compose" and not self.headers.get("Origin"):
                return self._json(403, {"error": "compose requests need a same-origin Origin header"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length <= 0 or length > MAX_BODY:
                return self._json(413 if length > MAX_BODY else 400, {"error": "body missing or over 16 KB"})
            body = self.rfile.read(length)
            if self.path == "/compose":
                status, obj = app.submit_job(self.headers, body)
            elif self.path == "/api/compose":
                status, obj = app.handle_compose(self.headers, body)
            else:
                try:
                    request = json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    status, obj = 400, {"error": "send a JSON object"}
                else:
                    status, obj = app.change_job(self.headers, self.path, request)
            self._json(status, obj)

        def log_message(self, fmt, *args):  # one short line per request, no headers or bodies
            print(f"{self.address_string()} {self.command} {self.path[:200]} {args[1] if len(args) > 1 else ''}",
                  flush=True)

    return Handler


def check_bind(host: str, passphrase: str) -> None:
    if host not in LOOPBACK and not passphrase:
        raise SystemExit("refused: to listen on a non-local address, set COMPOSER_SERVER_PASS first "
                         "(anyone who can compose spends your API credit)")


def serve(app: App, host: str, port: int) -> None:
    check_bind(host, app.passphrase)
    httpd = ThreadingHTTPServer((host, port), handler_for(app, local_only=host in LOOPBACK))
    shown = "127.0.0.1" if host == "localhost" else (f"[{host}]" if ":" in host else host)
    print(f"composer serving on http://{shown}:{port}/  (Ctrl+C to stop)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def passphrase_from_env() -> str:
    return os.environ.get("COMPOSER_SERVER_PASS", "")
