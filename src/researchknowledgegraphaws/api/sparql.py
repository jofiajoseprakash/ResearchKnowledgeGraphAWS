"""SPARQL API Lambda."""

from __future__ import annotations

from typing import Any

from researchknowledgegraphaws.shared.http import json_response, parse_json_body
from researchknowledgegraphaws.shared.sparql import execute_sparql


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        body = parse_json_body(event)
        query = str(body.get("query", ""))
        return json_response(200, {"result": execute_sparql(query)})
    except ValueError as exc:
        return json_response(400, {"error": str(exc)})
    except Exception as exc:
        return json_response(502, {"error": "SPARQL query failed", "detail": str(exc)})
