#!/usr/bin/env python3
"""Import curated recipe blog pages into PantryBuddy's canonical recipe artifact."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


MEAL_TYPES = ("breakfast", "lunch", "snack", "dinner")
USER_AGENT = "PantryBuddyImporter/1.0 (+https://pantrybuddy.dev)"
JSON_LD_SCRIPT_RE = re.compile(
    r"<script[^>]*type=[\"'][^\"']*ld\+json[^\"']*[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
NUMBER_RE = re.compile(r"(?<![A-Za-z])(\d+(?:\.\d+)?)")

MEAL_KEYWORDS = {
    "breakfast": (
        "breakfast",
        "brunch",
        "toast",
        "pancake",
        "oatmeal",
        "granola",
        "omelet",
        "smoothie",
    ),
    "lunch": (
        "lunch",
        "salad",
        "sandwich",
        "wrap",
        "bowl",
        "soup",
    ),
    "snack": (
        "snack",
        "bite",
        "bars",
        "chips",
        "dip",
        "cracker",
        "energy ball",
    ),
    "dinner": (
        "dinner",
        "main",
        "entree",
        "curry",
        "pasta",
        "roast",
        "stir fry",
        "stew",
    ),
}

DIET_KEYWORDS = {
    "vegan": ("vegan",),
    "vegetarian": ("vegetarian", "meatless"),
    "gluten-free": ("gluten free", "gluten-free"),
    "dairy-free": ("dairy free", "dairy-free"),
}

DIET_URL_MAP = {
    "https://schema.org/veganDiet": "vegan",
    "https://schema.org/vegetarianDiet": "vegetarian",
    "https://schema.org/glutenFreeDiet": "gluten-free",
    "https://schema.org/lowFatDiet": "low-fat",
    "https://schema.org/lowSaltDiet": "low-salt",
}

INGREDIENT_HEADINGS = ("ingredient", "ingredients")
INSTRUCTION_HEADINGS = ("instruction", "instructions", "direction", "directions", "method")


@dataclass
class SourceEntry:
    url: str
    meal_type: str | None = None
    diet: str | None = None
    cuisine: str | None = None
    source_name: str | None = None


class RecipePageParser(HTMLParser):
    """Collect lightweight metadata and section text for fallback extraction."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self.first_h1 = ""
        self.current_heading = ""
        self.ordered_tokens: list[tuple[str, str, str]] = []
        self._capture_tag: str | None = None
        self._capture_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value for key, value in attrs if value is not None}

        if tag == "meta":
            meta_key = (
                attr_map.get("property")
                or attr_map.get("name")
                or attr_map.get("itemprop")
            )
            content = attr_map.get("content")
            if meta_key and content:
                self.meta[meta_key.lower()] = clean_text(content)
            return

        if tag in {"title", "h1", "h2", "h3", "h4", "h5", "h6", "li", "p"}:
            self._capture_tag = tag
            self._capture_chunks = []

    def handle_data(self, data: str) -> None:
        if self._capture_tag is not None:
            self._capture_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != self._capture_tag:
            return

        text = clean_text("".join(self._capture_chunks))
        capture_tag = self._capture_tag
        self._capture_tag = None
        self._capture_chunks = []

        if not text:
            return

        if capture_tag == "title":
            self.title = text
        elif capture_tag == "h1":
            if not self.first_h1:
                self.first_h1 = text
            self.current_heading = text
            self.ordered_tokens.append(("heading", text.lower(), text))
        elif capture_tag in {"h2", "h3", "h4", "h5", "h6"}:
            self.current_heading = text
            self.ordered_tokens.append(("heading", text.lower(), text))
        elif capture_tag in {"li", "p"}:
            self.ordered_tokens.append(("text", self.current_heading.lower(), text))


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return WHITESPACE_RE.sub(" ", unescape(str(value).strip()))


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", clean_text(value).lower()).strip("-")
    return slug or "recipe"


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch curated recipe pages, extract schema.org Recipe data with "
            "fallback HTML parsing, and write PantryBuddy canonical recipe JSON."
        )
    )
    parser.add_argument(
        "--sources",
        required=True,
        help=(
            "JSON file containing curated source entries. Each item may be a URL string "
            "or an object with url plus optional mealType/diet/cuisine/sourceName."
        ),
    )
    parser.add_argument(
        "--output",
        default="data/recipes_json/recipes.json",
        help="Path to the canonical recipe artifact to write.",
    )
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="Merge imported recipes into the existing output artifact instead of replacing it.",
    )
    parser.add_argument(
        "--write-indexes",
        action="store_true",
        help="Also write breakfast/lunch/snack/dinner index files beside the canonical artifact.",
    )
    parser.add_argument(
        "--index-value-field",
        choices=("title", "id"),
        default="title",
        help="Canonical recipe field to emit into generated meal index files.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds for fetching each source page.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-source import details.",
    )
    return parser.parse_args()


