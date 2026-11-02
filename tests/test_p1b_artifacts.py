import json
import tempfile
import unittest
from pathlib import Path

from composer import receipts, seal
from composer.providers import Counted, Reply


class ArtifactTests(unittest.TestCase):
    def test_receipt_and_plain_transcript_do_not_store_source_text_or_estimated_cost(self):
        run = {
            "edition": {"lens": "system improvements", "transcript": "The model's own spoken script.\n",
                        "lens_definition": {"id": "custom-abc123def456",
                        "revision": "a" * 64, "prompt_sha256": "b" * 64}, "cards": [{"insight": "Clear improvement", "why": "It helps.",
                        "details": ["One detail."], "citations": []}], "check": {"seal": "abc", "seal_verified": True}},
            "fetched": {"one": ([{"title": "Title", "description": "private feed words", "url": "https://example.org"}],
                                {"source": "one", "label": "One", "status": "ok", "items": 1, "bytes": 22, "cleaned": 0})},
            "receipt": {"provider": "fixture", "calls": 1, "failed_calls": 0, "input_tokens": 4,
                        "output_tokens": 3, "per_call": [{"call": 1, "ok": True, "model": "fixture-model",
                                                              "input_tokens": 4, "output_tokens": 3, "seconds": 0.1}]},
        }
        with tempfile.TemporaryDirectory() as d:
            written = receipts.write_brief_artifacts(Path(d), run)
            transcript = (Path(d) / "transcript.txt").read_text(encoding="utf-8")
            receipt = json.loads((Path(d) / "receipts.json").read_text(encoding="utf-8"))
        self.assertEqual({p.name for p in written}, {"transcript.txt", "receipts.json"})
        self.assertEqual(transcript, "The model's own spoken script.\n")  # the script the model wrote, not a rendering
        self.assertNotIn("private feed words", transcript)
        self.assertNotIn("private feed words", json.dumps(receipt))
        self.assertEqual(receipt["requested_sources"], ["one"])
        self.assertEqual(receipt["sources"]["one"]["fetch_tier"], "native")
        self.assertNotIn("cost", receipt)
        self.assertEqual(receipt["model_calls"]["input_tokens"], 4)
        self.assertEqual(receipt["lens_definition"]["revision"], "a" * 64)
        self.assertEqual(receipt["lens_definition"]["prompt_sha256"], "b" * 64)

    def test_a_brief_without_a_script_gets_no_transcript_file(self):
        run = {"edition": {"lens": "x", "cards": []}, "fetched": {}, "receipt": {}}
        with tempfile.TemporaryDirectory() as d:
            written = receipts.write_brief_artifacts(Path(d), run, requested=["one"])
            self.assertEqual([p.name for p in written], ["receipts.json"])
            self.assertFalse((Path(d) / "transcript.txt").exists())


class CountedReceiptTests(unittest.TestCase):
    def test_receipt_uses_provider_reported_usage_without_estimation(self):
        class Model:
            name = "fixture"
            def __call__(self, prompt, timeout=None):
                return Reply("answer", model="fixture-model", usage={"input_tokens": 7, "output_tokens": 5})
        counted = Counted(Model())
        counted("prompt")
        receipt = receipts.model_receipt(counted)
        self.assertEqual(receipt["input_tokens"], 7)
        self.assertEqual(receipt["output_tokens"], 5)
        self.assertNotIn("cost", receipt)


class SealTests(unittest.TestCase):
    def test_reverify_delegates_only_to_the_seal_verifier(self):
        doc = {"claim_evidence": {"verification": {"seal": {"value": "abc"}}}}
        seen = []
        ok, value = seal.verify_check_document(doc, verifier=lambda evidence: seen.append(evidence) or True)
        self.assertTrue(ok)
        self.assertEqual(value, "abc")
        self.assertEqual(len(seen), 1)

    def test_missing_claim_evidence_is_not_claimed_as_verified(self):
        with self.assertRaises(seal.SealError):
            seal.verify_check_document({})


if __name__ == "__main__":
    unittest.main()
