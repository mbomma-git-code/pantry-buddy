import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "generate_recipe_artifacts.py"
SPEC = importlib.util.spec_from_file_location("generate_recipe_artifacts", MODULE_PATH)
GENERATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = GENERATOR
SPEC.loader.exec_module(GENERATOR)


SAMPLE_RECIPE = """Title: Stuffed Bell Peppers Meal Type: Dinner Diet: Vegan Cuisine:
Mediterranean Calories: 600 Protein: 20g

Ingredients: - 3 bell peppers - 1 cup quinoa - 2 tbsp olive oil

Instructions: Prepare peppers for stuffing. Bake until tender.
Serve warm.
"""


class GenerateRecipeArtifactsTests(unittest.TestCase):
    def test_parse_recipe_file_normalizes_wrapped_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            recipe_path = Path(temp_dir) / "stuffed_bell_peppers.txt"
            recipe_path.write_text(SAMPLE_RECIPE, encoding="utf-8")

            recipe = GENERATOR.parse_recipe_file(recipe_path, source_name="PantryBuddy Seed Data")

        self.assertEqual(recipe["id"], "stuffed-bell-peppers")
        self.assertEqual(recipe["mealType"], "dinner")
        self.assertEqual(recipe["diet"], "vegan")
        self.assertEqual(recipe["cuisine"], "Mediterranean")
        self.assertEqual(recipe["nutrition"]["calories"], 600)
        self.assertEqual(recipe["nutrition"]["proteinGrams"], 20)
        self.assertEqual(len(recipe["ingredients"]), 3)
        self.assertEqual(recipe["ingredients"][1]["amount"], 1)
        self.assertEqual(recipe["ingredients"][1]["unit"], "cup")
        self.assertEqual(recipe["instructions"][2]["text"], "Serve warm.")

    def test_build_indexes_groups_titles_by_meal_type(self):
        recipes = [
            {"title": "Berry Oats", "mealType": "breakfast"},
            {"title": "Veg Wrap", "mealType": "lunch"},
            {"title": "Trail Mix", "mealType": "snack"},
            {"title": "Lentil Soup", "mealType": "dinner"},
        ]

        indexes = GENERATOR.build_indexes(recipes)

        self.assertEqual(indexes["breakfast"], ["Berry Oats"])
        self.assertEqual(indexes["lunch"], ["Veg Wrap"])
        self.assertEqual(indexes["snack"], ["Trail Mix"])
        self.assertEqual(indexes["dinner"], ["Lentil Soup"])


if __name__ == "__main__":
    unittest.main()
