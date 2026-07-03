"""Work lookup Lambda handlers."""

from __future__ import annotations

from typing import Any

from researchknowledgegraphaws.shared.http import json_response
from researchknowledgegraphaws.shared.sparql import execute_sparql


PREFIXES = """
PREFIX kg: <https://example.org/research-kg/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    work_id = (event.get("pathParameters") or {}).get("work_id")
    if not work_id:
        return json_response(400, {"error": "work_id path parameter is required"})

    query = f"""
    {PREFIXES}
    SELECT ?work ?title ?year ?source ?topic
    WHERE {{
      ?work kg:hasOpenAlexId "{work_id}" ;
            rdfs:label ?title .
      OPTIONAL {{ ?work kg:publicationYear ?year . }}
      OPTIONAL {{ ?work kg:publishedIn/rdfs:label ?source . }}
      OPTIONAL {{ ?work kg:hasTopic/rdfs:label ?topic . }}
    }}
    LIMIT 100
    """
    try:
        return json_response(200, {"work_id": work_id, "result": execute_sparql(query)})
    except Exception as exc:
        return json_response(502, {"error": "Work lookup failed", "detail": str(exc)})


def citations_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    work_id = (event.get("pathParameters") or {}).get("work_id")
    if not work_id:
        return json_response(400, {"error": "work_id path parameter is required"})

    query = f"""
    {PREFIXES}
    SELECT ?citedWork ?title
    WHERE {{
      ?work kg:hasOpenAlexId "{work_id}" ;
            kg:cites ?citedWork .
      OPTIONAL {{ ?citedWork rdfs:label ?title . }}
    }}
    LIMIT 100
    """
    try:
        return json_response(200, {"work_id": work_id, "result": execute_sparql(query)})
    except Exception as exc:
        return json_response(502, {"error": "Citation lookup failed", "detail": str(exc)})
