import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

MODULE_PATH = BACKEND_DIR / "lambda_function.py"
SPEC = importlib.util.spec_from_file_location("lambda_function", MODULE_PATH)
LAMBDA = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = LAMBDA
SPEC.loader.exec_module(LAMBDA)


CANONICAL_ARTIFACT = {
    "version": "1.0",
    "generatedAt": "2026-03-25T00:00:00Z",
    "sourceType": "mixed",
    "recipes": [
        {
            "id": "berry-oats",
            "title": "Berry Oats",
            "mealType": "breakfast",
            "diet": "vegetarian",
            "cuisine": "American",
            "sourceName": "Pantry Buddy Test Kitchen",
            "sourceUrl": "https://example.test/berry-oats",
            "ingredients": [{"item": "Oats", "amount": 1, "unit": "cup", "preparation": None}],
            "instructions": [{"step": 1, "text": "Cook the oats."}],
            "nutrition": {
                "calories": 320,
                "proteinGrams": 12,
                "carbsGrams": 54,
                "fatGrams": 8,
            },
        },
        {
            "id": "veg-wrap",
            "title": "Veg Wrap",
            "mealType": "lunch",
            "diet": "vegetarian",
            "cuisine": "Mediterranean",
            "sourceName": "Lunch Lab",
            "sourceUrl": "https://example.test/veg-wrap",
            "ingredients": [{"item": "Tortilla", "amount": 1, "unit": None, "preparation": None}],
            "instructions": [{"step": 1, "text": "Fill and roll the wrap."}],
            "nutrition": {
                "calories": 410,
                "proteinGrams": 14,
                "carbsGrams": 48,
                "fatGrams": 16,
            },
        },
        {
            "id": "trail-mix",
            "title": "Trail Mix",
            "mealType": "snack",
            "diet": "vegan",
            "cuisine": "Global",
            "sourceName": "Snack Studio",
            "sourceUrl": "https://example.test/trail-mix",
            "ingredients": [{"item": "Mixed nuts", "amount": 1, "unit": "cup", "preparation": None}],
            "instructions": [{"step": 1, "text": "Mix and serve."}],
            "nutrition": {
                "calories": 250,
                "proteinGrams": 8,
                "carbsGrams": 16,
                "fatGrams": 18,
            },
        },
        {
            "id": "lentil-soup",
            "title": "Lentil Soup",
            "mealType": "dinner",
            "diet": "vegan",
            "cuisine": "Middle Eastern",
            "sourceName": "Dinner Desk",
            "sourceUrl": "https://example.test/lentil-soup",
            "ingredients": [{"item": "Lentils", "amount": 2, "unit": "cups", "preparation": None}],
            "instructions": [{"step": 1, "text": "Simmer until tender."}],
            "nutrition": {
                "calories": 430,
                "proteinGrams": 22,
                "carbsGrams": 52,
                "fatGrams": 10,
            },
        },
    ],
}


