import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_kb_index as builder  # noqa: E402


SAMPLE = {
    "version": "1.0",
    "generatedAt": "2026-09-02T00:00:00Z",
    "sourceType": "test",
    "recipes": [
        {
            "id": "berry-oats",
            "title": "Berry Oats",
            "sourceUrl": "https://example.test/berry-oats",
            "sourceName": "Test Kitchen",
            "mealType": "breakfast",
            "diet": "vegetarian",
            "cuisine": "American",
            "ingredients": [{"item": "Oats", "amount": 1, "unit": "cup", "preparation": None}],
            "instructions": [{"step": 1, "text": "Cook oats."}],
            "nutrition": {
                "calories": 300,
                "proteinGrams": 10,
                "carbsGrams": 40,
                "fatGrams": 8,
            },
        }
    ],
}


class BuildKbIndexTests(unittest.TestCase):
    def test_build_writes_body_metadata_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "recipes.json"
            output_dir = tmp_path / "kb"
            input_path.write_text(json.dumps(SAMPLE), encoding="utf-8")

            manifest = builder.build_index(input_path=input_path, output_dir=output_dir)
            body_path = output_dir / "structured" / "berry-oats.txt"
            meta_path = output_dir / "structured" / "berry-oats.txt.metadata.json"

            self.assertTrue(body_path.exists())
            self.assertTrue(meta_path.exists())
            body = body_path.read_text(encoding="utf-8")
            self.assertIn("title: Berry Oats", body)
            self.assertIn("sourceUrl: https://example.test/berry-oats", body)

            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            attrs = metadata["metadataAttributes"]
            self.assertEqual(attrs["recipeId"], "berry-oats")
            self.assertEqual(attrs["docType"], "structured")
            self.assertEqual(attrs["mealType"], "breakfast")
            self.assertEqual(manifest["documents"][0]["recipeId"], "berry-oats")

    def test_orphan_cleanup_removes_stale_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "recipes.json"
            output_dir = tmp_path / "kb"
            structured = output_dir / "structured"
            structured.mkdir(parents=True)
            stale = structured / "old-recipe.txt"
            stale.write_text("gone\n", encoding="utf-8")
            input_path.write_text(json.dumps(SAMPLE), encoding="utf-8")

            builder.build_index(input_path=input_path, output_dir=output_dir)
            self.assertFalse(stale.exists())
            self.assertTrue((structured / "berry-oats.txt").exists())


if __name__ == "__main__":
    unittest.main()
