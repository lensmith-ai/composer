"""The page's view of a brief carries what the claim popover needs: each citation's marked sentence and, only from the
job's own passages.json, the few words of located evidence. The edition and check.json never carry article words."""
import json
import tempfile
import unittest
from pathlib import Path

from composer import app_static, live_files

import helpers  # noqa: F401  (private temporary folders)

EDITION = {"schema": "composer-edition/v1", "lens": "x", "cards": [
    {"insight": "Tidewater opens its gauges", "why": "Readings come hourly from forty sensors.",
     "details": ["Volunteers mapped forty culverts."], "state": "partial",
     "citations": [{"label": "Lab A notes", "title": "River gauges", "url": "https://example.org/g",
                    "resolution": "exact", "field": "why", "start": 0, "end": 27, "relation": "implies",
                    "window_sha256": "a" * 64},
                   {"label": "Lab B notes", "title": "", "url": "", "resolution": "unresolved"},
                   {"label": "Lab B notes", "title": "Culverts", "url": "javascript:alert(1)", "resolution": "exact",
                    "field": "details[0]", "start": 0, "end": 10, "relation": "says"}]}]}
JOB = {"job": "job-0123456789abcdef", "result": EDITION, "finished_at": "2026-11-07T10:00:00Z"}


class ComposedViewTests(unittest.TestCase):
    def view(self, passages=None):
        return live_files.composed_view(JOB, {"Lab A notes": "lab-a", "Lab B notes": "lab-b"}, passages)

    def test_a_citation_carries_its_marked_sentence_in_the_pages_field_names(self):
        cites = self.view()["items"][0]["verification"]["citations"]
        self.assertEqual(cites[0]["span"], {"field": "why_it_matters", "start": 0, "end": 27, "sentence_relation": "implies"})
        self.assertEqual(cites[1]["span"]["field"], "detail[0]")

    def test_a_citation_without_a_title_is_left_out_and_the_rest_keep_the_checks_numbering(self):
        view = self.view({"0.0": {"text": "first", "cut": False}, "0.1": {"text": "never shown"},
                          "0.2": {"text": "third words", "cut": True}})
        cites = view["items"][0]["verification"]["citations"]
        self.assertEqual([c["ref"] for c in cites], ["River gauges", "Culverts"])
        self.assertEqual([c["passage"]["text"] for c in cites], ["first", "third words"])
        self.assertTrue(cites[1]["passage"]["cut"])

    def test_no_passages_file_means_no_passage_and_the_fingerprint_stays(self):
        first = self.view()["items"][0]["verification"]["citations"][0]
        self.assertNotIn("passage", first)
        self.assertEqual(first["window_sha256"], "a" * 64)

    def test_a_passage_replaces_the_fingerprint_not_adds_to_it(self):
        first = self.view({"0.0": {"text": "words"}})["items"][0]["verification"]["citations"][0]
        self.assertNotIn("window_sha256", first)

    def test_the_edition_itself_stays_free_of_passages(self):
        self.assertNotIn("passage", json.dumps(EDITION))


class ReadsPassagesFileTests(unittest.TestCase):
    class Store:
        def __init__(self, folder, job):
            self.folder, self.job = Path(folder), job

        def status(self, job_id):
            return self.job

        def job_dir(self, job_id):
            return self.folder

    def read(self, folder):
        found = live_files.read(self.Store(folder, JOB), JOB["job"], "composed.json")
        return json.loads(found[0])

    def test_the_job_folders_passages_json_is_merged_into_composed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "passages.json").write_text(json.dumps({"rows": {"0.0": {"text": "kept words", "cut": False}}}))
            cite = self.read(tmp)["items"][0]["verification"]["citations"][0]
            self.assertEqual(cite["passage"]["text"], "kept words")

    def test_a_missing_or_broken_file_is_no_passage_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertNotIn("passage", self.read(tmp)["items"][0]["verification"]["citations"][0])
            (Path(tmp) / "passages.json").write_text("{not json")
            self.assertNotIn("passage", self.read(tmp)["items"][0]["verification"]["citations"][0])
            (Path(tmp) / "passages.json").write_text(json.dumps({"rows": ["a list"]}))
            self.assertNotIn("passage", self.read(tmp)["items"][0]["verification"]["citations"][0])

    def test_passages_json_is_not_a_served_file(self):
        self.assertIsNone(live_files.parse("/data/live/job-0123456789abcdef/passages.json"))


class ClaimSealScriptTests(unittest.TestCase):
    js = (app_static.APP_DIR / "claimseal.js").read_text(encoding="utf-8")

    def test_it_is_served_and_listed(self):
        self.assertIn("claimseal.js", app_static.FILES)
        self.assertIsNotNone(app_static.lookup("/app/claimseal.js"))

    def test_nothing_from_a_brief_or_a_feed_goes_in_as_html(self):
        self.assertNotRegex(self.js, r"innerHTML|insertAdjacentHTML|outerHTML|document\.write")

    def test_links_are_http_or_https_only(self):
        self.assertIn("/^https?:\\/\\//i", self.js)


if __name__ == "__main__":
    unittest.main()