class LambdaFunctionCompatibilityTests(unittest.TestCase):
    def test_auto_mode_prefers_canonical_artifact(self):
        legacy_indexes = {
            "breakfast": ["Legacy Breakfast"],
            "lunch": ["Legacy Lunch"],
            "snack": ["Legacy Snack"],
            "dinner": ["Legacy Dinner"],
        }

        with patch.object(LAMBDA, "RECIPE_COMPATIBILITY_MODE", "auto"), patch.object(
            LAMBDA, "load_canonical_recipe_artifact", return_value=CANONICAL_ARTIFACT
        ), patch.object(
            LAMBDA, "load_legacy_recipe_indexes", return_value=legacy_indexes
        ) as load_legacy:
            recipes = LAMBDA.load_all_recipes()

        self.assertEqual(recipes["breakfast"][0]["title"], "Berry Oats")
        self.assertEqual(recipes["dinner"][0]["title"], "Lentil Soup")
        load_legacy.assert_not_called()

    def test_auto_mode_falls_back_to_legacy_indexes_when_canonical_is_invalid(self):
        legacy_indexes = {
            "breakfast": ["Legacy Breakfast"],
            "lunch": ["Legacy Lunch"],
            "snack": ["Legacy Snack"],
            "dinner": ["Legacy Dinner"],
        }

        with patch.object(LAMBDA, "RECIPE_COMPATIBILITY_MODE", "auto"), patch.object(
            LAMBDA, "load_canonical_recipe_artifact", return_value={"recipes": [{"title": "Broken"}]}
        ), patch.object(
            LAMBDA, "load_legacy_recipe_indexes", return_value=legacy_indexes
        ):
            recipes = LAMBDA.load_all_recipes()

        self.assertEqual(recipes, legacy_indexes)

    def test_build_week_plan_returns_recipe_detail_objects(self):
        recipes = LAMBDA.build_meal_indexes_from_canonical(CANONICAL_ARTIFACT)

        with patch.object(LAMBDA.random, "choice", side_effect=lambda items: items[0]):
            week_plan = LAMBDA.build_week_plan(recipes)

        self.assertEqual(len(week_plan), 7)
        self.assertEqual(week_plan[0]["day"], "Monday")
        self.assertEqual(week_plan[0]["breakfast"]["title"], "Berry Oats")
        self.assertEqual(week_plan[0]["breakfast"]["mealType"], "breakfast")
        self.assertEqual(week_plan[0]["breakfast"]["diet"], "vegetarian")
        self.assertEqual(
            week_plan[0]["breakfast"]["sourceName"], "Pantry Buddy Test Kitchen"
        )
        self.assertEqual(
            week_plan[0]["breakfast"]["sourceUrl"], "https://example.test/berry-oats"
        )
        self.assertEqual(week_plan[0]["breakfast"]["ingredients"][0]["item"], "Oats")
        self.assertEqual(week_plan[0]["lunch"]["title"], "Veg Wrap")
        self.assertEqual(week_plan[0]["snack"]["nutrition"]["proteinGrams"], 8)
        self.assertEqual(week_plan[0]["dinner"]["instructions"][0]["text"], "Simmer until tender.")

    def test_build_week_plan_enriches_legacy_titles_from_canonical_lookup(self):
        recipes = {
            "breakfast": ["Berry Oats"],
            "lunch": ["Veg Wrap"],
            "snack": ["Trail Mix"],
            "dinner": ["Lentil Soup"],
        }
        canonical_lookup = LAMBDA.build_recipe_lookup_from_canonical(CANONICAL_ARTIFACT)

        with patch.object(LAMBDA.random, "choice", side_effect=lambda items: items[0]), patch.object(
            LAMBDA, "load_canonical_recipe_lookup", return_value=canonical_lookup
        ):
            week_plan = LAMBDA.build_week_plan(recipes)

        self.assertEqual(week_plan[0]["breakfast"]["title"], "Berry Oats")
        self.assertEqual(
            week_plan[0]["breakfast"]["sourceName"], "Pantry Buddy Test Kitchen"
        )
        self.assertEqual(
            week_plan[0]["breakfast"]["sourceUrl"], "https://example.test/berry-oats"
        )
        self.assertEqual(week_plan[0]["breakfast"]["ingredients"][0]["item"], "Oats")
        self.assertEqual(week_plan[0]["dinner"]["nutrition"]["calories"], 430)

    def test_generate_structured_plan_returns_week_with_recipe_objects(self):
        recipes = LAMBDA.build_meal_indexes_from_canonical(CANONICAL_ARTIFACT)

        with patch.object(LAMBDA.random, "choice", side_effect=lambda items: items[0]):
            payload = LAMBDA.generate_structured_plan({}, {"recipes": recipes})

        self.assertEqual(list(payload.keys()), ["week"])
        self.assertEqual(payload["week"][0]["breakfast"]["title"], "Berry Oats")
        self.assertIsInstance(payload["week"][0]["dinner"], dict)

    def test_handle_v2_response_includes_source_fields_from_generated_recipes(self):
        recipes = LAMBDA.build_meal_indexes_from_canonical(CANONICAL_ARTIFACT)
        event = {
            "resource": "/v2/generate-meal-plan",
            "path": "/v2/generate-meal-plan",
            "body": "{}",
        }

        with patch.object(LAMBDA, "load_all_recipes", return_value=recipes), patch.object(
            LAMBDA.random, "choice", side_effect=lambda items: items[0]
        ):
            response = LAMBDA.lambda_handler(event, context=None)

        payload = json.loads(response["body"])
        monday_breakfast = payload["week"][0]["breakfast"]

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(monday_breakfast["title"], "Berry Oats")
        self.assertEqual(monday_breakfast["sourceName"], "Pantry Buddy Test Kitchen")
        self.assertEqual(monday_breakfast["sourceUrl"], "https://example.test/berry-oats")
        self.assertEqual(monday_breakfast["ingredients"][0]["item"], "Oats")


if __name__ == "__main__":
    unittest.main()