def load_sources(path: Path) -> list[SourceEntry]:
    with path.open("r", encoding="utf-8") as source_file:
        payload = json.load(source_file)

    if not isinstance(payload, list) or not payload:
        raise ValueError("Source manifest must be a non-empty JSON array.")

    sources: list[SourceEntry] = []
    for raw_entry in payload:
        if isinstance(raw_entry, str):
            entry = {"url": raw_entry}
        elif isinstance(raw_entry, dict):
            entry = raw_entry
        else:
            raise ValueError("Each source entry must be a URL string or JSON object.")

        url = clean_text(entry.get("url"))
        if not url:
            raise ValueError("Each source entry must include a non-empty 'url'.")

        meal_type = clean_text(entry.get("mealType") or "") or None
        if meal_type is not None and meal_type not in MEAL_TYPES:
            raise ValueError(
                f"Invalid mealType '{meal_type}' in source manifest. "
                f"Expected one of {', '.join(MEAL_TYPES)}."
            )

        sources.append(
            SourceEntry(
                url=url,
                meal_type=meal_type,
                diet=clean_text(entry.get("diet") or "") or None,
                cuisine=clean_text(entry.get("cuisine") or "") or None,
                source_name=clean_text(entry.get("sourceName") or "") or None,
            )
        )

    return sources


