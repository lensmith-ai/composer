"""`composer serve`: the always-on tier. A small web server that shows the latest brief and,
with a key in its environment, composes new ones from a form.

Safe defaults:
  - It listens on 127.0.0.1 only, unless you pass --host.
  - On any other address it refuses to start without COMPOSER_SERVER_PASS set; every compose
    request must then send that phrase in the X-Composer-Pass header. Anyone who can compose
    spends your API credit, so do not skip this.
  - One brief at a time; a second request while one runs gets 429.
  - Request bodies over 16 KB, unknown sources and long lenses are refused before any fetch.
  - It is a plain standard-library server: put a TLS-terminating proxy in front of it before
    you expose it to the internet.
"""
from __future__ import annotations

import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import demo, page, pipeline
from .prompt import DEFAULT_INSIGHTS, LENS_MAX_CHARS
from .providers import ProviderError
from .registry import RegistryError

MAX_BODY = 16 * 1024
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


class App:
    def __init__(self, registry, make_model, *, out_dir: Path | None = None, passphrase: str = "",
                 compose=pipeline.compose):
        self.registry = registry
        self.make_model = make_model
        self.out_dir = out_dir
        self.passphrase = passphrase
        self.compose = compose
        self.lock = threading.Lock()
        self.latest = demo.load()

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


def handler_for(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "composer"
        sys_version = ""

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
            if self.path in ("/", "/index.html"):
                self._send(200, app.page(), "text/html; charset=utf-8")
            elif self.path == "/api/latest":
                self._json(200, app.latest)
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):  # noqa: N802
            if self.path != "/api/compose":
                return self._json(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length <= 0 or length > MAX_BODY:
                return self._json(413 if length > MAX_BODY else 400, {"error": "body missing or over 16 KB"})
            status, obj = app.handle_compose(self.headers, self.rfile.read(length))
            self._json(status, obj)

        def log_message(self, fmt, *args):  # one short line per request, no headers or bodies
            print(f"{self.address_string()} {self.command} {self.path} {args[1] if len(args) > 1 else ''}")

    return Handler


def check_bind(host: str, passphrase: str) -> None:
    if host not in LOOPBACK and not passphrase:
        raise SystemExit("refused: to listen on a non-local address, set COMPOSER_SERVER_PASS first "
                         "(anyone who can compose spends your API credit)")


def serve(app: App, host: str, port: int) -> None:
    check_bind(host, app.passphrase)
    httpd = ThreadingHTTPServer((host, port), handler_for(app))
    print(f"composer serving on http://{host}:{port}/  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def passphrase_from_env() -> str:
    return os.environ.get("COMPOSER_SERVER_PASS", "")
