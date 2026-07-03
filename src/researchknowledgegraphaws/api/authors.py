"""Author lookup Lambda handlers."""

from __future__ import annotations

from typing import Any

from researchknowledgegraphaws.shared.http import json_response
from researchknowledgegraphaws.shared.sparql import execute_sparql


PREFIXES = """
PREFIX kg: <https://example.org/research-kg/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    author_id = (event.get("pathParameters") or {}).get("author_id")
    if not author_id:
        return json_response(400, {"error": "author_id path parameter is required"})

    query = f"""
    {PREFIXES}
    SELECT ?author ?name ?institution ?work ?title
    WHERE {{
      ?author kg:hasOpenAlexId "{author_id}" ;
              rdfs:label ?name .
      OPTIONAL {{ ?author kg:affiliatedWith/rdfs:label ?institution . }}
      OPTIONAL {{
        ?work kg:authoredBy ?author ;
              rdfs:label ?title .
      }}
    }}
    LIMIT 100
    """
    try:
        return json_response(200, {"author_id": author_id, "result": execute_sparql(query)})
    except Exception as exc:
        return json_response(502, {"error": "Author lookup failed", "detail": str(exc)})


def network_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    author_id = (event.get("pathParameters") or {}).get("author_id")
    if not author_id:
        return json_response(400, {"error": "author_id path parameter is required"})

    query = f"""
    {PREFIXES}
    SELECT DISTINCT ?coauthor ?coauthorName ?work ?title
    WHERE {{
      ?author kg:hasOpenAlexId "{author_id}" .
      ?work kg:authoredBy ?author ;
            kg:authoredBy ?coauthor ;
            rdfs:label ?title .
      ?coauthor rdfs:label ?coauthorName .
      FILTER (?coauthor != ?author)
    }}
    LIMIT 100
    """
    try:
        return json_response(200, {"author_id": author_id, "result": execute_sparql(query)})
    except Exception as exc:
        return json_response(502, {"error": "Author network lookup failed", "detail": str(exc)})
