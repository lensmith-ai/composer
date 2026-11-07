"""The app page: Composer's own phone-width interface, served at /app/.

The files live in composer/web/app/ and are served from a fixed list (no path is ever joined
from the request). The page talks to the engine on the same origin only: /compose, /status/<job>,
/health, /source/probe, /source/register and the data files under /data/.

Headers for every app file:
  - a Content-Security-Policy that allows only this origin (no outside request of any kind,
    no inline script or style, no plugins), lets the page frame itself (the finished brief is
    shown in a same-origin frame while it lands) and nobody else frame it;
  - nosniff, no referrer, no caching, same-origin resource policy.
"""
from __future__ import annotations

from pathlib import Path

APP_DIR = Path(__file__).with_name("web") / "app"
PREFIX = "/app/"
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8"}
FILES = ("index.html", "app.js", "app.css", "boot.js", "boot-note.js", "claimseal.js", "sand-engine.js",
         "composer-entry-transition.js", "entry-transition.css")
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; "
       "connect-src 'self'; font-src 'self'; frame-src 'self'; frame-ancestors 'self'; form-action 'none'; "
       "base-uri 'none'; object-src 'none'")
HEADERS = (("Content-Security-Policy", CSP), ("X-Content-Type-Options", "nosniff"),
           ("Referrer-Policy", "no-referrer"), ("X-Frame-Options", "SAMEORIGIN"),
           ("Cross-Origin-Resource-Policy", "same-origin"), ("Cache-Control", "no-store"))


def lookup(path: str) -> tuple[bytes, str] | None:
    """The body and content type for an app URL, or None when the URL is not an app file.
    The query string is ignored (the page reads ?job=, ?demo and its view flags itself)."""
    path = path.split("?", 1)[0].split("#", 1)[0]
    if path == PREFIX.rstrip("/"):
        return None
    if not path.startswith(PREFIX):
        return None
    name = path[len(PREFIX):] or "index.html"
    if name not in FILES:
        return None
    file = APP_DIR / name
    return file.read_bytes(), TYPES[file.suffix]


def send(handler, path: str, *, head: bool = False) -> bool:
    """Answer an app URL on a BaseHTTPRequestHandler. True when it was an app URL."""
    if path.split("?", 1)[0] == PREFIX.rstrip("/"):
        handler.send_response(301)
        handler.send_header("Location", PREFIX)
        handler.send_header("Content-Length", "0")
        handler.end_headers()
        return True
    found = lookup(path)
    if found is None:
        return False
    body, ctype = found
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    for name, value in HEADERS:
        handler.send_header(name, value)
    handler.end_headers()
    if not head:
        handler.wfile.write(body)
    return True
