"""Fail if the repository carries text that must not be published.

Three kinds of check, over every file in the working tree (and, when this is a git checkout,
every patch and commit message in its history):

1. Shapes: server paths, internal id shapes (timestamp job ids, dated run ids, message numbers)
   and credential shapes (API keys, access tokens, private-key blocks).
2. Words: a list of names that belong to the project's private setup. They are stored here as
   salted SHA-256 digests, so this public file does not spell them out. Every word-like token
   in a file (and each part of it split on . _ : -) is hashed and compared.
3. Your own list: set COMPOSER_DENYLIST to a file kept OUTSIDE the repository, one Python regex
   per line (case-insensitive; blank and # lines ignored).

Binary files: a PNG may hold only its picture (no text chunks); any other binary fails.
"""
import hashlib
import os
import re
import shutil
import subprocess
import unittest

from helpers import ROOT

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "briefs", "build", "dist", ".pytest_cache"}
SALT = "composer-banned-v1:"
BANNED_WORD_DIGESTS = {
    "99a7120affe56fef9942a87b7389de9d8bf32f8e013fca7b645acc80e7477616",
    "6ee8f093dca97e5d784c812f0b746eb1e9e51b8495a028e27178c1c0bfc41d26",
    "7a40ea84f6f5f5cfa871f6225e8be1509615ebe2fdebf4aff83f0b764c105761",
    "216b0ba531679d30132ce19bbca9006029f55dd43f3cb875c8c3f5883943a5ec",
    "d31351b0e27bb7a04434e1399e1edf18c29f0adff7c9928bdb89005e64cf8533",
    "cbbf28580cb387e5bd153f5a11d1b4a4745bfcf0e72c0ec85fd918ffd71afa05",
    "88499ae321a775e57d0ce3b4afdd82d50698b20d02ad61781435f1d74d269443",
    "07b905d18bad131f0536653ec712492ecf945f9eb7586c4ea539193cba5568a0",
    "b6446c6416431996ee3022327e69f418b59d37fa5319ff7af341d4fabf02c8b8",
    "f61bf2dbed52b20236b653bb33d864640d64c4cb677d25eea1521c9ca3c6a1c4",
    "1b6eaefd499b23cea6a7e3854edcfe51d9ab6cee2265b1efd33f7b5ee6828ef9",
    "f5bd3e51f3b06f498c0df2daecbb6756d60d4cd2d874a68a01bf5dfe58c05c72",
    "e0dc3fde9567331982695ad97ea88084b9fb966413d134c21f8c78c9710214d4",
    "577c81af46bf5822beca4e920de100b7ecdeadc7cfb9fba32677e3c28f24fbe6",
    "e7edb2c7e274cc610a59bf76e6ac95a6431faec1d9677450e18edab60be98b42",
    "379d489889b27b61dc460cdb7e284965e0f273948408823286be2607ff1e98d1",
    "df076493bbbac532a9456336544234b54b770a5e252bcac5a4b07bb87a67e072",
    "2e82240d639672f041907638b2c902120c214db7cde5ae5666bcffc4ed3a0bb9",
    "9174106ae46e93c189fe9bd4900ca3f1f1bbdc154b70246265e7524a159d4cc3",
    "337088e741f695d0de1651050594f1eab6c0c78ab60a1ccb0542f3cd9d78284b",
    "82e9aa36df98db4b183799bf33e36f0eb5a176a2ab6fae38c3dd3706ca44980f",
    "ff0690d6cfa4ffbb20f09eaf97650b1f7b269ac3a025510521643398b5f43f8d",
    "3c88c5224ca22a095353a0ca4193ad3997d82aece75c58b0f3284af153180b4a",
    "81b76b668218dc4d6324531a689376161229ada90a59ec2cde098fb82f91e29a",
}
TOKEN = re.compile(r"[A-Za-z0-9@][A-Za-z0-9@._:-]*")
PARTS = re.compile(r"[._:@-]+")
ALLOWED_HISTORY_TRAILER = "built by " + "S" + "al (gpt-5.6-terra)"

