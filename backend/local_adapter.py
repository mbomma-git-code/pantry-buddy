"""
Local HTTP adapter for the Lambda handler.

This lets the static frontend call a normal local URL while preserving the
Lambda's existing API Gateway proxy-style event contract.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from config import API_ENDPOINTS, HTTP_CONFIG
from lambda_function import lambda_handler


DEFAULT_HOST = os.environ.get("LOCAL_ADAPTER_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("LOCAL_ADAPTER_PORT", "8000"))
SUPPORTED_PATHS = {
    endpoint
    for version_endpoints in API_ENDPOINTS.values()
    for endpoint in version_endpoints.values()
}


def _normalize_header_value(value):
    if value is None:
        return ""
    return value


def normalize_supported_path(raw_path):
    if raw_path in SUPPORTED_PATHS:
        return raw_path

    # Accept trailing slash variants locally while preserving configured endpoints.
    if raw_path.endswith("/"):
        without_trailing_slash = raw_path.rstrip("/")
        if without_trailing_slash in SUPPORTED_PATHS:
            return without_trailing_slash

    return None


def build_event(handler, resolved_path):
    parsed_url = urlparse(handler.path)
    raw_body = ""

    content_length = int(handler.headers.get("Content-Length", "0") or "0")
    if content_length > 0:
        raw_body = handler.rfile.read(content_length).decode("utf-8")

    query_params = {
        key: values[-1]
        for key, values in parse_qs(parsed_url.query, keep_blank_values=True).items()
    }

    return {
        "resource": resolved_path,
        "path": resolved_path,
        "httpMethod": handler.command,
        "headers": {key: value for key, value in handler.headers.items()},
        "queryStringParameters": query_params or None,
        "body": raw_body,
        "isBase64Encoded": False,
        "requestContext": {
            "httpMethod": handler.command,
            "path": resolved_path,
            "identity": {
                "sourceIp": handler.client_address[0],
                "userAgent": _normalize_header_value(handler.headers.get("User-Agent")),
            },
        },
    }


def cors_headers():
    headers = HTTP_CONFIG["HEADERS"].copy()
    headers.setdefault("Access-Control-Allow-Origin", "*")
    headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
    headers.setdefault("Access-Control-Allow-Methods", "OPTIONS,POST")
    return headers


def send_json_response(handler, status_code, payload, headers=None):
    response_headers = cors_headers()
    if headers:
        response_headers.update(headers)

    body = payload
    if isinstance(body, (dict, list)):
        body = json.dumps(body)
    elif body is None:
        body = ""
    elif not isinstance(body, str):
        body = str(body)

    encoded_body = body.encode("utf-8")

    handler.send_response(status_code)
    for key, value in response_headers.items():
        handler.send_header(key, value)
    handler.send_header("Content-Length", str(len(encoded_body)))
    handler.end_headers()
    handler.wfile.write(encoded_body)


class LocalLambdaAdapterHandler(BaseHTTPRequestHandler):
    server_version = "PantryBuddyLocalAdapter/1.0"

    def do_OPTIONS(self):
        send_json_response(self, 204, "", {})

    def do_POST(self):
        parsed_url = urlparse(self.path)
        resolved_path = normalize_supported_path(parsed_url.path)
        if not resolved_path:
            send_json_response(
                self,
                404,
                {"error": f"Unsupported route: {parsed_url.path}"},
            )
            return

        event = build_event(self, resolved_path)

        try:
            lambda_response = lambda_handler(event, context=None)
        except Exception as exc:
            send_json_response(
                self,
                500,
                {"error": "Local adapter failed to invoke lambda_handler", "details": str(exc)},
            )
            return

        status_code = int(lambda_response.get("statusCode", HTTP_CONFIG["DEFAULT_STATUS_CODE"]))
        response_headers = lambda_response.get("headers", {})
        response_body = lambda_response.get("body", "")
        send_json_response(self, status_code, response_body, response_headers)

    def do_GET(self):
        send_json_response(
            self,
            405,
            {"error": "Use POST for meal plan requests."},
        )

    def log_message(self, format, *args):
        return


def run_server(host=DEFAULT_HOST, port=DEFAULT_PORT):
    server = ThreadingHTTPServer((host, port), LocalLambdaAdapterHandler)
    routes = ", ".join(sorted(SUPPORTED_PATHS))
    print(f"Local adapter listening on http://{host}:{port}")
    print(f"Available routes: {routes}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
