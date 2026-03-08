import json          # Standard library for working with JSON strings/objects
import random        # Standard library for random selection
from pathlib import Path

try:
    import boto3     # AWS SDK for Python, used to talk to S3 and other AWS services
except ImportError:
    boto3 = None

# Import configuration and constants
from config import (
    API_VERSION,
    AWS_CONFIG,
    LOCAL_RECIPE_DATA_ROOT,
    RECIPE_FILES,
    RECIPE_DATA_SOURCE,
    API_ENDPOINTS,
    HTTP_CONFIG
)
from constants import DAYS_OF_WEEK

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

def load_recipes(key):
    """
    Load a list of recipes from the configured data source for a given key.

    :param key: Path of the JSON file inside the S3 bucket
                (e.g. 'recipes_json/breakfast.json')
    :return: Python object parsed from the JSON (expected to be a list of recipes)
    """
    if RECIPE_DATA_SOURCE == "local":
        local_path = Path(LOCAL_RECIPE_DATA_ROOT) / key
        with local_path.open("r", encoding="utf-8") as recipe_file:
            return json.load(recipe_file)

    # Fetch the object from S3
    s3 = get_s3_client()
    response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
    # Read the file content from the streaming body and decode bytes to string
    content = response["Body"].read().decode("utf-8")
    # Parse JSON string into a Python object (e.g. list of recipe names)
    return json.loads(content)


def load_all_recipes():
    recipes = {}

    for meal, key in RECIPE_FILES.items():
        recipes[meal] = load_recipes(key)

    return recipes


def build_week_plan(recipes):
    week_plan = []

    for day in DAYS_OF_WEEK:
        day_plan = {
            "day": day,
            "breakfast": random.choice(recipes["breakfast"]),
            "lunch": random.choice(recipes["lunch"]),
            "snack": random.choice(recipes["snack"]),
            "dinner": random.choice(recipes["dinner"]),
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


def retrieve_from_kb(body):
    # Preserve the retrieval boundary for a future knowledge-base integration.
    return {
        "recipes": load_all_recipes(),
        "request": {
            key: body[key]
            for key in OPTIONAL_REQUEST_FIELDS
            if key in body and body[key] is not None
        },
    }


def generate_structured_plan(body, retrieved_context):
    recipes = retrieved_context.get("recipes") or load_all_recipes()
    return {"week": build_week_plan(recipes)}

def lambda_handler(event, context):
    """
    Main Lambda entry point.

    :param event: Data passed in by the invoker (API Gateway, test event, etc.)
    :param context: Runtime information about the Lambda invocation

    Steps:
      1. Load all recipe lists (breakfast/lunch/snack/dinner) from S3.
      2. For each day of the week, randomly choose one recipe from each list.
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

        retrieved_context = retrieve_from_kb(body)
        meal_plan = generate_structured_plan(body, retrieved_context)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return response(400, {"error": str(exc)})

    return response(200, meal_plan)