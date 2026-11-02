"""Every brief says it was written by AI: "AI-written summary; check the source." on the one-file brief page and
on the app page, as plain text that needs no script and no tap. (EU AI Act Article 50(4) asks for this on AI-written
text published about matters of public interest; it also tells every reader the check is a model too.)"""
import unittest
from html.parser import HTMLParser

from composer import demo, page

from helpers import ROOT

NOTE = "AI-written summary; check the source."


class _Order(HTMLParser):
    """The order of: the note's paragraph, the edition element, and the header."""

    def __init__(self):
        super().__init__()
        self.events = []
        self._in_note = False
        self.note_text = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id") in ("ai-note", "aiNote"):
            self.events.append("note")
            self._in_note = True
        elif a.get("id") in ("edition",):
            self.events.append("edition")

    def handle_endtag(self, tag):
        if tag in ("p", "div"):
            self._in_note = False

    def handle_data(self, data):
        if self._in_note:
            self.note_text += data


class BriefPageTests(unittest.TestCase):
    def test_the_constant_is_the_agreed_line(self):
        self.assertEqual(page.AI_NOTE, NOTE)

    def test_each_kind_of_brief_page_carries_the_note_once_before_the_edition(self):
        ed = demo.load()
        for kwargs in ({}, {"live": True}, {"live": True, "needs_pass": True}):
            with self.subTest(**kwargs):
                html = page.build(ed, **kwargs)
                self.assertEqual(html.count(NOTE), 1)
                p = _Order()
                p.feed(html)
                self.assertEqual(p.events, ["note", "edition"])
                self.assertEqual(p.note_text.strip(), NOTE)

    def test_the_published_demo_page_carries_it(self):
        html = (ROOT / "docs" / "demo" / "brief.html").read_text(encoding="utf-8")
        self.assertEqual(html.count(NOTE), 1)


class AppPageTests(unittest.TestCase):
    def test_the_app_header_carries_the_note_once(self):
        html = (ROOT / "composer" / "web" / "app" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count(NOTE), 1)
        header = html[html.index('<header class="hd">'):html.index("</header>")]
        self.assertIn(f'<div class="ainote" id="aiNote">{NOTE}</div>', header)

    def test_the_note_is_styled_and_never_hidden(self):
        css = (ROOT / "composer" / "web" / "app" / "app.css").read_text(encoding="utf-8")
        self.assertIn(".hd .ainote{", css)
        for hidden in (".ainote{display:none", "#aiNote{display:none", ".ainote{visibility:hidden"):
            self.assertNotIn(hidden, css)
        js = (ROOT / "composer" / "web" / "app" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("aiNote", js)  # no script removes or rewrites it


if __name__ == "__main__":
    unittest.main()
