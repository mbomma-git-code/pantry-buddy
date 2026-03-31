#!/usr/bin/env python3
"""Generate canonical recipe artifacts and meal-type indexes from text seeds."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MEAL_TYPES = ("breakfast", "lunch", "snack", "dinner")
HEADER_LABELS = ("Title", "Meal Type", "Diet", "Cuisine", "Calories", "Protein")
SECTION_PATTERN = re.compile(
    r"(?is)^(?P<header>.*?)(?:Ingredients\s*:\s*)(?P<ingredients>.*?)(?:Instructions\s*:\s*)(?P<instructions>.*)$"
)
HEADER_PATTERN = re.compile(r"(Title|Meal Type|Diet|Cuisine|Calories|Protein)\s*:\s*", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])(\d+(?:\.\d+)?)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Parse legacy text recipe seeds into PantryBuddy canonical recipe JSON and "
            "derived meal-type index files."
        )
    )
    parser.add_argument(
        "--input-dir",
        default="data/recipes_text",
        help="Directory containing legacy text recipe seed files.",
    )
    parser.add_argument(
        "--output",
        default="data/recipes_json/recipes.json",
        help="Path to the canonical recipe artifact to write.",
    )
    parser.add_argument(
        "--sample-output",
        default="data/recipes_json/recipes.sample.json",
        help="Path to the sample canonical artifact to write.",
    )
    parser.add_argument(
        "--schema",
        default="data/recipes_json/recipes.schema.json",
        help="Path to the canonical recipe schema for validation reference.",
    )
    parser.add_argument(
        "--source-name",
        default="PantryBuddy Seed Data",
        help="Source label to assign to locally seeded recipes.",
    )
    parser.add_argument(
        "--sample-size-per-meal",
        type=int,
        default=2,
        help="How many recipes per meal type to include in recipes.sample.json.",
    )
    return parser.parse_args()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", clean_text(value).lower()).strip("-")
    return slug or "recipe"


def parse_header_fields(header_text: str) -> dict[str, str]:
    normalized = clean_text(header_text)
    matches = list(HEADER_PATTERN.finditer(normalized))
    if not matches:
        raise ValueError("Recipe header is missing labeled metadata.")

    fields: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        label = match.group(1).lower().replace(" ", "")
        fields[label] = normalized[start:end].strip()

    return fields


def parse_numeric_value(value: str) -> float | int | None:
    match = NUMBER_PATTERN.search(clean_text(value))
    if not match:
        return None
    number = float(match.group(1))
    if number.is_integer():
        return int(number)
    return number


def split_ingredient_line(line: str) -> tuple[float | int | str | None, str | None, str]:
    cleaned = clean_text(line)
    if not cleaned:
        raise ValueError("Ingredient line cannot be empty.")

    match = NUMBER_PATTERN.match(cleaned)
    if not match:
        return None, None, cleaned

    raw_amount = match.group(1)
    amount = float(raw_amount)
    if amount.is_integer():
        amount = int(amount)

    remainder = cleaned[match.end():].strip(" -")
    parts = remainder.split(" ", 1)
    if len(parts) == 2 and len(parts[0]) <= 12:
        unit = parts[0] or None
        item = parts[1].strip()
    else:
        unit = None
        item = remainder or cleaned

    return amount, unit, item


def parse_ingredients(section_text: str) -> list[dict[str, Any]]:
    normalized = clean_text(section_text)
    if normalized.startswith("- "):
        normalized = normalized[2:]

    raw_items = [item.strip() for item in re.split(r"\s+-\s+", normalized) if item.strip()]
    ingredients = []
    for raw_item in raw_items:
        amount, unit, item = split_ingredient_line(raw_item)
        ingredients.append(
            {
                "item": item,
                "amount": amount,
                "unit": unit,
                "preparation": None,
            }
        )

    return ingredients


def parse_instructions(section_text: str) -> list[dict[str, Any]]:
    normalized = section_text.replace("\r\n", "\n").strip()
    lines = [
        re.sub(r"^\s*(?:[-*]|\d+[.)]?)\s*", "", line).strip()
        for line in normalized.splitlines()
        if clean_text(line)
    ]

    raw_steps: list[str] = []
    for line in lines:
        split_steps = re.split(r"(?<=[.!?])\s+(?=[A-Z])", clean_text(line))
        raw_steps.extend(step for step in split_steps if step)

    return [
        {"step": index, "text": step}
        for index, step in enumerate(raw_steps, start=1)
    ]


def normalize_meal_type(value: str) -> str:
    meal_type = clean_text(value).lower()
    if meal_type not in MEAL_TYPES:
        raise ValueError(f"Unsupported meal type '{value}'.")
    return meal_type


def normalize_diet(value: str) -> str | None:
    normalized = clean_text(value).lower()
    if not normalized:
        return None

    mappings = {
        "vegetarian": "vegetarian",
        "vegan": "vegan",
        "non vegetarian": "non-vegetarian",
        "non-vegetarian": "non-vegetarian",
    }
    return mappings.get(normalized, normalized)


def normalize_cuisine(value: str) -> str | None:
    cuisine = clean_text(value)
    return cuisine or None


def parse_recipe_file(path: Path, source_name: str) -> dict[str, Any]:
    raw_text = path.read_text(encoding="utf-8").strip()
    match = SECTION_PATTERN.match(raw_text)
    if match is None:
        raise ValueError(f"{path.name} is missing Ingredients or Instructions sections.")

    fields = parse_header_fields(match.group("header"))
    title = clean_text(fields.get("title")) or path.stem.replace("_", " ").title()
    ingredients = parse_ingredients(match.group("ingredients"))
    instructions = parse_instructions(match.group("instructions"))

    recipe = {
        "id": slugify(title),
        "title": title,
        "sourceUrl": None,
        "sourceName": source_name,
        "mealType": normalize_meal_type(fields.get("mealtype", "")),
        "diet": normalize_diet(fields.get("diet", "")),
        "cuisine": normalize_cuisine(fields.get("cuisine", "")),
        "ingredients": ingredients,
        "instructions": instructions,
        "nutrition": {
            "calories": parse_numeric_value(fields.get("calories", "")),
            "proteinGrams": parse_numeric_value(fields.get("protein", "")),
            "carbsGrams": None,
            "fatGrams": None,
        },
        "image": None,
    }

    validate_recipe(recipe)
    return recipe


def validate_required_keys(record: dict[str, Any], keys: tuple[str, ...], label: str) -> None:
    missing = [key for key in keys if key not in record]
    if missing:
        raise ValueError(f"{label} is missing required keys: {', '.join(missing)}")


def validate_recipe(recipe: dict[str, Any]) -> None:
    validate_required_keys(
        recipe,
        (
            "id",
            "title",
            "sourceUrl",
            "sourceName",
            "mealType",
            "diet",
            "cuisine",
            "ingredients",
            "instructions",
            "nutrition",
            "image",
        ),
        "Recipe",
    )

    if not isinstance(recipe["id"], str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", recipe["id"]):
        raise ValueError(f"Recipe '{recipe.get('title', '<unknown>')}' has an invalid id.")
    if not isinstance(recipe["title"], str) or not recipe["title"].strip():
        raise ValueError("Recipe title must be a non-empty string.")
    if recipe["mealType"] not in MEAL_TYPES:
        raise ValueError(f"Recipe '{recipe['title']}' has invalid mealType '{recipe['mealType']}'.")
    if recipe["sourceUrl"] is not None:
        raise ValueError(f"Seed recipe '{recipe['title']}' must have a null sourceUrl.")
    if recipe["image"] is not None:
        raise ValueError(f"Seed recipe '{recipe['title']}' must have a null image.")

    ingredients = recipe["ingredients"]
    if not isinstance(ingredients, list) or not ingredients:
        raise ValueError(f"Recipe '{recipe['title']}' must include at least one ingredient.")
    for ingredient in ingredients:
        validate_required_keys(
            ingredient,
            ("item", "amount", "unit", "preparation"),
            f"Ingredient in recipe '{recipe['title']}'",
        )
        if not isinstance(ingredient["item"], str) or not ingredient["item"].strip():
            raise ValueError(f"Recipe '{recipe['title']}' includes an invalid ingredient item.")

    instructions = recipe["instructions"]
    if not isinstance(instructions, list) or not instructions:
        raise ValueError(f"Recipe '{recipe['title']}' must include at least one instruction.")
    for index, instruction in enumerate(instructions, start=1):
        validate_required_keys(
            instruction,
            ("step", "text"),
            f"Instruction in recipe '{recipe['title']}'",
        )
        if instruction["step"] != index:
            raise ValueError(f"Recipe '{recipe['title']}' has non-sequential instruction steps.")
        if not isinstance(instruction["text"], str) or not instruction["text"].strip():
            raise ValueError(f"Recipe '{recipe['title']}' includes an empty instruction.")

    nutrition = recipe["nutrition"]
    validate_required_keys(
        nutrition,
        ("calories", "proteinGrams", "carbsGrams", "fatGrams"),
        f"Nutrition for recipe '{recipe['title']}'",
    )
    for key, value in nutrition.items():
        if value is not None and not isinstance(value, (int, float)):
            raise ValueError(f"Nutrition field '{key}' in recipe '{recipe['title']}' must be numeric or null.")


def load_schema_reference(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as schema_file:
        schema = json.load(schema_file)

    recipe_required = tuple(schema["$defs"]["recipe"]["required"])
    top_level_required = tuple(schema["required"])
    if "recipes" not in top_level_required or "id" not in recipe_required:
        raise ValueError("Recipe schema structure is not compatible with the generator.")

    return schema


def validate_artifact(payload: dict[str, Any]) -> None:
    validate_required_keys(payload, ("version", "generatedAt", "sourceType", "recipes"), "Artifact")
    if payload["version"] != "1.0":
        raise ValueError("Artifact version must be '1.0'.")
    if payload["sourceType"] != "manual":
        raise ValueError("Seed artifact sourceType must be 'manual'.")
    if not isinstance(payload["recipes"], list) or not payload["recipes"]:
        raise ValueError("Artifact recipes must be a non-empty list.")

    seen_ids = set()
    meal_counts = Counter()
    for recipe in payload["recipes"]:
        validate_recipe(recipe)
        if recipe["id"] in seen_ids:
            raise ValueError(f"Duplicate recipe id '{recipe['id']}' detected.")
        seen_ids.add(recipe["id"])
        meal_counts[recipe["mealType"]] += 1

    for meal_type in MEAL_TYPES:
        if meal_counts[meal_type] == 0:
            raise ValueError(f"Artifact is missing recipes for meal type '{meal_type}'.")


def build_artifact(recipes: list[dict[str, Any]]) -> dict[str, Any]:
    payload = {
        "version": "1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourceType": "manual",
        "recipes": recipes,
    }
    validate_artifact(payload)
    return payload


def build_sample_recipes(
    recipes: list[dict[str, Any]],
    sample_size_per_meal: int,
) -> list[dict[str, Any]]:
    sample: list[dict[str, Any]] = []
    for meal_type in MEAL_TYPES:
        meal_recipes = [recipe for recipe in recipes if recipe["mealType"] == meal_type]
        sample.extend(meal_recipes[:sample_size_per_meal])
    return sample


def build_indexes(recipes: list[dict[str, Any]]) -> dict[str, list[str]]:
    indexes = {meal_type: [] for meal_type in MEAL_TYPES}
    for recipe in recipes:
        indexes[recipe["mealType"]].append(recipe["title"])

    for meal_type, titles in indexes.items():
        if not titles:
            raise ValueError(f"Cannot build indexes without recipes for '{meal_type}'.")

    return indexes


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, indent=2)
        output_file.write("\n")


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    output_path = Path(args.output).resolve()
    sample_output_path = Path(args.sample_output).resolve()
    schema_path = Path(args.schema).resolve()

    if not input_dir.exists():
        raise ValueError(f"Recipe input directory does not exist: {input_dir}")

    load_schema_reference(schema_path)

    recipes = [
        parse_recipe_file(path, source_name=args.source_name)
        for path in sorted(input_dir.glob("*.txt"))
    ]
    recipes.sort(key=lambda recipe: (recipe["mealType"], recipe["title"]))

    artifact = build_artifact(recipes)
    sample_artifact = build_artifact(
        build_sample_recipes(recipes, sample_size_per_meal=args.sample_size_per_meal)
    )
    indexes = build_indexes(recipes)

    write_json(output_path, artifact)
    write_json(sample_output_path, sample_artifact)
    for meal_type, titles in indexes.items():
        write_json(output_path.parent / f"{meal_type}.json", titles)

    print(
        f"Wrote {len(recipes)} canonical recipe(s), sample artifact, and "
        f"{len(indexes)} meal-type indexes to {output_path.parent}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