SHAPES = [
    ("server path", re.compile(r"(?<![\w.:/])/(?:s" r"rv|root|opt|var/www|var/lib|etc)/[\w.-]")),
    ("home path", re.compile(r"(?<![\w.:/])(?:/home/|/Users/)[\w.-]+")),
    ("api key shape", re.compile(r"\b(?:sk|pk|rk)-(?:ant-)?[A-Za-z0-9_-]{20,}")),
    ("access token shape", re.compile(r"\b(?:ghp|gho|ghs|github_pat|glpat|xox[abpr])[-_][A-Za-z0-9_-]{16,}")),
    ("cloud key shape", re.compile(r"\bAKIA[0-9A-Z]{16}\b|\bAIza[0-9A-Za-z_-]{30,}")),
    ("bot credential shape", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY" r"-----")),
    ("job id shape", re.compile(r"\b\d{8}T\d{6}Z-[0-9a-f]{6}\b", re.I)),
    ("run id shape", re.compile(r"\b20\d{2}-[01]\d-[0-3]\d-[0-2]\d[0-5]\d\b")),
    ("message number", re.compile(r"\bmsgs?\s?#?\d{3,6}\b", re.I)),
    ("our own records", re.compile(r"\bour (?:own )?(?:runs?|run records?|run logs?)\b", re.I)),
]


def word_hits(text: str) -> list[str]:
    hits = []
    for tok in TOKEN.findall(text):
        for word in {tok, *PARTS.split(tok)}:
            if word and hashlib.sha256((SALT + word.lower()).encode()).hexdigest() in BANNED_WORD_DIGESTS:
                hits.append(word)
    return hits


def shape_hits(text: str) -> list[str]:
    return [f"{label}: {m.group(0)[:24]}" for label, rx in SHAPES for m in rx.finditer(text)]


def denylist_hits(text: str) -> list[str]:
    path = os.environ.get("COMPOSER_DENYLIST")
    if not path:
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and re.search(line, text, re.I):
                out.append(f"deny-list pattern #{hashlib.sha256(line.encode()).hexdigest()[:8]}")
    return out


def png_text_chunks(data: bytes) -> list[str]:
    """Names of any chunk in a PNG that can carry text or metadata."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ["not a PNG"]
    out, at = [], 8
    allowed = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"sRGB", b"gAMA", b"pHYs", b"cHRM", b"sBIT"}
    while at + 8 <= len(data):
        length = int.from_bytes(data[at:at + 4], "big")
        kind = data[at + 4:at + 8]
        if kind not in allowed:
            out.append(kind.decode("latin-1"))
        at += 12 + length
    return out


def tree_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info")]
        for name in filenames:
            yield os.path.join(dirpath, name)


class BannedTextTests(unittest.TestCase):
    def test_the_checks_themselves_fire(self):
        self.assertTrue(word_hits("from the " + "sa" + "lamander box"))
        self.assertTrue(word_hits("na" + "te's newsletter"))
        self.assertTrue(shape_hits("see " + "/s" + "rv/x"))
        self.assertTrue(shape_hits("job 1999" + "0101T000000Z-abcdef"))
        self.assertTrue(shape_hits("run 2099-01-01" + "-0000"))
        self.assertTrue(shape_hits("key " + "sk-" + "ant-" + "a" * 24))
        self.assertFalse(word_hits("Composer reads the Google AI blog and the Google DeepMind blog."))
        self.assertFalse(shape_hits("composed on 2026-10-25, see https://example.org/a"))

    def test_working_tree_is_clean(self):
        problems = []
        for path in tree_files():
            rel = os.path.relpath(path, ROOT)
            if rel == ".git":
                continue  # linked worktrees use a gitdir pointer file, not public source
            with open(path, "rb") as fh:
                data = fh.read()
            if rel.endswith(".png"):
                bad = png_text_chunks(data)
                if bad:
                    problems.append(f"{rel}: PNG chunks {bad}")
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                problems.append(f"{rel}: not UTF-8 text and not a reviewed PNG")
                continue
            for hit in word_hits(text) + shape_hits(text) + denylist_hits(text):
                problems.append(f"{rel}: {hit}")
        self.assertEqual(problems, [])

    @unittest.skipUnless((ROOT / ".git").exists() and shutil.which("git"), "not a git checkout")
    def test_history_is_clean(self):
        if subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--is-inside-work-tree"],
                          capture_output=True).returncode:
            self.skipTest("git history is unavailable in this source-only test mount")
        log = subprocess.run(["git", "-C", str(ROOT), "log", "-p", "--all", "--format=%B", "--",
                              ".", ":(exclude)*.png"],
                             capture_output=True, text=True, errors="replace", check=True).stdout
        scanned = "\n".join(line for line in log.splitlines() if line != ALLOWED_HISTORY_TRAILER)
        problems = word_hits(scanned) + shape_hits(scanned) + denylist_hits(scanned)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
