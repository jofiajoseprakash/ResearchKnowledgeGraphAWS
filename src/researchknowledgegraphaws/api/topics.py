"""Topic lookup Lambda handlers."""

from __future__ import annotations

from typing import Any

from researchknowledgegraphaws.shared.http import json_response
from researchknowledgegraphaws.shared.sparql import execute_sparql


PREFIXES = """
PREFIX kg: <https://example.org/research-kg/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""


def works_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    topic_id = (event.get("pathParameters") or {}).get("topic_id")
    if not topic_id:
        return json_response(400, {"error": "topic_id path parameter is required"})

    query = f"""
    {PREFIXES}
    SELECT ?work ?title ?year
    WHERE {{
      ?topic kg:hasOpenAlexId "{topic_id}" .
      ?work kg:hasTopic ?topic ;
            rdfs:label ?title .
      OPTIONAL {{ ?work kg:publicationYear ?year . }}
    }}
    ORDER BY DESC(?year)
    LIMIT 100
    """
    try:
        return json_response(200, {"topic_id": topic_id, "result": execute_sparql(query)})
    except Exception as exc:
        return json_response(502, {"error": "Topic lookup failed", "detail": str(exc)})
