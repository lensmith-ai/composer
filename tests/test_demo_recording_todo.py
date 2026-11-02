"""TODO(demo-recording): this test FAILS ON PURPOSE until the recorded demo brief is replaced.

The bundled sources are now six public feeds (composer/sources.json). The recorded brief that `composer demo`, the
static demo and the README screenshots replay (composer/data/recorded-run.json, recorded 2026-10-25 from the Google AI
blog and the Google DeepMind blog) is to be swapped for a new recording made from the new default sources.

When the new recording lands:
  1. replace composer/data/recorded-run.json, rebuild docs/demo (`composer demo --site docs/demo`) and the README
     screenshots (docs/readme/capture.mjs), and update the tests that name the old recording's sources and cards;
  2. delete this file.

The second test stays useful after the swap: a recording may only cite sources that ship as defaults.
"""
import hashlib
import json
import unittest

from helpers import ROOT

RECORDING = ROOT / "composer" / "data" / "recorded-run.json"
# SHA-256 of the 2026-10-25 recording (Google AI blog + Google DeepMind blog, lens "system improvements").
OLD_RECORDING_SHA256 = "9c8cf21167786c790281f5838dcaa3a6f3a47f074ddc90983b7c299acc34624f"


class DemoRecordingTodo(unittest.TestCase):
    def test_TODO_the_demo_recording_has_been_swapped_for_one_from_the_six_default_sources(self):
        got = hashlib.sha256(RECORDING.read_bytes()).hexdigest()
        self.assertNotEqual(
            got, OLD_RECORDING_SHA256,
            "TODO(demo-recording): composer/data/recorded-run.json is still the 2026-10-25 recording. Swap in the "
            "new recording made from the default sources, rebuild docs/demo, then delete "
            "tests/test_demo_recording_todo.py.")

    def test_the_recording_cites_only_default_sources(self):
        defaults = {s["label"] for s in json.loads((ROOT / "composer" / "sources.json").read_text("utf-8"))["sources"]}
        ed = json.loads(RECORDING.read_text(encoding="utf-8"))
        used = {s["label"] for s in ed["sources"]} | {c["label"] for card in ed["cards"] for c in card["citations"]}
        self.assertLessEqual(used, defaults)


if __name__ == "__main__":
    unittest.main()
