import tempfile
import unittest
from pathlib import Path

from composer import lenses


class BuiltinLensTests(unittest.TestCase):
    def test_public_registry_has_three_available_lenses_with_declared_shapes(self):
        registry = lenses.LensRegistry.builtin()
        self.assertEqual(registry.ids, ("system-improvements", "second-order-effects", "raised-eyebrow"))
        for entry in registry.entries():
            self.assertTrue(entry.available)
            self.assertTrue(entry.blurb)
            self.assertEqual(entry.shape["items"], "insights")

    def test_shape_check_rejects_wrong_item_count_and_unreadable_result(self):
        registry = lenses.LensRegistry.builtin()
        entry = registry.get("system-improvements")
        self.assertEqual(lenses.check_shape(entry, {"items": [{"insight": "One short clear sentence."}]} , 1), [])
        self.assertIn("asked for 2", lenses.check_shape(entry, {"items": [{"insight": "One."}]}, 2)[0])
        self.assertIn("plain", lenses.check_shape(entry, {"items": [{"insight": "Pneumonoultramicroscopicsilicovolcanoconiosis."}]}, 1)[0])


class CustomLensStoreTests(unittest.TestCase):
    def test_save_and_edit_create_content_addressed_revisions(self):
        with tempfile.TemporaryDirectory() as d:
            store = lenses.LensStore(Path(d))
            first = store.save({"name": "Team focus", "instruction": "Look for practical team improvements.",
                                "reading_level": "plain"})
            second = store.save({"name": "Team focus", "instruction": "Look for practical team improvements and tradeoffs.",
                                 "reading_level": "plain"}, previous=first.revision)
            self.assertNotEqual(first.revision, second.revision)
            self.assertTrue((Path(d) / first.revision / "recipe.json").exists())
            self.assertEqual(store.get(second.revision).instruction, "Look for practical team improvements and tradeoffs.")

    def test_recipe_rejects_prompt_delimiters_and_unknown_reading_level(self):
        with tempfile.TemporaryDirectory() as d:
            store = lenses.LensStore(Path(d))
            with self.assertRaises(lenses.LensError):
                store.save({"name": "Bad", "instruction": "<<<LENS", "reading_level": "plain"})
            with self.assertRaises(lenses.LensError):
                store.save({"name": "Bad", "instruction": "Look carefully.", "reading_level": "graduate"})


if __name__ == "__main__":
    unittest.main()
