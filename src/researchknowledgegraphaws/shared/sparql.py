"""SPARQL query execution helpers for Amazon Neptune."""

from __future__ import annotations

import json
from urllib import parse, request

from researchknowledgegraphaws.shared.config import get_settings


READ_ONLY_PREFIXES = ("select", "ask", "construct", "describe", "prefix", "base")
BLOCKED_KEYWORDS = ("insert", "delete", "load", "clear", "create", "drop", "move", "copy", "add")


def validate_read_only_query(query: str) -> None:
    normalized = " ".join(query.strip().lower().split())
    if not normalized:
        raise ValueError("SPARQL query is required")
    if any(keyword in normalized for keyword in BLOCKED_KEYWORDS):
        raise ValueError("SPARQL update operations are not allowed through this API")
    if not normalized.startswith(READ_ONLY_PREFIXES):
        raise ValueError("Only read-only SPARQL queries are allowed")


def execute_sparql(query: str) -> dict:
    validate_read_only_query(query)
    settings = get_settings()
    data = parse.urlencode({"query": query}).encode("utf-8")
    req = request.Request(
        f"{settings.neptune_url}/sparql",
        data=data,
        headers={
            "accept": "application/sparql-results+json, application/json",
            "content-type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))
