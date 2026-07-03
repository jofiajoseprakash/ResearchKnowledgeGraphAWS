"""Small HTTP helpers for Lambda proxy responses."""

from __future__ import annotations

import json
from typing import Any


DEFAULT_HEADERS = {
    "content-type": "application/json",
    "access-control-allow-origin": "*",
}


def json_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": DEFAULT_HEADERS,
        "body": json.dumps(body, default=str),
    }


def parse_json_body(event: dict[str, Any]) -> dict[str, Any]:
    raw_body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raise ValueError("Base64 request bodies are not supported")
    parsed = json.loads(raw_body)
    if not isinstance(parsed, dict):
        raise ValueError("Request body must be a JSON object")
    return parsed