def fetch_source(entry: SourceEntry, timeout: float) -> tuple[str, str]:
    if entry.url.startswith("file://"):
        local_path = Path(entry.url[7:])
        return local_path.read_text(encoding="utf-8"), entry.url

    request = Request(
        entry.url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(content_type, errors="replace")
        return html, response.geturl()


def extract_json_ld_nodes(html: str) -> list[dict[str, Any]]:
    recipe_nodes: list[dict[str, Any]] = []
    for raw_json in JSON_LD_SCRIPT_RE.findall(html):
        cleaned = clean_json_text(raw_json)
        if not cleaned:
            continue

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            continue

        recipe_nodes.extend(list(flatten_recipe_nodes(payload)))

    return recipe_nodes


def clean_json_text(raw_json: str) -> str:
    cleaned = raw_json.strip()
    if cleaned.startswith("<!--") and cleaned.endswith("-->"):
        cleaned = cleaned[4:-3].strip()
    return cleaned


def flatten_recipe_nodes(payload: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for item in as_list(payload):
        if isinstance(item, dict):
            if is_recipe_node(item):
                nodes.append(item)
            if "@graph" in item:
                nodes.extend(flatten_recipe_nodes(item["@graph"]))
    return nodes


def is_recipe_node(node: dict[str, Any]) -> bool:
    raw_type = node.get("@type")
    for candidate in as_list(raw_type):
        if isinstance(candidate, str) and candidate.lower() == "recipe":
            return True
    return False


def import_recipe(entry: SourceEntry, timeout: float) -> dict[str, Any]:
    html, resolved_url = fetch_source(entry, timeout)
    json_ld_nodes = extract_json_ld_nodes(html)

    recipe_data = None
    for node in json_ld_nodes:
        try:
            recipe_data = normalize_recipe_from_schema(node, entry, resolved_url)
        except ValueError:
            continue
        if recipe_data is not None:
            break

    if recipe_data is None:
        recipe_data = normalize_recipe_from_fallback(html, entry, resolved_url)

    validate_recipe(recipe_data)
    return recipe_data


def normalize_recipe_from_schema(
    node: dict[str, Any],
    entry: SourceEntry,
    resolved_url: str,
) -> dict[str, Any]:
    title = first_non_empty(
        node.get("name"),
        node.get("headline"),
        node.get("alternateName"),
    )
    if not title:
        raise ValueError("Schema.org recipe node does not include a usable title.")

    ingredients = normalize_ingredients(node.get("recipeIngredient"))
    instructions = normalize_instructions(node.get("recipeInstructions"))
    if not ingredients or not instructions:
        raise ValueError("Schema.org recipe node is missing ingredients or instructions.")

    keyword_text = " ".join(
        filter(
            None,
            [
                title,
                flatten_text(node.get("recipeCategory")),
                flatten_text(node.get("keywords")),
                flatten_text(node.get("description")),
            ],
        )
    )

    source_name = (
        entry.source_name
        or extract_name(node.get("publisher"))
        or extract_name(node.get("author"))
        or source_name_from_url(resolved_url)
    )

    return {
        "id": build_recipe_id(title, resolved_url),
        "title": title,
        "sourceUrl": normalize_url(first_non_empty(node.get("url"), resolved_url)),
        "sourceName": source_name,
        "mealType": infer_meal_type(entry.meal_type, node.get("recipeCategory"), keyword_text),
        "diet": infer_diet(entry.diet, node.get("suitableForDiet"), keyword_text),
        "cuisine": entry.cuisine or normalize_optional_string(flatten_text(node.get("recipeCuisine"))),
        "ingredients": ingredients,
        "instructions": instructions,
        "nutrition": normalize_nutrition(node.get("nutrition")),
        "image": extract_image_url(node.get("image")),
    }


def normalize_recipe_from_fallback(
    html: str,
    entry: SourceEntry,
    resolved_url: str,
) -> dict[str, Any]:
    parser = RecipePageParser()
    parser.feed(html)

    title = (
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or parser.first_h1
        or parser.title
    )
    title = clean_text(title)
    if not title:
        raise ValueError(f"Could not determine a recipe title for {resolved_url}.")

    ingredients = normalize_ingredients(extract_section_items(parser.ordered_tokens, INGREDIENT_HEADINGS))
    instructions = normalize_instructions(extract_section_items(parser.ordered_tokens, INSTRUCTION_HEADINGS))
    if not ingredients or not instructions:
        raise ValueError(
            f"Could not extract ingredients and instructions from {resolved_url}."
        )

    keyword_text = " ".join(
        filter(
            None,
            [
                title,
                parser.meta.get("description"),
                parser.meta.get("keywords"),
                parser.meta.get("og:description"),
            ],
        )
    )

    source_name = (
        entry.source_name
        or parser.meta.get("og:site_name")
        or parser.meta.get("application-name")
        or source_name_from_url(resolved_url)
    )

    return {
        "id": build_recipe_id(title, resolved_url),
        "title": title,
        "sourceUrl": normalize_url(resolved_url),
        "sourceName": source_name,
        "mealType": infer_meal_type(entry.meal_type, None, keyword_text),
        "diet": infer_diet(entry.diet, None, keyword_text),
        "cuisine": entry.cuisine,
        "ingredients": ingredients,
        "instructions": instructions,
        "nutrition": empty_nutrition(),
        "image": normalize_url(parser.meta.get("og:image") or parser.meta.get("twitter:image")),
    }


def first_non_empty(*values: Any) -> str | None:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return None


def flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return flatten_text(value.get("name") or value.get("text") or "")
    return ", ".join(filter(None, (clean_text(item) for item in as_list(value))))


def extract_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return first_non_empty(value.get("name"))
    if isinstance(value, list):
        for item in value:
            name = extract_name(item)
            if name:
                return name
    return first_non_empty(value)


def extract_image_url(value: Any) -> str | None:
    if isinstance(value, dict):
        return normalize_url(value.get("url") or value.get("contentUrl"))
    if isinstance(value, list):
        for item in value:
            candidate = extract_image_url(item)
            if candidate:
                return candidate
        return None
    return normalize_url(value)


def source_name_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not host:
        return None
    return host.removeprefix("www.")


def normalize_optional_string(value: Any) -> str | None:
    text = clean_text(value)
    return text or None


def normalize_url(value: Any) -> str | None:
    text = clean_text(value)
    return text or None


def infer_meal_type(override: str | None, recipe_category: Any, keyword_text: str) -> str:
    if override in MEAL_TYPES:
        return override

    haystack = " ".join(filter(None, [flatten_text(recipe_category), clean_text(keyword_text)])).lower()
    for meal_type, keywords in MEAL_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return meal_type

    raise ValueError("Could not infer mealType. Add mealType to the curated source entry.")


def infer_diet(override: str | None, suitable_for_diet: Any, keyword_text: str) -> str | None:
    if override:
        return override

    raw_diets = [clean_text(item).lower() for item in as_list(suitable_for_diet)]
    for raw_diet in raw_diets:
        if raw_diet in DIET_URL_MAP:
            return DIET_URL_MAP[raw_diet]
        if raw_diet:
            return raw_diet.rsplit("/", 1)[-1].replace("diet", "").strip("- ") or raw_diet

    lowered_keywords = clean_text(keyword_text).lower()
    for diet_name, keywords in DIET_KEYWORDS.items():
        if any(keyword in lowered_keywords for keyword in keywords):
            return diet_name

    return None


def normalize_ingredients(value: Any) -> list[dict[str, Any]]:
    ingredients: list[dict[str, Any]] = []
    for raw_ingredient in as_list(value):
        line = extract_instruction_text(raw_ingredient)
        if not line:
            continue

        amount, unit, item = split_ingredient_line(line)
        ingredients.append(
            {
                "item": item,
                "amount": amount,
                "unit": unit,
                "preparation": None,
            }
        )

    return ingredients


def split_ingredient_line(line: str) -> tuple[float | str | None, str | None, str]:
    cleaned = clean_text(line)
    if not cleaned:
        raise ValueError("Ingredient line cannot be empty.")

    match = NUMBER_RE.match(cleaned)
    if match:
        raw_amount = match.group(1)
        amount: float | str | None
        amount = float(raw_amount)
        if amount.is_integer():
            amount = int(amount)
        remainder = cleaned[match.end():].strip(" -")
        parts = remainder.split(" ", 1)
        if len(parts) == 2 and len(parts[0]) <= 12:
            unit_candidate, item = parts
            unit = unit_candidate or None
        else:
            unit = None
            item = remainder or cleaned
        return amount, unit, item

    return None, None, cleaned


def normalize_instructions(value: Any) -> list[dict[str, Any]]:
    steps: list[str] = []
    for raw_step in as_list(value):
        if isinstance(raw_step, dict) and is_how_to_section(raw_step):
            for nested_step in as_list(raw_step.get("itemListElement")):
                step_text = extract_instruction_text(nested_step)
                if step_text:
                    steps.append(step_text)
            continue

        step_text = extract_instruction_text(raw_step)
        if step_text:
            steps.append(step_text)

    return [
        {"step": index, "text": step_text}
        for index, step_text in enumerate(steps, start=1)
    ]


def is_how_to_section(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    for candidate in as_list(value.get("@type")):
        if isinstance(candidate, str) and candidate.lower() == "howtosection":
            return True
    return False


def extract_instruction_text(value: Any) -> str:
    if isinstance(value, dict):
        return clean_text(value.get("text") or value.get("name"))
    return clean_text(value)


def normalize_nutrition(value: Any) -> dict[str, float | None]:
    if not isinstance(value, dict):
        return empty_nutrition()

    return {
        "calories": parse_numeric_value(value.get("calories")),
        "proteinGrams": parse_numeric_value(value.get("proteinContent")),
        "carbsGrams": parse_numeric_value(value.get("carbohydrateContent")),
        "fatGrams": parse_numeric_value(value.get("fatContent")),
    }


def parse_numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = clean_text(value)
    if not text:
        return None
    match = NUMBER_RE.search(text)
    if not match:
        return None
    return float(match.group(1))


def empty_nutrition() -> dict[str, None]:
    return {
        "calories": None,
        "proteinGrams": None,
        "carbsGrams": None,
        "fatGrams": None,
    }


def extract_section_items(
    ordered_tokens: list[tuple[str, str, str]],
    heading_keywords: tuple[str, ...],
) -> list[str]:
    collected: list[str] = []
    collecting = False

    for token_type, heading_context, text in ordered_tokens:
        if token_type == "heading":
            collecting = any(keyword in heading_context for keyword in heading_keywords)
            continue

        if collecting and token_type == "text" and text:
            collected.append(text)

    return collected


def build_recipe_id(title: str, source_url: str) -> str:
    slug = slugify(title)
    parsed = urlparse(source_url)
    suffix = slugify(parsed.path.rsplit("/", 1)[-1]) if parsed.path else ""
    if suffix and suffix != slug:
        return f"{slug}-{suffix}"
    return slug


def validate_recipe(recipe: dict[str, Any]) -> None:
    required_fields = (
        "id",
        "title",
        "sourceUrl",
        "sourceName",
        "mealType",
        "ingredients",
        "instructions",
        "nutrition",
    )
    for field_name in required_fields:
        if field_name not in recipe:
            raise ValueError(f"Recipe is missing required field '{field_name}'.")

    if recipe["mealType"] not in MEAL_TYPES:
        raise ValueError("Recipe mealType must be one of the PantryBuddy meal types.")

    if not isinstance(recipe["ingredients"], list) or not recipe["ingredients"]:
        raise ValueError("Recipe must contain at least one ingredient.")
    if not isinstance(recipe["instructions"], list) or not recipe["instructions"]:
        raise ValueError("Recipe must contain at least one instruction.")


def load_existing_artifact(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as existing_file:
        payload = json.load(existing_file)

    if isinstance(payload, dict):
        recipes = payload.get("recipes", [])
    elif isinstance(payload, list):
        recipes = payload
    else:
        raise ValueError("Existing recipe artifact must be an object or list.")

    if not isinstance(recipes, list):
        raise ValueError("Existing recipe artifact must include a 'recipes' list.")

    return recipes


def merge_recipes(
    existing: list[dict[str, Any]],
    imported: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_keys: dict[tuple[str, str], int] = {}

    def upsert(recipe: dict[str, Any]) -> None:
        keys = recipe_identity_keys(recipe)
        for key in keys:
            if key in seen_keys:
                merged[seen_keys[key]] = recipe
                for refresh_key in keys:
                    seen_keys[refresh_key] = seen_keys[key]
                return

        index = len(merged)
        merged.append(recipe)
        for key in keys:
            seen_keys[key] = index

    for recipe in existing:
        upsert(recipe)
    for recipe in imported:
        upsert(recipe)

    return sorted(merged, key=lambda recipe: (recipe.get("mealType", ""), recipe.get("title", "")))


def recipe_identity_keys(recipe: dict[str, Any]) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    recipe_id = clean_text(recipe.get("id"))
    if recipe_id:
        keys.append(("id", recipe_id))
    source_url = clean_text(recipe.get("sourceUrl"))
    if source_url:
        keys.append(("sourceUrl", source_url))
    return keys


def determine_source_type(recipes: list[dict[str, Any]]) -> str:
    has_imported = any(recipe.get("sourceUrl") for recipe in recipes)
    has_manual = any(not recipe.get("sourceUrl") for recipe in recipes)
    if has_imported and has_manual:
        return "mixed"
    if has_imported:
        return "imported"
    return "manual"


def write_artifact(path: Path, recipes: list[dict[str, Any]]) -> None:
    payload = {
        "version": "1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourceType": determine_source_type(recipes),
        "recipes": recipes,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, indent=2)
        output_file.write("\n")


def build_indexes(recipes: list[dict[str, Any]], value_field: str) -> dict[str, list[str]]:
    indexes = {meal: [] for meal in MEAL_TYPES}
    for recipe in recipes:
        meal_type = recipe.get("mealType")
        if meal_type not in indexes:
            raise ValueError(f"Recipe '{recipe.get('id')}' has invalid mealType '{meal_type}'.")

        value = clean_text(recipe.get(value_field) or recipe.get("title") or recipe.get("id"))
        if not value:
            raise ValueError(
                f"Recipe '{recipe.get('id')}' is missing a usable '{value_field}' value."
            )
        indexes[meal_type].append(value)

    for meal_type, values in indexes.items():
        if not values:
            raise ValueError(
                f"Cannot write meal indexes because no recipes were found for '{meal_type}'."
            )

    return indexes


def write_indexes(output_dir: Path, indexes: dict[str, list[str]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for meal_type, values in indexes.items():
        output_path = output_dir / f"{meal_type}.json"
        with output_path.open("w", encoding="utf-8") as output_file:
            json.dump(values, output_file, indent=2)
            output_file.write("\n")


def main() -> int:
    args = parse_args()
    sources_path = Path(args.sources).resolve()
    output_path = Path(args.output).resolve()
    sources = load_sources(sources_path)

    imported: list[dict[str, Any]] = []
    failures: list[tuple[str, str]] = []

    for entry in sources:
        try:
            recipe = import_recipe(entry, timeout=args.timeout)
        except Exception as exc:  # noqa: BLE001
            failures.append((entry.url, str(exc)))
            if args.verbose:
                print(f"FAILED {entry.url}: {exc}")
            continue

        imported.append(recipe)
        if args.verbose:
            print(f"IMPORTED {recipe['title']} from {entry.url}")

    if not imported:
        print("No recipes were imported successfully.")
        for url, error in failures:
            print(f"- {url}: {error}")
        return 1

    existing = load_existing_artifact(output_path) if args.merge_existing else []
    recipes = merge_recipes(existing, imported) if args.merge_existing else imported
    write_artifact(output_path, recipes)

    if args.write_indexes:
        indexes = build_indexes(recipes, args.index_value_field)
        write_indexes(output_path.parent, indexes)

    print(
        f"Imported {len(imported)} recipe(s); wrote {len(recipes)} canonical recipe(s) "
        f"to {output_path}."
    )
    if failures:
        print(f"Skipped {len(failures)} source(s):")
        for url, error in failures:
            print(f"- {url}: {error}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
