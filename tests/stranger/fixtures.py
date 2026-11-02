"""Made-up services for the stranger test, so no step needs the internet or a model key.

  python -I -B fixtures.py CERT KEY LOG [--site-port 8443] [--model-port 8790]

Both listen on 127.0.0.1 only, inside the test machine:
  - a small HTTPS site (certificate made for the run; the app is told to trust it through SSL_CERT_FILE and to allow a
    local address through COMPOSER_ALLOW_PRIVATE_FETCH=1, the documented switch for reading a feed on purpose from
    this machine): a blog page that advertises its feed (and a comments feed), and the feeds themselves;
  - a model with the OpenAI chat-completions shape at /v1 (the kind of endpoint a local Ollama or LM Studio server
    offers). It writes a brief that cites titles from the feeds in the prompt and answers the claim checker from the
    table it filled while writing, so the brief goes through the real pipeline, check and seal.
It prints one JSON line with the addresses, then serves until it is stopped. Every request is appended to LOG as one
JSON line (path and the first words of the prompt), so the test can show which service the app called.
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOCK = threading.Lock()
LOG_PATH = ""


def log(row: dict) -> None:
    row["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with LOCK, open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def rss(title: str, items: list[tuple[str, str]]) -> bytes:
    rows = "".join(
        f"<item><title>{t}</title><link>https://example.org/tidewater/{n}</link><description>{d}</description>"
        f"<pubDate>Mon, 02 Nov 2026 0{n}:00:00 GMT</pubDate></item>" for n, (t, d) in enumerate(items, 1))
    return (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{title}</title>'
            f"<link>https://example.org/</link><description>A made-up feed for a test.</description>{rows}"
            "</channel></rss>").encode("utf-8")


FEED_ITEMS = [
    ("Tidewater opens its river gauge readings", "The gauges along the river now publish a reading every hour."),
    ("Volunteers mapped forty culverts this spring", "Forty culverts were mapped by volunteers in eight weeks."),
    ("Why the gauges sit on old bridge piers", "Old bridge piers give a stable mount above flood level."),
    ("The flood map now shows every gauge", "Each gauge appears on the public flood map with its last reading."),
    ("Schools borrow the gauge data for lessons", "Three schools use the hourly readings in science lessons."),
]
SECOND_ITEMS = [
    ("Harbor sensors report water temperature", "Harbor sensors now report the water temperature every ten minutes."),
    ("A ferry route changes for the winter", "The winter ferry route skips the north pier from December."),
    ("The harbor publishes its tide tables early", "Tide tables for next year are out three months early."),
]
def blog(path: str, title: str) -> dict:
    """A blog page that advertises its feed and a comments feed, and the two feeds."""
    page = (f'<!doctype html><html><head><title>{title}</title>'
            f'<link rel="alternate" type="application/rss+xml" title="{title}" href="{path}/feed.xml">'
            f'<link rel="alternate" type="application/rss+xml" title="Comments" href="{path}/comments/feed/">'
            "</head><body><h1>Field notes</h1></body></html>").encode("utf-8")
    return {path: (page, "text/html"),
            f"{path}/feed.xml": (rss(title, FEED_ITEMS), "application/rss+xml"),
            f"{path}/comments/feed/": (rss("Comments", [("Comment on the gauges by a reader", "Nice work.")]),
                                       "application/rss+xml")}


# /blog and /blog-2 .. /blog-4: one page per browser pass, so each pass adds a source of its own
SITE = {**blog("/blog", "Tidewater Field Notes"),
        **{k: v for n in range(2, 5) for k, v in blog(f"/blog-{n}", f"Tidewater Field Notes {n}").items()},
        "/harbor/feed.xml": (rss("Harbor Log", SECOND_ITEMS), "application/rss+xml")}


class Site(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        hit = SITE.get(self.path) or SITE.get(self.path.rstrip("/"))
        log({"service": "site", "path": self.path, "status": 200 if hit else 404})
        body, ctype = hit or (b"not here", "text/plain")
        self.send_response(200 if hit else 404)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


_SECTION = re.compile(r"^\[SOURCE ([a-z0-9-]+)\] .*?\n(.*?)\n\[END SOURCE \1\]", re.M | re.S)
_CLAIM = re.compile(r"^CLAIM (\d+):\n  (.*)$", re.M)
_DATA_BLOCK = re.compile(r"<<<([A-Z0-9_ -]+) BEGIN>>>.*?<<<\1 END>>>", re.S)


class Model:
    """Writes a brief from the titles in the prompt; answers the checker from the table it fills as it writes."""

    def __init__(self):
        self.answers: dict = {}
        self.lock = threading.Lock()

    def brief(self, prompt: str) -> str:
        count = int(re.search(r"Write exactly (\d+) items", prompt).group(1))
        material = prompt.split("SOURCE MATERIAL FOLLOWS.", 1)[1]
        rows = []
        for source_id, body in _SECTION.findall(material):
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                continue
            rows += [(source_id, r) for r in parsed if isinstance(r, dict) and r.get("title")]
        rows = rows[:count]
        if not rows:
            raise ValueError("the prompt carries no feed items")
        items = []
        for n, (source_id, row) in enumerate(rows, 1):
            desc = str(row.get("description") or row.get("summary") or row["title"])
            insight = f"Finding {n}: {row['title'][:60]}"
            items.append({"insight": insight, "why_it_matters": f"Single source: {desc[:150]}",
                          "detail": [desc[:150]], "sources": [{"id": source_id, "ref": row["title"]}]})
            quote = desc[:40]
            with self.lock:
                self.answers[insight] = {
                    "verdict": "supported", "why": "The feed says so.", "relation": "says", "strength": 80,
                    "citation_spans": [{"citation_index": 0, "span_quote": quote, "span_relation": "says"}],
                    "evidence_spans": [{"citation_index": 0, "support_span": quote}]}
        connection = {"headline": "Each source publishes its own measurements in the open.",
                      "confidence": "plausible", "why": "Each feed describes data shared openly.",
                      "sources": [{"id": rows[0][0], "ref": rows[0][1]["title"]},
                                  {"id": rows[-1][0], "ref": rows[-1][1]["title"]}]}
        with self.lock:
            self.answers[connection["headline"]] = {"verdict": "partial", "why": "Each feed shows it in one way.",
                                                    "relation": "implies", "strength": 50}
        script = " ".join(f"Item {n}. {it['insight']}. {it['why_it_matters']}" for n, it in enumerate(items, 1))
        transcript = ("Here is the brief. " + script + " That is the brief, read from the feeds you chose. ") * 2
        return json.dumps({"items": items, "connection": connection, "transcript": transcript})

    def judge(self, prompt: str) -> str:
        instructions = _DATA_BLOCK.sub("", prompt)
        if "Judge only the delimited fetched excerpts." in instructions:
            return json.dumps({})
        verdicts = []
        with self.lock:
            table = {" ".join(k.split()): v for k, v in self.answers.items()}
        for number, text in _CLAIM.findall(instructions):
            entry = table.get(" ".join(text.split()))
            if isinstance(entry, dict):
                verdicts.append(dict(entry, claim=int(number)))
        return json.dumps({"verdicts": verdicts})

    def reply(self, prompt: str) -> str:
        if prompt.startswith("You write a short, sourced brief"):
            return self.brief(prompt)
        if "CLAIM 1:" in prompt or "Judge only" in prompt:
            return self.judge(prompt)
        return "OK"


MODEL = Model()


class ModelHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, doc: dict) -> None:
        body = json.dumps(doc).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        log({"service": "model", "path": self.path})
        if self.path.rstrip("/") == "/v1/models":
            return self._send(200, {"object": "list", "data": [{"id": "fixture-model", "object": "model"}]})
        return self._send(404, {"error": {"type": "not_found", "message": "not here"}})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(length).decode("utf-8"))
            prompt = req["messages"][-1]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            log({"service": "model", "path": self.path, "status": 400})
            return self._send(400, {"error": {"type": "bad_request", "message": "send a chat-completions body"}})
        if not self.path.rstrip("/").endswith("/chat/completions"):
            log({"service": "model", "path": self.path, "status": 404})
            return self._send(404, {"error": {"type": "not_found", "message": "not here"}})
        try:
            text = MODEL.reply(prompt)
            status = 200
        except Exception as exc:  # noqa: BLE001 - a test double reports, never crashes
            log({"service": "model", "path": self.path, "status": 500, "error": str(exc)[:200]})
            return self._send(500, {"error": {"type": "fixture_error", "message": str(exc)[:200]}})
        log({"service": "model", "path": self.path, "status": status, "prompt": " ".join(prompt.split()[:8])})
        return self._send(200, {"id": "fixture", "object": "chat.completion", "model": req.get("model") or "fixture-model",
                                "choices": [{"index": 0, "finish_reason": "stop",
                                             "message": {"role": "assistant", "content": text}}],
                                "usage": {"prompt_tokens": len(prompt.split()), "completion_tokens": len(text.split())}})

    def log_message(self, *args):
        pass


def main() -> int:
    global LOG_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("cert")
    ap.add_argument("key")
    ap.add_argument("log")
    ap.add_argument("--site-port", type=int, default=8443)
    ap.add_argument("--model-port", type=int, default=8790)
    args = ap.parse_args()
    LOG_PATH = args.log
    site = ThreadingHTTPServer(("127.0.0.1", args.site_port), Site)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(args.cert, args.key)
    site.socket = ctx.wrap_socket(site.socket, server_side=True)
    model = ThreadingHTTPServer(("127.0.0.1", args.model_port), ModelHandler)
    for server in (site, model):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    print(json.dumps({"blog": f"https://127.0.0.1:{args.site_port}/blog",
                      "feed": f"https://127.0.0.1:{args.site_port}/blog/feed.xml",
                      "feed2": f"https://127.0.0.1:{args.site_port}/harbor/feed.xml",
                      "model": f"http://127.0.0.1:{args.model_port}/v1"}), flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
