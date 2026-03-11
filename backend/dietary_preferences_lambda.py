import json
import os
from datetime import datetime, timezone

import boto3

TABLE_NAME = os.environ["DIETARY_PREFERENCES_TABLE"]
_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(TABLE_NAME)


def _response(status_code, payload):
    return {
        "statusCode": int(status_code),
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(payload),
    }


def _parse_body(event):
    body = event.get("body")
    if isinstance(body, str):
        if not body:
            return {}
        return json.loads(body)
    if isinstance(body, dict):
        return body

    request_body = event.get("requestBody", {})
    if isinstance(request_body, dict):
        content = request_body.get("content", {})
        if isinstance(content, dict):
            app_json = content.get("application/json", {})
            if isinstance(app_json, dict) and "properties" in app_json:
                properties = app_json["properties"]
                if isinstance(properties, list):
                    parsed = {}
                    for item in properties:
                        name = item.get("name")
                        value = item.get("value")
                        if name:
                            parsed[name] = value
                    return parsed
    return {}


def _extract_route(event):
    method = (event.get("httpMethod") or event.get("action") or "").upper()
    path = event.get("apiPath") or event.get("path") or ""
    return method, path


def _validate_preferences(preferences):
    if not isinstance(preferences, list) or not all(isinstance(item, str) for item in preferences):
        raise ValueError("'preferences' must be a list of strings.")


def _put_preferences(user_id, preferences):
    timestamp = datetime.now(timezone.utc).isoformat()
    _table.put_item(
        Item={
            "userId": user_id,
            "preferences": preferences,
            "updatedAt": timestamp,
        }
    )
    return timestamp


def lambda_handler(event, context):
    try:
        method, path = _extract_route(event)
        body = _parse_body(event)

        if method == "POST" and path == "/dietary-preferences":
            user_id = body.get("userId")
            preferences = body.get("preferences")
            if not user_id:
                raise ValueError("'userId' is required.")
            _validate_preferences(preferences)
            updated_at = _put_preferences(user_id, preferences)
            return _response(
                200,
                {
                    "message": "Dietary preferences saved.",
                    "userId": user_id,
                    "preferences": preferences,
                    "updatedAt": updated_at,
                },
            )

        if method == "PUT" and path.startswith("/dietary-preferences/"):
            user_id = path.rsplit("/", 1)[-1]
            preferences = body.get("preferences")
            if not user_id:
                raise ValueError("'userId' path parameter is required.")
            _validate_preferences(preferences)
            updated_at = _put_preferences(user_id, preferences)
            return _response(
                200,
                {
                    "message": "Dietary preferences updated.",
                    "userId": user_id,
                    "preferences": preferences,
                    "updatedAt": updated_at,
                },
            )

        return _response(
            400,
            {
                "error": f"Unsupported operation for method '{method}' and path '{path}'.",
            },
        )
    except (ValueError, json.JSONDecodeError) as exc:
        return _response(400, {"error": str(exc)})
    except Exception as exc:
        return _response(500, {"error": f"Internal server error: {str(exc)}"})
