#!/usr/bin/env python3
"""Generate legacy meal-type index files from a canonical recipe artifact."""

import argparse
import json
from pathlib import Path


MEAL_TYPES = ("breakfast", "lunch", "snack", "dinner")


def load_canonical_recipes(input_path):
    with input_path.open("r", encoding="utf-8") as input_file:
        payload = json.load(input_file)

    if isinstance(payload, dict):
        recipes = payload.get("recipes")
    elif isinstance(payload, list):
        recipes = payload
    else:
        raise ValueError("Canonical recipe input must be an object or list.")

    if not isinstance(recipes, list) or not recipes:
        raise ValueError("Canonical recipe input must contain a non-empty 'recipes' list.")

    return recipes


def build_indexes(recipes, value_field):
    indexes = {meal: [] for meal in MEAL_TYPES}

    for recipe in recipes:
        if not isinstance(recipe, dict):
            raise ValueError("Each canonical recipe must be an object.")

        meal_type = recipe.get("mealType")
        if meal_type not in indexes:
            raise ValueError(f"Invalid mealType '{meal_type}' in canonical recipe data.")

        value = recipe.get(value_field) or recipe.get("title") or recipe.get("id")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Canonical recipe for mealType '{meal_type}' is missing a usable '{value_field}'."
            )

        indexes[meal_type].append(value)

    for meal_type, values in indexes.items():
        if not values:
            raise ValueError(f"No recipes found for meal type '{meal_type}'.")

    return indexes


def write_indexes(indexes, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)

    for meal_type, values in indexes.items():
        output_path = output_dir / f"{meal_type}.json"
        with output_path.open("w", encoding="utf-8") as output_file:
            json.dump(values, output_file, indent=2)
            output_file.write("\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate legacy meal-type JSON indexes from a canonical recipe artifact."
    )
    parser.add_argument(
        "--input",
        default="data/recipes_json/recipes.json",
        help="Path to the canonical recipe artifact JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/recipes_json",
        help="Directory where breakfast/lunch/snack/dinner JSON files should be written.",
    )
    parser.add_argument(
        "--value-field",
        choices=("title", "id"),
        default="title",
        help="Canonical recipe field to emit into the generated index files.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()

    recipes = load_canonical_recipes(input_path)
    indexes = build_indexes(recipes, args.value_field)
    write_indexes(indexes, output_dir)

    print(
        f"Wrote {len(MEAL_TYPES)} meal index files to {output_dir} "
        f"from {input_path.name} using '{args.value_field}'."
    )


if __name__ == "__main__":
    main()
