"""Health check Lambda."""

from __future__ import annotations

from typing import Any

from researchknowledgegraphaws.shared.http import json_response


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return json_response(200, {"status": "ok", "service": "research-knowledge-graph"})
