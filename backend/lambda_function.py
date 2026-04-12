import json          # Standard library for working with JSON strings/objects
import random        # Standard library for random selection
from pathlib import Path

try:
    import boto3     # pyright: ignore[reportMissingImports]
except ImportError:
    boto3 = None

try:
    from botocore.exceptions import ClientError  # pyright: ignore[reportMissingImports]
except ImportError:
    ClientError = None

# Import configuration and constants
from config import (
    API_VERSION,
    AWS_CONFIG,
    CANONICAL_RECIPE_FILE,
    LOCAL_RECIPE_DATA_ROOT,
    RECIPE_FILES,
    RECIPE_COMPATIBILITY_MODE,
    RECIPE_DATA_SOURCE,
    API_ENDPOINTS,
    HTTP_CONFIG
)
from constants import DAYS_OF_WEEK, MEAL_TYPES

# Extract AWS configuration
BUCKET_NAME = AWS_CONFIG['BUCKET_NAME']

_s3_client = None
OPTIONAL_REQUEST_FIELDS = {
    "preferences",
    "dietaryRestrictions",
    "allergies",
    "excludedIngredients",
}


def get_s3_client():
    global _s3_client

    if boto3 is None:
        raise RuntimeError(
            "boto3 is required when RECIPE_DATA_SOURCE is not 'local'."
        )

    if _s3_client is None:
        _s3_client = boto3.client("s3")

    return _s3_client

def _is_missing_recipe_object_error(exc):
    if isinstance(exc, FileNotFoundError):
        return True

    if ClientError is not None and isinstance(exc, ClientError):
        error_code = exc.response.get("Error", {}).get("Code")
        return error_code in {"404", "NoSuchKey", "NotFound"}

    return exc.__class__.__name__ == "NoSuchKey"


def load_json_object(key, required=True):
    """
    Load JSON content from the configured data source for a given key.

    :param key: Path of the JSON file inside the S3 bucket
                (e.g. 'recipes_json/breakfast.json')
    :param required: When False, return None instead of raising for a missing object
    :return: Python object parsed from the JSON
    """
    if RECIPE_DATA_SOURCE == "local":
        local_path = Path(LOCAL_RECIPE_DATA_ROOT) / key
        if not local_path.exists():
            if required:
                raise FileNotFoundError(f"Recipe file not found: {local_path}")
            return None

        with local_path.open("r", encoding="utf-8") as recipe_file:
            return json.load(recipe_file)

    s3 = get_s3_client()
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
    except Exception as exc:
        if not required and _is_missing_recipe_object_error(exc):
            return None
        raise

    content = response["Body"].read().decode("utf-8")
    return json.loads(content)


def _normalize_recipe_choice(recipe):
    if isinstance(recipe, str) and recipe.strip():
        return recipe

    if isinstance(recipe, dict):
        title = recipe.get("title") or recipe.get("id")
        if isinstance(title, str) and title.strip():
            return title

    raise ValueError("Each recipe entry must be a non-empty string or object with a title.")


def _normalize_recipe_collection(meal, recipe_list):
    if not isinstance(recipe_list, list):
        raise ValueError(f"'{meal}' recipes must be a list.")

    normalized = []
    for recipe in recipe_list:
        _normalize_recipe_choice(recipe)
        normalized.append(recipe)

    if not normalized:
        raise ValueError(f"'{meal}' recipes must contain at least one recipe.")

    return normalized


def _extract_recipe_list(artifact):
    if artifact is None:
        raise ValueError("Canonical recipe artifact is not available.")

    if isinstance(artifact, dict):
        recipe_list = artifact.get("recipes")
    elif isinstance(artifact, list):
        recipe_list = artifact
    else:
        raise ValueError("Canonical recipe artifact must be an object or list.")

    if not isinstance(recipe_list, list) or not recipe_list:
        raise ValueError("Canonical recipe artifact must include a non-empty 'recipes' list.")

    return recipe_list


def load_legacy_recipe_indexes():
    recipes = {}

    for meal, key in RECIPE_FILES.items():
        recipes[meal] = _normalize_recipe_collection(meal, load_json_object(key))

    return recipes


def load_canonical_recipe_artifact(required=False):
    return load_json_object(CANONICAL_RECIPE_FILE, required=required)


