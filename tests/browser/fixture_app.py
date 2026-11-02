"""The real Composer server, offline, for the browser flow test (tests/browser/parity_flow.mjs).

  python tests/browser/fixture_app.py        prints one JSON line {"app": ..., "blog": ...}, then serves until killed

What it starts, all on 127.0.0.1 and in a new temporary folder:
  - a local HTTPS site with a made-up blog: a page that advertises its feed (and a comments feed), the two feeds, and
    the feeds of the two bundled sources (their ids are pointed at this site, so nothing leaves this machine). Its
    certificate is made for this run with `openssl` and trusted only by this process (SSL_CERT_FILE);
    COMPOSER_ALLOW_PRIVATE_FETCH=1 lets the guarded fetch read 127.0.0.1 on purpose. Every other fetch rule (https
    only, redirects, size and time limits, no proxies) is the same as for a real feed;
  - the app server (composer.server.App, the same handler `composer serve` uses) with a sources file, a packages
    file and a lens folder in the temporary folder;
  - a made-up model: it writes a brief that cites titles from the feeds it was shown, and answers the claim checker
    from a table (claim-seal's ReplayJudge), so the brief runs through the real pipeline, check and seal with no key.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

WORK = Path(tempfile.mkdtemp(prefix="composer-browser-"))


def rss(title: str, items: list[tuple[str, str]]) -> bytes:
    rows = "".join(f"<item><title>{t}</title><link>https://example.org/{n}</link><description>{d}</description>"
                   f"<pubDate>Mon, 02 Nov 2026 0{n}:00:00 GMT</pubDate></item>" for n, (t, d) in enumerate(items, 1))
    return (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{title}</title>'
            f"<link>https://example.org/</link><description>A made-up feed for a test.</description>{rows}"
            "</channel></rss>").encode("utf-8")


SITE = {
    "/blog": (b'<!doctype html><html><head><title>Tidewater Field Notes</title>'
              b'<link rel="alternate" type="application/rss+xml" title="Tidewater Field Notes" href="/blog/feed.xml">'
              b'<link rel="alternate" type="application/rss+xml" title="Comments" href="/blog/comments/feed/">'
              b"</head><body><h1>Field notes</h1></body></html>", "text/html"),
    "/blog/feed.xml": (rss("Tidewater Field Notes", [
        ("Tidewater opens its river gauge readings", "The gauges along the river now publish a reading every hour."),
        ("Volunteers mapped forty culverts this spring", "Forty culverts were mapped by volunteers in eight weeks."),
        ("Why the gauges sit on old bridge piers", "Old bridge piers give a stable mount above flood level.")]),
        "application/rss+xml"),
    "/blog/comments/feed/": (rss("Comments", [("Comment on the gauges by a reader", "Nice work.")]),
                             "application/rss+xml"),
    "/lab-a/feed.xml": (rss("Lab A", [
        ("Lab A releases a small open model for phones", "The model runs on a phone with no network."),
        ("Lab A publishes its evaluation notes", "The notes list every test the model was given.")]),
        "application/rss+xml"),
    "/lab-b/feed.xml": (rss("Lab B", [
        ("Lab B shares a dataset of river sounds", "The dataset holds ten thousand recordings of rivers."),
        ("Lab B explains how it labels audio", "Each clip is labelled by two people who must agree.")]),
        "application/rss+xml"),
}


class Site(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body, ctype = SITE.get(self.path) or SITE.get(self.path.rstrip("/")) or (b"not here", "text/plain")
        self.send_response(200 if body != b"not here" else 404)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def start_site() -> int:
    cert, key = WORK / "cert.pem", WORK / "key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=127.0.0.1",
                    "-addext", "subjectAltName=IP:127.0.0.1", "-addext", "basicConstraints=critical,CA:TRUE",
                    "-keyout", str(key), "-out", str(cert)], check=True, capture_output=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Site)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert), str(key))
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    os.environ["SSL_CERT_FILE"] = str(cert)
    os.environ["COMPOSER_ALLOW_PRIVATE_FETCH"] = "1"
    return httpd.server_address[1]


_SECTION = re.compile(r"^\[SOURCE ([a-z0-9-]+)\] .*?\n(.*?)\n\[END SOURCE \1\]", re.M | re.S)


class FixtureModel:
    """Writes a brief from the titles in the prompt; answers the claim checker from the table it fills as it writes."""

    name = "fixture-model"

    def __init__(self):
        self.answers: dict = {}

    def __call__(self, prompt: str, timeout=None):
        if not prompt.startswith("You write a short, sourced brief"):
            from claim_seal.adapters import ReplayJudge
            return ReplayJudge(self.answers)(prompt, timeout=timeout)
        count = int(re.search(r"Write exactly (\d+) items", prompt).group(1))
        material = prompt.split("SOURCE MATERIAL FOLLOWS.", 1)[1]
        rows = []
        for source_id, body in _SECTION.findall(material):
            try:
                rows += [(source_id, r) for r in json.loads(body)]
            except json.JSONDecodeError:
                continue
        rows = rows[:count]
        items = []
        for n, (source_id, row) in enumerate(rows, 1):
            insight = f"Finding {n}: {row['title'][:60]}"
            items.append({"insight": insight, "why_it_matters": f"Single source: {row['description'][:150]}",
                          "detail": [row["description"][:150]],
                          "sources": [{"id": source_id, "ref": row["title"]}]})
            quote = row["description"][:40]
            self.answers[insight] = {"verdict": "supported", "why": "The feed says so.", "relation": "says",
                                     "strength": 80,
                                     "citation_spans": [{"citation_index": 0, "span_quote": quote,
                                                         "span_relation": "says"}],
                                     "evidence_spans": [{"citation_index": 0, "support_span": quote}]}
        connection = {"headline": "The sources each publish their own measurements in the open.",
                      "confidence": "plausible", "why": "Each feed describes data shared openly.",
                      "sources": [{"id": rows[0][0], "ref": rows[0][1]["title"]},
                                  {"id": rows[-1][0], "ref": rows[-1][1]["title"]}]}
        self.answers[connection["headline"]] = {"verdict": "partial", "why": "Each feed shows it in one way.",
                                                "relation": "implies", "strength": 50}
        script = " ".join(f"Item {n}. {it['insight']}. {it['why_it_matters']}" for n, it in enumerate(items, 1))
        transcript = ("Here is the brief. " + script + " That is the brief, read from the feeds you chose. ") * 2
        return json.dumps({"items": items, "connection": connection, "transcript": transcript})

    def ready(self):
        return None


if __name__ == "__main__":
    import signal

    def stop(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    port = start_site()
    from composer import lenses, server, settings, sources_registry
    from composer.registry import Registry

    base = f"https://127.0.0.1:{port}"
    sources_file = WORK / "sources.json"
    sources_file.write_text(json.dumps({"schema": "composer-sources/v1", "sources": [
        {"id": "google-ai", "label": "Lab A notes", "kind": "rss-or-atom", "url": f"{base}/lab-a/feed.xml"},
        {"id": "deepmind", "label": "Lab B notes", "kind": "rss-or-atom", "url": f"{base}/lab-b/feed.xml"}]}))
    service = sources_registry.SourceService(sources_file,
                                             packages=sources_registry.PackageService(WORK / "packages.json"))
    model = FixtureModel()
    app = server.App(Registry.load(str(sources_file)), lambda: model, data_root=WORK / "data",
                     settings={"narration": dict(settings.DEFAULTS["narration"])}, source_service=service,
                     lens_store=lenses.LensStore(WORK / "lenses"))
    quiet_handler = type("Quiet", (server.handler_for(app),), {"log_message": lambda *a: None})
    httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), quiet_handler)
    print(json.dumps({"app": f"http://127.0.0.1:{httpd.server_address[1]}/", "blog": f"{base}/blog",
                      "work": str(WORK)}), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        shutil.rmtree(WORK, ignore_errors=True)
