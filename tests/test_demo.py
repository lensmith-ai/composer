import io
import json
import re
import unittest
from unittest import mock

from composer import demo, page

from helpers import ROOT


class RecordedRunTests(unittest.TestCase):
    def setUp(self):
        self.ed = demo.load()

    def test_recorded_brief_is_valid(self):
        self.assertEqual(demo.validate(self.ed), [])
        self.assertTrue(self.ed["recorded"])
        self.assertEqual([s["label"] for s in self.ed["sources"]], ["Google AI blog", "Google DeepMind blog"])
        self.assertEqual(len(self.ed["cards"]), 5)
        self.assertEqual(self.ed["model"]["calls"], 7)

    def test_every_citation_is_a_title_a_link_and_a_digest(self):
        for card in self.ed["cards"]:
            for cit in card["citations"]:
                self.assertEqual(set(cit), {"label", "title", "url", "field", "start", "end", "relation",
                                            "window_sha256"})
                self.assertTrue(cit["url"].startswith(("https://blog.google/", "https://deepmind.google/")))

    def test_no_long_quotes_and_no_times_of_day(self):
        blob = json.dumps(self.ed, ensure_ascii=False)
        for quoted in re.findall(r"[“\"]([^\"”]{1,200})[”\"]", " ".join(
                c["why"] + " ".join(c["details"]) for c in self.ed["cards"])):
            self.assertLessEqual(len(quoted.split()), 5)
        self.assertIsNone(re.search(r"\b\d{1,2}:\d{2}\b", blob))

    def test_validate_catches_bad_offsets(self):
        bad = json.loads(json.dumps(self.ed))
        bad["cards"][0]["citations"][0]["end"] = 10_000
        self.assertTrue(any("offsets" in p for p in demo.validate(bad)))

    def test_terminal_replay_makes_no_request(self):
        out = io.StringIO()
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")), \
                mock.patch("composer.fetch.http_get", side_effect=AssertionError("network")):
            demo.replay(self.ed, out, beat_s=0)
        text = out.getvalue()
        self.assertIn("No key, no network, no model call", text)
        self.assertIn("reading Google AI blog · 5 items (ok)", text)
        self.assertIn("checked · 4 partly supported · 1 supported", text)
        self.assertIn("Model capability and safety need paired release tracks", text)

    def test_replay_pauses_between_steps(self):
        slept = []
        demo.replay(self.ed, io.StringIO(), beat_s=0.5, sleep=slept.append)
        self.assertEqual(slept, [0.5] * len(demo.steps(self.ed)))


class PageTests(unittest.TestCase):
    def test_page_is_self_contained(self):
        html = page.build(demo.load())
        self.assertNotRegex(html, r"<(script|link|img)[^>]+(src|href)=")
        csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', html).group(1)
        self.assertIn("default-src &#x27;none&#x27;", csp)
        self.assertNotIn("connect-src", csp)
        self.assertNotIn("unsafe-inline", csp)

    def test_script_and_style_hashes_match(self):
        import base64
        import hashlib
        html = page.build(demo.load())
        js = re.search(r"<script>(.*)</script>", html, re.S).group(1)
        css = re.search(r"<style>(.*)</style>", html, re.S).group(1)
        for body in (js, css):
            digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
            self.assertIn(digest, html)

    def test_embedded_json_cannot_close_its_tag(self):
        ed = demo.load()
        ed["lens"] = "</script><script>alert(1)</script>"
        html = page.build(ed)
        self.assertEqual(html.count("</script>"), 3)
        data = re.search(r'id="edition-data">(.*?)</script>', html, re.S).group(1)
        self.assertEqual(json.loads(data)["lens"], ed["lens"])

    def test_committed_plain_page_matches_the_build(self):
        committed = (ROOT / "docs" / "demo" / "brief.html").read_text(encoding="utf-8")
        self.assertEqual(committed, page.build(demo.load()),
                         "docs/demo/brief.html is stale: run `composer demo --site docs/demo`")

    def test_live_page_allows_only_same_origin_posts(self):
        from composer.registry import Registry, read_file, BUNDLED
        html = page.build(demo.load(), live=True, sources=Registry(read_file(BUNDLED)).entries(), needs_pass=True)
        self.assertIn("connect-src &#x27;self&#x27;", html)
        self.assertIn('name="pass"', html)
        cfg = json.loads(re.search(r'id="page-config">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(cfg["sources"][0], {"id": "google-ai", "label": "Google AI blog"})


if __name__ == "__main__":
    unittest.main()
