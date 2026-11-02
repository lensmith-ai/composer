import json
import re
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from composer import demo, window

from helpers import ROOT

SITE = ROOT / "docs" / "demo"
SHEET = [s["label"] for s in json.loads((ROOT / "composer" / "sources.json").read_text("utf-8"))["sources"]]
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
        self.html = window.window_html(self.ed, SHEET)

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
        self.assertEqual(data["sources"], SHEET)
        self.assertEqual(data["rows"], SHEET)
        self.assertEqual(data["steps"][0]["text"], "compose started · 6 sources · system improvements lens")
        self.assertEqual(data["steps"][-1]["text"], "checked · 2 supported · 3 partly supported")
        self.assertEqual(self.html.count('class="lw-detail"'), 5)
        self.assertIn("6 of 6 checks agree", self.html)

    def test_cited_phrases_are_our_words_with_links_and_fingerprints(self):
        self.assertIn('<mark class="cmark">Hugging Face frames Granite Switch updates as software updates.</mark>', self.html)
        self.assertIn("fingerprint 5e45f9194e69", self.html)
        self.assertIn('href="https://huggingface.co/blog/ibm-granite/granite-switch-4-1-1"', self.html)

    def test_six_spools_keep_their_names_apart(self):
        # six sources share the drawing's width: each name must fit its own share, or the names print over each other
        names = re.findall(r'<text class="lname" x="([\d.]+)" y="(\d+)">([^<]*)</text>', self.html)
        self.assertEqual(len({x for x, _, _ in names}), 6)
        share = (340 - 40) / 6
        for x, _, text in names:
            self.assertLessEqual(len(text) * window.NAME_CHAR_W, share, text)
        self.assertIn("MICROSOFT", [t for _, _, t in names])
        self.assertNotIn("items</text>", self.html.split('id="loom"')[1].split("</svg>")[0])
        # two sources keep the wide spool with the full name and "5 items"
        two = dict(self.ed, sources=self.ed["sources"][:2],
                   cards=[dict(c, citations=[x for x in c["citations"] if x["label"] in SHEET[:2]]) for c in self.ed["cards"]])
        wide = window.loom_svg(two)
        self.assertIn(">GOOGLE DEEPMIND BLOG</text>", wide)
        self.assertIn(">5 items</text>", wide)

    def test_an_undetermined_relation_reads_cites(self):
        self.assertIn("Microsoft Research blog cites this", self.html)
        self.assertNotIn("undetermined this", self.html)
        self.assertEqual(window.shown_relation("says"), "says")
        self.assertEqual(window.shown_relation(None), "cites")

    def test_a_source_missing_from_the_sheet_is_refused(self):
        with self.assertRaises(ValueError):
            window.window_html(self.ed, SHEET[:-1])

    def test_text_is_escaped(self):
        ed = json.loads(json.dumps(self.ed))
        ed["cards"][0]["insight"] = "<script>alert(1)</script>"
        out = window.window_html(ed, SHEET)
        self.assertNotIn("<script>alert", out)


if __name__ == "__main__":
    unittest.main()
