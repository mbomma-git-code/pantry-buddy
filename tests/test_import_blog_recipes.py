import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "import_blog_recipes.py"
SPEC = importlib.util.spec_from_file_location("import_blog_recipes", MODULE_PATH)
IMPORTER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = IMPORTER
SPEC.loader.exec_module(IMPORTER)


SCHEMA_HTML = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": "Lemon Pasta",
        "url": "https://example.com/lemon-pasta",
        "recipeCategory": ["Dinner"],
        "recipeCuisine": "Italian",
        "recipeIngredient": [
          "8 oz pasta",
          "2 tbsp olive oil",
          "1 lemon"
        ],
        "recipeInstructions": [
          {"@type": "HowToStep", "text": "Boil the pasta."},
          {"@type": "HowToStep", "text": "Toss with lemon and oil."}
        ],
        "nutrition": {
          "@type": "NutritionInformation",
          "calories": "420 calories",
          "proteinContent": "12 g",
          "carbohydrateContent": "58 g",
          "fatContent": "14 g"
        },
        "publisher": {
          "@type": "Organization",
          "name": "Example Kitchen"
        },
        "image": "https://example.com/lemon-pasta.jpg"
      }
    </script>
  </head>
  <body></body>
</html>
"""


FALLBACK_HTML = """
<html>
  <head>
    <title>Berry Oatmeal</title>
    <meta property="og:site_name" content="Breakfast Blog" />
    <meta property="og:image" content="https://example.com/berry-oatmeal.jpg" />
    <meta name="description" content="A vegetarian breakfast bowl." />
  </head>
  <body>
    <h1>Berry Oatmeal</h1>
    <h2>Ingredients</h2>
    <ul>
      <li>1 cup oats</li>
      <li>2 cups milk</li>
      <li>1 cup berries</li>
    </ul>
    <h2>Instructions</h2>
    <ol>
      <li>Cook oats with milk.</li>
      <li>Top with berries and serve.</li>
    </ol>
  </body>
</html>
"""

SCHEMA_HTML_TEMPLATE = """
<html>
  <head>
    <script type="application/ld+json">
      {{
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": "{title}",
        "url": "{url}",
        "recipeCategory": ["{meal_category}"],
        "recipeCuisine": "{cuisine}",
        "recipeIngredient": [
          "1 cup ingredient"
        ],
        "recipeInstructions": [
          {{"@type": "HowToStep", "text": "Make {title}."}}
        ],
        "nutrition": {{
          "@type": "NutritionInformation",
          "calories": "{calories} calories",
          "proteinContent": "10 g",
          "carbohydrateContent": "20 g",
          "fatContent": "5 g"
        }},
        "publisher": {{
          "@type": "Organization",
          "name": "{source_name}"
        }},
        "image": "{image_url}"
      }}
    </script>
  </head>
  <body></body>
