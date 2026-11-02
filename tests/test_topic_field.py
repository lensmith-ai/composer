"""The topic focus is not part of the public app: the page has no topic field and never sends one, and the compose
route refuses a `topic` key."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from composer import server
from composer.registry import BUNDLED, Registry, read_file

APP = Path(__file__).resolve().parent.parent / "composer" / "web" / "app"


class TopicFieldTests(unittest.TestCase):
    def test_the_page_has_no_topic_field(self):
        for name in ("app.js", "index.html", "app.css"):
            text = (APP / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertIsNone(re.search(r"topic", text, re.IGNORECASE))

    def test_the_compose_route_still_refuses_a_topic(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = server.App(Registry(read_file(BUNDLED)), lambda: "model", data_root=Path(tmp.name) / "data")
        status, body = app.submit_job({}, json.dumps({"sources": ["google-ai"], "lens": "x",
                                                      "topic": "rivers"}).encode())
        self.assertEqual(400, status, body)


if __name__ == "__main__":
    unittest.main()
