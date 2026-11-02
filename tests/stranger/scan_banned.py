"""Scan the BUILT release files for text that must not be published.

  python3 scan_banned.py RESULTS REPORT FILE [FILE ...] [--words-from TEST_BANNED_PY]

Opens every archive (.tar.gz, .whl/.zip) and scans each member as text, plus plain files (SHA256SUMS, SBOM JSON):
  - private names: every word-like token (and its parts split on . _ : -) is hashed with the same salt as
    tests/test_banned.py and compared with a list of digests, so this file does not spell the names out. The list
    holds the project's private agent and tool names and the name of a creator the public pages must not cite; with
    --words-from, the digests in the commit's own tests/test_banned.py are added;
  - shapes: server paths, home paths, internal run and job id shapes, message numbers, and wording that points
    at private run records;
  - credentials: API key, access token and private-key block shapes.
A binary member (not UTF-8) is reported unless it is a PNG with no text chunks. Writes one row "artifact.banned_text"
to RESULTS and the full hit list (file, line, kind; never the matched private name) to REPORT.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import tarfile
import time
import zipfile
from pathlib import Path

SALT = "composer-banned-v1:"
DIGESTS = {
    "88499ae321a775e57d0ce3b4afdd82d50698b20d02ad61781435f1d74d269443",
    "7a40ea84f6f5f5cfa871f6225e8be1509615ebe2fdebf4aff83f0b764c105761",
    "216b0ba531679d30132ce19bbca9006029f55dd43f3cb875c8c3f5883943a5ec",
    "f5bd3e51f3b06f498c0df2daecbb6756d60d4cd2d874a68a01bf5dfe58c05c72",
    "99a7120affe56fef9942a87b7389de9d8bf32f8e013fca7b645acc80e7477616",
    "d31351b0e27bb7a04434e1399e1edf18c29f0adff7c9928bdb89005e64cf8533",
    "cbbf28580cb387e5bd153f5a11d1b4a4745bfcf0e72c0ec85fd918ffd71afa05",
    "1b6eaefd499b23cea6a7e3854edcfe51d9ab6cee2265b1efd33f7b5ee6828ef9",
}
TOKEN = re.compile(r"[A-Za-z0-9@][A-Za-z0-9@._:-]*")
PARTS = re.compile(r"[._:@-]+")
SHAPES = [
    ("server path", re.compile(r"(?<![\w.:/])/(?:s" r"rv|root|opt|var/www|var/lib|etc)/[\w.-]")),
    ("home path", re.compile(r"(?<![\w.:/])(?:/home/|/Users/)[\w.-]+")),
    ("api key shape", re.compile(r"\b(?:sk|pk|rk)-(?:ant-)?[A-Za-z0-9_-]{20,}")),
    ("access token shape", re.compile(r"\b(?:ghp|gho|ghs|github_pat|glpat|xox[abpr])[-_][A-Za-z0-9_-]{16,}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY" r"-----")),
    ("job id shape", re.compile(r"\b\d{8}T\d{6}Z-[0-9a-f]{6}\b", re.I)),
    ("run id shape", re.compile(r"\b20\d{2}-[01]\d-[0-3]\d-[0-2]\d[0-5]\d\b")),
    ("message number", re.compile(r"\bmsgs?\s?#?\d{3,6}\b", re.I)),
    ("our own records", re.compile(r"\bour (?:own )?(?:runs?|run records?|run logs?)\b", re.I)),
]
PNG = b"\x89PNG\r\n\x1a\n"


def png_ok(data: bytes) -> bool:
    if not data.startswith(PNG):
        return False
    i = 8
    while i + 8 <= len(data):
        n = int.from_bytes(data[i:i + 4], "big")
        kind = data[i + 4:i + 8]
        if kind in (b"tEXt", b"zTXt", b"iTXt"):
            return False
        i += 12 + n
    return True


def scan_text(name: str, text: str, hits: list) -> None:
    for no, line in enumerate(text.splitlines(), 1):
        for kind, rx in SHAPES:
            if rx.search(line):
                hits.append({"file": name, "line": no, "kind": kind})
        for tok in TOKEN.findall(line):
            for word in {tok, *PARTS.split(tok)}:
                if word and hashlib.sha256((SALT + word.lower()).encode()).hexdigest() in DIGESTS:
                    hits.append({"file": name, "line": no, "kind": "private name (digest match)"})


def scan_bytes(name: str, data: bytes, hits: list) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        if not png_ok(data):
            hits.append({"file": name, "line": 0, "kind": "binary file that is not a plain PNG"})
        return
    scan_text(name, text, hits)


def members(path: Path):
    if path.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path, "r:gz") as tar:
            for m in tar.getmembers():
                if m.isfile():
                    yield f"{path.name}!{m.name}", tar.extractfile(m).read()
    elif path.suffix in (".whl", ".zip"):
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if not info.is_dir():
                    yield f"{path.name}!{info.filename}", z.read(info)
    else:
        yield path.name, path.read_bytes()


def main(argv: list[str]) -> int:
    if "--words-from" in argv:
        i = argv.index("--words-from")
        src = Path(argv[i + 1])
        if src.is_file():
            block = src.read_text(encoding="utf-8").split("BANNED_WORD_DIGESTS", 1)[-1].split("}", 1)[0]
            DIGESTS.update(re.findall(r"[0-9a-f]{64}", block))
        del argv[i:i + 2]
    results, report, files = argv[0], argv[1], [Path(p) for p in argv[2:]]
    hits: list = []
    scanned = 0
    for f in files:
        for name, data in members(f):
            scanned += 1
            scan_bytes(name, data, hits)
    Path(report).write_text(json.dumps({"files": [f.name for f in files], "members_scanned": scanned,
                                        "hits": hits}, indent=1) + "\n", encoding="utf-8")
    if not scanned:
        status, reason = "fail", "nothing was scanned"
    elif hits:
        where = "; ".join(f"{h['file']}:{h['line']} {h['kind']}" for h in hits[:8])
        status, reason = "fail", f"{len(hits)} hits in {scanned} files: {where}"
    else:
        status, reason = "pass", (f"{scanned} files in {', '.join(f.name for f in files)}: no private names "
                                  f"({len(DIGESTS)} digests), server or home paths, run or job ids, private-record wording or credential shapes")
    with open(results, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "id": "artifact.banned_text",
                             "status": status, "reason": reason}) + "\n")
    print(f"banned-text scan: {status}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