def build_meal_indexes_from_canonical(artifact):
    recipe_list = _extract_recipe_list(artifact)

    recipes_by_meal = {meal: [] for meal in MEAL_TYPES}

    for recipe in recipe_list:
        if not isinstance(recipe, dict):
            raise ValueError("Canonical recipes must be objects.")

        meal_type = recipe.get("mealType")
        if meal_type not in recipes_by_meal:
            raise ValueError(
                "Canonical recipe entries must include a valid 'mealType'."
            )

        recipes_by_meal[meal_type].append(recipe)

    for meal, meal_recipes in recipes_by_meal.items():
        recipes_by_meal[meal] = _normalize_recipe_collection(meal, meal_recipes)

    return recipes_by_meal


def _recipe_lookup_keys(value):
    if not isinstance(value, str):
        return []

    cleaned = value.strip()
    if not cleaned:
        return []

    return [cleaned, cleaned.lower()]


def build_recipe_lookup_from_canonical(artifact):
    lookup = {}

    for recipe in _extract_recipe_list(artifact):
        if not isinstance(recipe, dict):
            raise ValueError("Canonical recipes must be objects.")

        for field_name in ("id", "title"):
            for key in _recipe_lookup_keys(recipe.get(field_name)):
                lookup[key] = recipe

    return lookup


def empty_nutrition():
    return {
        "calories": None,
        "proteinGrams": None,
        "carbsGrams": None,
        "fatGrams": None,
    }


def _shape_ingredients(value):
    if not isinstance(value, list):
        return []

    shaped = []
    for ingredient in value:
        if not isinstance(ingredient, dict):
            continue

        shaped.append(
            {
                "item": ingredient.get("item"),
                "amount": ingredient.get("amount"),
                "unit": ingredient.get("unit"),
                "preparation": ingredient.get("preparation"),
            }
        )

    return shaped


def _shape_instructions(value):
    if not isinstance(value, list):
        return []

    shaped = []
    for index, instruction in enumerate(value, start=1):
        if isinstance(instruction, dict):
            text = instruction.get("text")
            step = instruction.get("step", index)
        else:
            text = instruction
            step = index

        if not isinstance(text, str) or not text.strip():
            continue

        shaped.append({"step": step, "text": text.strip()})

    return shaped


def _shape_nutrition(value):
    nutrition = empty_nutrition()
    if not isinstance(value, dict):
        return nutrition

    for key in nutrition:
        nutrition[key] = value.get(key)

    return nutrition


def _build_recipe_detail(recipe, meal_type, canonical_lookup=None):
    if isinstance(recipe, dict):
        source_recipe = recipe
    elif isinstance(recipe, str):
        source_recipe = None
        if canonical_lookup is not None:
            for key in _recipe_lookup_keys(recipe):
                if key in canonical_lookup:
                    source_recipe = canonical_lookup[key]
                    break

        source_recipe = source_recipe or {
            "id": None,
            "title": recipe.strip(),
            "mealType": meal_type,
            "diet": None,
            "cuisine": None,
            "ingredients": [],
            "instructions": [],
            "nutrition": empty_nutrition(),
        }
    else:
        raise ValueError("Each recipe entry must be a non-empty string or object with a title.")

    title = _normalize_recipe_choice(source_recipe)
    return {
        "id": source_recipe.get("id"),
        "title": title,
        "mealType": source_recipe.get("mealType") or meal_type,
        "diet": source_recipe.get("diet"),
        "cuisine": source_recipe.get("cuisine"),
        "sourceName": source_recipe.get("sourceName"),
        "sourceUrl": source_recipe.get("sourceUrl"),
        "ingredients": _shape_ingredients(source_recipe.get("ingredients")),
        "instructions": _shape_instructions(source_recipe.get("instructions")),
        "nutrition": _shape_nutrition(source_recipe.get("nutrition")),
    }


def load_canonical_recipe_lookup(required=False):
    artifact = load_canonical_recipe_artifact(required=required)
    if artifact is None:
        return None

    return build_recipe_lookup_from_canonical(artifact)


