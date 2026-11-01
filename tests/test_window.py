import json
import re
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from composer import demo, window

from helpers import ROOT

SITE = ROOT / "docs" / "demo"
NETWORK_CALLS = re.compile(r"\bfetch\s*\(|XMLHttpRequest|WebSocket|EventSource|sendBeacon|\bimport\s*\(|importScripts")


class Refs(HTMLParser):
    """Every src/href in a page, with the tag it is on."""

    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("src", "href") and v is not None:
                self.refs.append((tag, v))


def refs(text):
    p = Refs()
    p.feed(text)
    return p.refs


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.ed = demo.load()
        self.html = window.window_html(self.ed, ["Google AI blog", "Google DeepMind blog"])

    def test_committed_site_matches_a_fresh_build(self):
        with tempfile.TemporaryDirectory() as d:
            written = window.write_site(d, self.ed)
            for path in written:
                rel = path.relative_to(d)
                self.assertEqual((SITE / rel).read_bytes(), path.read_bytes(),
                                 f"docs/demo/{rel} is stale: run `composer demo --site docs/demo`")
            committed = {p.relative_to(SITE) for p in SITE.rglob("*") if p.is_file()}
            self.assertEqual(committed, {p.relative_to(d) for p in written})

    def test_pages_load_only_their_own_files(self):
        for page in (SITE / "index.html", SITE / "window" / "index.html"):
            text = page.read_text(encoding="utf-8")
            csp = re.search(r'Content-Security-Policy" content="([^"]+)"', text).group(1)
            self.assertIn("default-src &#x27;none&#x27;", csp)
            self.assertIn("connect-src &#x27;none&#x27;", csp)
            for tag, ref in refs(text):
                if tag == "a" and ref.startswith("https://"):
                    continue  # a link a reader may click; nothing loads it
                self.assertNotRegex(ref, r"^[a-z]+:", f"{page.name}: {tag} {ref} leaves the site")
                target = (page.parent / ref.split("#")[0].split("?")[0]).resolve()
                self.assertTrue(target.is_file(), f"{page.name}: {ref} is missing")

    def test_scripts_and_styles_make_no_request_and_carry_no_comments(self):
        for path in sorted((SITE / "window").glob("*.*")) + [SITE / "frame.js", SITE / "site.css"]:
            if path.name == "index.html":
                continue
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertIsNone(NETWORK_CALLS.search(text))
                self.assertNotRegex(text, r"https?://")
                self.assertNotIn("/*", text)
                self.assertIsNone(re.search(r"(^|[\s;{}])//", text, re.M), "a line comment survived")

    def test_window_tells_the_recorded_run(self):
        data = json.loads(re.search(r'data-lw="([^"]+)"', self.html).group(1).replace("&quot;", '"')
                          .replace("&#x27;", "'").replace("&amp;", "&"))
        self.assertEqual(data["sources"], ["Google AI blog", "Google DeepMind blog"])
        self.assertEqual(data["rows"], ["Google AI blog", "Google DeepMind blog"])
        self.assertEqual(data["steps"][0]["text"], "compose started · 2 sources · system improvements lens")
        self.assertEqual(data["steps"][-1]["text"], "checked · 4 partly supported · 1 supported")
        self.assertEqual(self.html.count('class="lw-detail"'), 5)
        self.assertIn("6 of 6 checks agree", self.html)

    def test_cited_phrases_are_our_words_with_links_and_fingerprints(self):
        self.assertIn('<mark class="cmark">global map of distinct forest types</mark>', self.html)
        self.assertIn("fingerprint 5b6e82d2a96b", self.html)
        self.assertIn('href="https://deepmind.google/blog/beyond-tree-cover-mapping-the-worlds-forest-types/"', self.html)

    def test_a_source_missing_from_the_sheet_is_refused(self):
        with self.assertRaises(ValueError):
            window.window_html(self.ed, ["Google AI blog"])

    def test_text_is_escaped(self):
        ed = json.loads(json.dumps(self.ed))
        ed["cards"][0]["insight"] = "<script>alert(1)</script>"
        out = window.window_html(ed, ["Google AI blog", "Google DeepMind blog"])
        self.assertNotIn("<script>alert", out)


if __name__ == "__main__":
    unittest.main()
