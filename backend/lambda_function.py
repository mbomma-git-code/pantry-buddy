import json          # Standard library for working with JSON strings/objects
import random        # Standard library for random selection
import boto3         # AWS SDK for Python, used to talk to S3 and other AWS services

# Import configuration and constants
from config import (
    API_VERSION,
    AWS_CONFIG,
    RECIPE_FILES,
    API_ENDPOINTS,
    HTTP_CONFIG
)
from constants import DAYS_OF_WEEK

# Create an S3 client using the Lambda's IAM role credentials
s3 = boto3.client("s3")

# Extract AWS configuration
BUCKET_NAME = AWS_CONFIG['BUCKET_NAME']

def load_recipes(key):
    """
    Load a list of recipes from S3 for a given object key.

    :param key: Path of the JSON file inside the S3 bucket
                (e.g. 'recipes_json/breakfast.json')
    :return: Python object parsed from the JSON (expected to be a list of recipes)
    """
    # Fetch the object from S3
    response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
    # Read the file content from the streaming body and decode bytes to string
    content = response["Body"].read().decode("utf-8")
    # Parse JSON string into a Python object (e.g. list of recipe names)
    return json.loads(content)

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
    recipes = {}
    # Load each meal's recipes from S3 and store them under their meal key
    for meal, key in RECIPE_FILES.items():
        recipes[meal] = load_recipes(key)

    week_plan = []

    # Build a daily plan for each day in the week
    for day in DAYS_OF_WEEK:
        day_plan = {
            "day": day,
            # Pick one random recipe from each meal category's list
            "breakfast": random.choice(recipes["breakfast"]),
            "lunch": random.choice(recipes["lunch"]),
            "snack": random.choice(recipes["snack"]),
            "dinner": random.choice(recipes["dinner"])
        }
        week_plan.append(day_plan)


    # Determine API version from event path
    path = event.get("resource") or event.get("path", "")
    
    # Route to appropriate version handler based on path
    v2_endpoint = API_ENDPOINTS['v2']['generate_meal_plan']
    if path == v2_endpoint:
        return handle_v2(event)

    # Return an HTTP-style response, suitable for API Gateway proxy integration
    return {
        "statusCode": HTTP_CONFIG['DEFAULT_STATUS_CODE'],
        "headers": HTTP_CONFIG['HEADERS'].copy(),
        "body": json.dumps({
            "week": week_plan
        })
    }


def handle_v2(event):
    body = json.loads(event["body"])
    validate_request(body)
    
    retrieved_context = retrieve_from_kb(body)
    meal_plan = generate_structured_plan(body, retrieved_context)
    
    return response(200, meal_plan)