def load_all_recipes():
    compatibility_mode = RECIPE_COMPATIBILITY_MODE

    if compatibility_mode not in {"auto", "indexes", "canonical"}:
        raise ValueError(
            "RECIPE_COMPATIBILITY_MODE must be one of: auto, indexes, canonical."
        )

    if compatibility_mode == "indexes":
        return load_legacy_recipe_indexes()

    canonical_artifact = load_canonical_recipe_artifact(
        required=(compatibility_mode == "canonical")
    )

    if compatibility_mode == "canonical":
        return build_meal_indexes_from_canonical(canonical_artifact)

    if canonical_artifact is not None:
        try:
            return build_meal_indexes_from_canonical(canonical_artifact)
        except (ValueError, TypeError, KeyError):
            pass

    return load_legacy_recipe_indexes()


def build_week_plan(recipes):
    week_plan = []
    canonical_lookup = None

    # Legacy title-only indexes can still be enriched from the canonical artifact.
    if any(
        isinstance(recipe, str)
        for meal in MEAL_TYPES
        for recipe in recipes.get(meal, [])
    ):
        try:
            canonical_lookup = load_canonical_recipe_lookup(required=False)
        except (ValueError, TypeError, KeyError, FileNotFoundError):
            canonical_lookup = None

    for day in DAYS_OF_WEEK:
        day_plan = {
            "day": day,
            "breakfast": _build_recipe_detail(
                random.choice(recipes["breakfast"]),
                "breakfast",
                canonical_lookup=canonical_lookup,
            ),
            "lunch": _build_recipe_detail(
                random.choice(recipes["lunch"]),
                "lunch",
                canonical_lookup=canonical_lookup,
            ),
            "snack": _build_recipe_detail(
                random.choice(recipes["snack"]),
                "snack",
                canonical_lookup=canonical_lookup,
            ),
            "dinner": _build_recipe_detail(
                random.choice(recipes["dinner"]),
                "dinner",
                canonical_lookup=canonical_lookup,
            ),
        }
        week_plan.append(day_plan)

    return week_plan


def response(status_code, payload):
    body = payload
    if not isinstance(body, str):
        body = json.dumps(body)

    return {
        "statusCode": int(status_code),
        "headers": HTTP_CONFIG["HEADERS"].copy(),
        "body": body,
    }


def _validate_string_list_field(name, value):
    if value is None:
        return

    if isinstance(value, str):
        return

    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return

    raise ValueError(
        f"'{name}' must be a string or a list of strings when provided."
    )


def validate_request(body):
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object.")

    for field_name in OPTIONAL_REQUEST_FIELDS:
        if field_name not in body:
            continue

        if field_name == "preferences":
            value = body[field_name]
            if value is None:
                continue
            if isinstance(value, (str, dict)):
                continue
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                continue
            raise ValueError(
                "'preferences' must be a string, object, or list of strings when provided."
            )

        _validate_string_list_field(field_name, body[field_name])


def build_planning_context(body):
    # Assemble inputs for plan generation; extend here if external sources are added later.
    return {
        "recipes": load_all_recipes(),
        "request": {
            key: body[key]
            for key in OPTIONAL_REQUEST_FIELDS
            if key in body and body[key] is not None
        },
    }


def generate_structured_plan(body, planning_context):
    recipes = planning_context.get("recipes") or load_all_recipes()
    return {"week": build_week_plan(recipes)}

def lambda_handler(event, context):
    """
    Main Lambda entry point.

    :param event: Data passed in by the invoker (API Gateway, test event, etc.)
    :param context: Runtime information about the Lambda invocation

    Steps:
      1. Load recipe data from the canonical artifact when available, or fall back
         to the legacy meal-type indexes.
      2. For each day of the week, randomly choose one recipe from each meal list.
      3. Build a 'week' array containing one object per day.
      4. Return an HTTP-style JSON response with CORS headers.
    """
    # Determine API version from event path
    path = event.get("resource") or event.get("path", "")

    # Route to appropriate version handler based on path
    v2_endpoint = API_ENDPOINTS['v2']['generate_meal_plan']
    if path == v2_endpoint:
        return handle_v2(event)

    recipes = load_all_recipes()
    week_plan = build_week_plan(recipes)
    return response(HTTP_CONFIG["DEFAULT_STATUS_CODE"], {"week": week_plan})


def handle_v2(event):
    try:
        body = json.loads(event.get("body") or "{}")
        validate_request(body)

        planning_context = build_planning_context(body)
        meal_plan = generate_structured_plan(body, planning_context)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return response(400, {"error": str(exc)})

    return response(200, meal_plan)