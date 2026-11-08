"""A fake internet for the installer's fault tests: one HTTPS server that answers as github.com, api.github.com,
codeload.github.com, pypi.org, files.pythonhosted.org, www.python.org, registry.npmmirror.com and lensmith.ai, serving
the real pinned files, and breaks them on request.

  python fake_net.py --artifacts DIR --kit DIR --certs DIR --faults faults.json --log requests.jsonl [--port 443]

faults.json: {"rules": [{"host": "regex", "path": "regex", "action": ACTION, ...}], "composer_on_pypi": false}
A request is matched against the rules in order; the first match decides. Actions:
  status   answer with "status" (504, 503, 404 ...) and no file
  drop     the TLS handshake for that host fails (what a blocked host looks like to curl)
  stall    the handshake hangs for "seconds" (a black hole)
  corrupt  serve the file with one bit flipped (same size)
  slow     serve the file at "rate" bytes per second
  stallmid serve "after" bytes, then hang for "seconds" (a download that dies in the middle)
Nothing here is used outside tests."""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import re
import ssl
import sys
import threading
import time
import urllib.parse
from pathlib import Path

UV_IDS = {226708833: "uv-aarch64-apple-darwin.tar.gz", 226708838: "uv-aarch64-unknown-linux-gnu.tar.gz",
          226708873: "uv-x86_64-apple-darwin.tar.gz", 226708878: "uv-x86_64-unknown-linux-gnu.tar.gz"}
PBS = "cpython-3.12.9+20250205-{}-install_only_stripped.tar.gz"
PBS_IDS = {226609966: PBS.format("aarch64-apple-darwin"), 226609975: PBS.format("aarch64-unknown-linux-gnu"),
           226610558: PBS.format("x86_64-apple-darwin"), 226610613: PBS.format("x86_64-unknown-linux-gnu")}
HOSTS = ["raw.githubusercontent.com", "github.com", "api.github.com", "codeload.github.com", "objects.githubusercontent.com", "pypi.org",
         "files.pythonhosted.org", "www.python.org", "registry.npmmirror.com", "lensmith.ai"]

ART: Path
KIT: Path
CFG: dict = {}
LOCK = threading.Lock()
LOGF: Path


def log(entry: dict) -> None:
    with LOCK, LOGF.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def file_for(host: str, path: str, accept: str):
    """The file this address stands for, or None."""
    path = urllib.parse.unquote(path.split("?")[0])
    name = path.rsplit("/", 1)[-1]
    if host == "api.github.com":
        m = re.match(r"^/repos/(astral-sh/uv|astral-sh/python-build-standalone)/releases/assets/(\d+)$", path)
        if m and "octet-stream" in accept:
            n = {**UV_IDS, **PBS_IDS}.get(int(m.group(2)))
            return ART / n if n else None
        return None
    if host == "github.com":
        if re.match(r"^/astral-sh/uv/releases/download/0\.5\.29/", path) or \
                re.match(r"^/astral-sh/python-build-standalone/releases/download/20250205/", path):
            return ART / name
        if re.match(r"^/lensmith-ai/composer/releases/download/v[0-9.]+/", path):
            return KIT / name
        m = re.match(r"^/lensmith-ai/claim-seal/archive/([0-9a-f]{40})\.tar\.gz$", path)
        if m:
            return KIT / f"claim-seal-{m.group(1)}.tar.gz"
    if host == "raw.githubusercontent.com" and path == "/lensmith-ai/composer/main/install.sh":
        return Path(CFG.get("install_sh", "/nonexistent"))
    if host == "codeload.github.com":
        m = re.match(r"^/lensmith-ai/claim-seal/tar\.gz/([0-9a-f]{40})$", path)
        if m:
            return KIT / f"claim-seal-{m.group(1)}.tar.gz"
    if host == "registry.npmmirror.com" and path.startswith("/-/binary/python-build-standalone/20250205/"):
        return ART / name
    if host == "files.pythonhosted.org" and path.startswith("/packages/"):
        for d in (ART, KIT):
            if (d / name).is_file():
                return d / name
    if host == "www.python.org" and path == "/ftp/python/3.12.9/python-3.12.9-macos11.pkg":
        return ART / "python-3.12.9-macos11.pkg"
    if host == "lensmith.ai":
        m = re.match(r"^/composer/mirror/(uv|python-build-standalone/20250205|kit|python)/", path)
        if m:
            for d in (ART, KIT):
                if (d / name).is_file():
                    return d / name
        if path == "/composer/install.sh":
            return Path(CFG.get("install_sh", "/nonexistent"))
    return None