</html>
"""


class ImportBlogRecipesTests(unittest.TestCase):
    def test_schema_org_recipe_is_normalized(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            html_path = Path(temp_dir) / "schema.html"
            html_path.write_text(SCHEMA_HTML, encoding="utf-8")

            entry = IMPORTER.SourceEntry(url=html_path.as_uri())
            recipe = IMPORTER.import_recipe(entry, timeout=1.0)

        self.assertEqual(recipe["title"], "Lemon Pasta")
        self.assertEqual(recipe["mealType"], "dinner")
        self.assertEqual(recipe["cuisine"], "Italian")
        self.assertEqual(recipe["sourceName"], "Example Kitchen")
        self.assertEqual(recipe["nutrition"]["calories"], 420.0)
        self.assertEqual(len(recipe["ingredients"]), 3)
        self.assertEqual(len(recipe["instructions"]), 2)

    def test_fallback_parser_extracts_heading_sections(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            html_path = Path(temp_dir) / "fallback.html"
            html_path.write_text(FALLBACK_HTML, encoding="utf-8")

            entry = IMPORTER.SourceEntry(url=html_path.as_uri(), meal_type="breakfast")
            recipe = IMPORTER.import_recipe(entry, timeout=1.0)

        self.assertEqual(recipe["title"], "Berry Oatmeal")
        self.assertEqual(recipe["mealType"], "breakfast")
        self.assertEqual(recipe["sourceName"], "Breakfast Blog")
        self.assertEqual(recipe["diet"], "vegetarian")
        self.assertEqual(recipe["image"], "https://example.com/berry-oatmeal.jpg")
        self.assertEqual(recipe["ingredients"][0]["amount"], 1)
        self.assertEqual(recipe["instructions"][1]["text"], "Top with berries and serve.")

    def test_merge_existing_replaces_matching_source_url(self):
        existing = [
            {
                "id": "berry-oatmeal",
                "title": "Berry Oatmeal",
                "sourceUrl": "https://example.com/berry-oatmeal",
                "sourceName": "Old Blog",
                "mealType": "breakfast",
                "diet": None,
                "cuisine": None,
                "ingredients": [{"item": "oats", "amount": None, "unit": None, "preparation": None}],
                "instructions": [{"step": 1, "text": "Cook."}],
                "nutrition": IMPORTER.empty_nutrition(),
                "image": None,
            }
        ]
        imported = [
            {
                "id": "berry-oatmeal",
                "title": "Better Berry Oatmeal",
                "sourceUrl": "https://example.com/berry-oatmeal",
                "sourceName": "New Blog",
                "mealType": "breakfast",
                "diet": "vegetarian",
                "cuisine": None,
                "ingredients": [{"item": "berries", "amount": None, "unit": None, "preparation": None}],
                "instructions": [{"step": 1, "text": "Serve."}],
                "nutrition": IMPORTER.empty_nutrition(),
                "image": None,
            }
        ]

        merged = IMPORTER.merge_recipes(existing, imported)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["title"], "Better Berry Oatmeal")

    def test_source_manifest_accepts_strings_and_objects(self):
        manifest = [
            "https://example.com/recipe-1",
            {"url": "https://example.com/recipe-2", "mealType": "lunch"},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "sources.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            sources = IMPORTER.load_sources(manifest_path)

        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0].url, "https://example.com/recipe-1")
        self.assertEqual(sources[1].meal_type, "lunch")

    def test_main_writes_generated_artifact_and_indexes_from_manifest(self):
        meal_specs = [
            ("breakfast", "Breakfast", "Toasted Oats", "Minimalist Baker", "American", 320),
            ("lunch", "Lunch", "Kale Salad", "Love and Lemons", "American", 410),
            ("snack", "Snack", "Energy Balls", "Nora Cooks", "American", 210),
            ("dinner", "Dinner", "Tomato Chickpea Pasta", "Cookie and Kate", "Mediterranean", 520),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest_entries = []
            for meal_type, meal_category, title, source_name, cuisine, calories in meal_specs:
                html_path = temp_path / f"{meal_type}.html"
                html_path.write_text(
                    SCHEMA_HTML_TEMPLATE.format(
                        title=title,
                        url=f"https://example.com/{meal_type}",
                        meal_category=meal_category,
                        cuisine=cuisine,
                        calories=calories,
                        source_name=source_name,
                        image_url=f"https://example.com/{meal_type}.jpg",
                    ),
                    encoding="utf-8",
                )
                manifest_entries.append(
                    {
                        "url": html_path.as_uri(),
                        "mealType": meal_type,
                        "cuisine": cuisine,
                        "sourceName": source_name,
                    }
                )

            manifest_path = temp_path / "sources.json"
            output_path = temp_path / "recipes.json"
            manifest_path.write_text(json.dumps(manifest_entries), encoding="utf-8")

            argv = [
                "import_blog_recipes.py",
                "--sources",
                str(manifest_path),
                "--output",
                str(output_path),
                "--write-indexes",
            ]
            with patch.object(sys, "argv", argv):
                exit_code = IMPORTER.main()

            artifact = json.loads(output_path.read_text(encoding="utf-8"))
            breakfast_index = json.loads((temp_path / "breakfast.json").read_text(encoding="utf-8"))
            lunch_index = json.loads((temp_path / "lunch.json").read_text(encoding="utf-8"))
            snack_index = json.loads((temp_path / "snack.json").read_text(encoding="utf-8"))
            dinner_index = json.loads((temp_path / "dinner.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(artifact["sourceType"], "imported")
        self.assertEqual(len(artifact["recipes"]), 4)
        self.assertEqual({recipe["mealType"] for recipe in artifact["recipes"]}, {"breakfast", "lunch", "snack", "dinner"})
        self.assertTrue(all(recipe["sourceUrl"] for recipe in artifact["recipes"]))
        self.assertTrue(all(recipe["sourceName"] for recipe in artifact["recipes"]))
        self.assertEqual(breakfast_index, ["Toasted Oats"])
        self.assertEqual(lunch_index, ["Kale Salad"])
        self.assertEqual(snack_index, ["Energy Balls"])
        self.assertEqual(dinner_index, ["Tomato Chickpea Pasta"])


if __name__ == "__main__":
    unittest.main()
