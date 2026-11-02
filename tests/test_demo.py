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
        defaults = [s["label"] for s in json.loads((ROOT / "composer" / "sources.json").read_text("utf-8"))["sources"]]
        self.assertEqual([s["label"] for s in self.ed["sources"]], defaults)  # all six default sources were read
        self.assertEqual(len(self.ed["cards"]), 5)
        self.assertEqual(self.ed["model"]["calls"], 7)
        self.assertEqual((self.ed["check"]["rows"], self.ed["check"]["agree"]), (6, 6))

    def test_every_citation_is_a_title_a_link_and_where_marked_a_digest(self):
        hosts = ("https://blog.google/", "https://deepmind.google/", "https://huggingface.co/",
                 "https://www.microsoft.com/en-us/research/", "https://pytorch.org/", "https://arxiv.org/")
        marked = 0
        for card in self.ed["cards"]:
            for cit in card["citations"]:
                self.assertLessEqual({"label", "title", "url", "resolution"}, set(cit))
                self.assertLessEqual(set(cit), {"label", "title", "url", "resolution", "field", "start", "end",
                                                "relation", "window_sha256"})
                self.assertTrue(cit["url"].startswith(hosts), cit["url"])
                if "field" in cit:
                    marked += 1
                    self.assertTrue({"start", "end"} <= set(cit))
        self.assertGreaterEqual(marked, 7)

    def test_the_recording_cites_only_default_sources(self):
        defaults = {s["label"] for s in json.loads((ROOT / "composer" / "sources.json").read_text("utf-8"))["sources"]}
        used = {s["label"] for s in self.ed["sources"]} | {c["label"] for card in self.ed["cards"]
                                                            for c in card["citations"]}
        self.assertLessEqual(used, defaults)

    def test_the_recording_uses_the_bundled_ids_and_no_run_detail(self):
        # paths, private names and key shapes are covered by test_banned for every file; here: the recording names
        # sources only by their bundled labels, and carries no job id, session id or file path of the run it came from
        blob = json.dumps(self.ed, ensure_ascii=False)
        self.assertIsNone(re.search(r"\d{8}T\d{6}Z|session|\.mp3|\.json|googleai|hugging-face-blog|"
                                    r"microsoft-research-blog", blob))

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
        self.assertIn("reading arXiv cs.AI · 5 items (ok)", text)
        self.assertIn("checked · 2 supported · 3 partly supported", text)
        self.assertIn("Safety decisions need policy-relevant evidence, not believable forecasts.", text)

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
        self.assertEqual(cfg["sources"][0], {"id": "google-ai", "label": "Google AI blog",
                                              "available": True, "hidden": False, "reason": ""})


if __name__ == "__main__":
    unittest.main()