def simple_index(host: str, path: str):
    if host != "pypi.org":
        return None
    m = re.match(r"^/simple/([A-Za-z0-9_.-]+)/$", path)
    if not m:
        return None
    project = re.sub(r"[-_.]+", "-", m.group(1)).lower()
    prefix = {"certifi": "certifi-", "setuptools": "setuptools-", "lensmith-composer": "lensmith_composer-",
              "claim-seal": "claim_seal-"}.get(project)
    if prefix is None:
        return None
    if project == "lensmith-composer" and not CFG.get("composer_on_pypi", False):
        return None
    if project == "claim-seal" and not CFG.get("claim_seal_on_pypi", False):
        return None
    files = [p for p in sorted(KIT.glob(prefix + "*")) if p.suffix == ".whl"]
    rows = "".join(f'<a href="https://files.pythonhosted.org/packages/ab/cd/{p.name}#sha256='
                   f'{hashlib.sha256(p.read_bytes()).hexdigest()}">{p.name}</a><br>\n' for p in files)
    return f"<!doctype html><html><body>\n{rows}</body></html>".encode()


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def send_err(self, code: int, host: str, path: str):
        body = f"fake {code}".encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        log({"t": time.time(), "host": host, "path": path, "status": code, "bytes": 0})

    def do_GET(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        path = self.path
        accept = self.headers.get("Accept", "")
        action = None
        for rule in CFG.get("rules", []):
            if re.search(rule["host"], host) and re.search(rule.get("path", ".*"), path):
                action = rule
                break
        if action and action["action"] == "status":
            return self.send_err(int(action["status"]), host, path)
        idx = simple_index(host, path)
        if idx is not None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(idx)))
            self.end_headers()
            self.wfile.write(idx)
            log({"t": time.time(), "host": host, "path": path, "status": 200, "bytes": len(idx)})
            return
        f = file_for(host, path, accept)
        if f is None or not f.is_file():
            return self.send_err(404, host, path)
        data = f.read_bytes()
        if action and action["action"] == "corrupt":
            data = data[:-1] + bytes([data[-1] ^ 1])  # the right size, one wrong bit: what a bad mirror or a tamperer sends
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        sent = 0
        try:
            if action and action["action"] == "slow":
                rate = int(action["rate"])
                chunk = max(1024, rate // 20)
                for i in range(0, len(data), chunk):
                    self.wfile.write(data[i:i + chunk])
                    sent += len(data[i:i + chunk])
                    time.sleep(chunk / rate)
            elif action and action["action"] == "stallmid":
                cut = int(action["after"])
                self.wfile.write(data[:cut])
                self.wfile.flush()
                sent = cut
                time.sleep(float(action["seconds"]))
            else:
                self.wfile.write(data)
                sent = len(data)
        except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
            pass
        log({"t": time.time(), "host": host, "path": path, "status": 200, "bytes": sent, "of": len(data)})

    do_HEAD = do_GET


def main() -> int:
    global ART, KIT, CFG, LOGF
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--kit", required=True)
    ap.add_argument("--certs", required=True)
    ap.add_argument("--faults", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--port", type=int, default=443)
    a = ap.parse_args()
    ART, KIT, LOGF = Path(a.artifacts), Path(a.kit), Path(a.log)
    CFG = json.loads(Path(a.faults).read_text())
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(Path(a.certs) / "server.pem", Path(a.certs) / "server.key")

    def sni(sock, name, _ctx):
        for rule in CFG.get("rules", []):
            if name and re.search(rule["host"], name) and rule["action"] in ("drop", "stall") and not rule.get("path"):
                log({"t": time.time(), "host": name, "path": "(handshake)", "status": rule["action"], "bytes": 0})
                if rule["action"] == "stall":
                    time.sleep(float(rule.get("seconds", 120)))
                return ssl.ALERT_DESCRIPTION_HANDSHAKE_FAILURE
        return None
    ctx.sni_callback = sni
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", a.port), Handler)
    httpd.daemon_threads = True
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True, do_handshake_on_connect=False)
    # the handshake happens in each request's own thread (do_handshake_on_connect=False), so one stalled
    # handshake does not block the others
    httpd.handle_error = lambda *args: None
    print("fake net ready", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
