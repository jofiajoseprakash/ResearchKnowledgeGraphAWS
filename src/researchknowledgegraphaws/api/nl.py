"""Natural-language → SPARQL via Ollama, then execute via SparqlFunction (Lambda invoke)."""

from __future__ import annotations

import json
import os
import re
from urllib import request as urllib_request

import boto3

from researchknowledgegraphaws.shared.http import json_response

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")
SPARQL_FUNCTION_NAME = os.environ.get("SPARQL_FUNCTION_NAME", "")

PREFIXES = """\
PREFIX kg: <https://example.org/research-kg/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>"""

_PROMPT_TEMPLATE = f"""\
SPARQL generator. Output ONLY the query, no fences, no explanation.
RULE: Never filter by exact string literal (e.g. ?x rdfs:label "foo"). Always use FILTER(CONTAINS(LCASE(?var), "foo")) for label searches.
Prefixes: PREFIX kg: <https://example.org/research-kg/ontology/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
Schema: kg:Work(rdfs:label,kg:publicationYear,kg:cites→Work,kg:authoredBy→Author,kg:hasTopic→Topic) kg:Author(rdfs:label,kg:affiliatedWith→Institution) kg:Topic(rdfs:label) kg:Institution(rdfs:label)

Q: most cited papers?
A: PREFIX kg: <https://example.org/research-kg/ontology/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?title (COUNT(?c) AS ?citations) WHERE {{ ?c kg:cites ?w . ?w rdfs:label ?title }} GROUP BY ?title ORDER BY DESC(?citations) LIMIT 15

Q: top authors by paper count?
A: PREFIX kg: <https://example.org/research-kg/ontology/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?name (COUNT(DISTINCT ?w) AS ?papers) WHERE {{ ?w kg:authoredBy ?a . ?a rdfs:label ?name }} GROUP BY ?name ORDER BY DESC(?papers) LIMIT 15

Q: recent papers?
A: PREFIX kg: <https://example.org/research-kg/ontology/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?title ?year WHERE {{ ?w a kg:Work ; rdfs:label ?title ; kg:publicationYear ?year }} ORDER BY DESC(?year) LIMIT 20

Q: most active institutions?
A: PREFIX kg: <https://example.org/research-kg/ontology/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?inst (COUNT(DISTINCT ?w) AS ?papers) WHERE {{ ?w kg:authoredBy ?a . ?a kg:affiliatedWith ?i . ?i rdfs:label ?inst }} GROUP BY ?inst ORDER BY DESC(?papers) LIMIT 15

Q: papers about deep learning?
A: PREFIX kg: <https://example.org/research-kg/ontology/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?w ?title ?t ?tname WHERE {{ ?w a kg:Work ; rdfs:label ?title ; kg:hasTopic ?t . ?t rdfs:label ?tname . FILTER(CONTAINS(LCASE(?tname), "deep learning")) }} LIMIT 40

Q: {{question}}
A:"""


def _call_ollama(question: str) -> str:
    prompt = _PROMPT_TEMPLATE.replace("{question}", question)
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 350},
    }).encode()
    req = urllib_request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=35) as resp:
        return json.loads(resp.read()).get("response", "").strip()


def _extract_sparql(raw: str) -> str:
    raw = re.sub(r"```(?:sparql)?", "", raw, flags=re.IGNORECASE).strip("` \n")
    if "PREFIX" not in raw.upper():
        raw = PREFIXES + "\n" + raw
    # Fix: kg:hasTopic "literal" → kg:hasTopic ?_t . ?_t rdfs:label ?_lbl . FILTER(CONTAINS(...))
    m2 = re.search(r'kg:hasTopic\s+"([^"]+)"', raw)
    if m2:
        term = m2.group(1).lower()
        raw = (raw[:m2.start()]
               + f'kg:hasTopic ?_ht . ?_ht rdfs:label ?_lbl . FILTER(CONTAINS(LCASE(?_lbl), "{term}"))'
               + raw[m2.end():])
    # Fix: exact rdfs:label string match → CONTAINS filter
    # Handles: ?t rdfs:label "Graph Neural Networks"  (any quote style)
    n = 0
    while True:
        m = re.search(r'(\?\w+\s+rdfs:label\s+)"([^"]+)"', raw)
        if not m:
            break
        n += 1
        var, term = f"?_lv{n}", m.group(2).lower()
        raw = raw[:m.start()] + f'{m.group(1)}{var} . FILTER(CONTAINS(LCASE({var}), "{term}"))' + raw[m.end():]
    # Fix: Work pattern missing kg:hasTopic — model forgets to connect ?w to ?t
    # Detects: "?w a kg:Work ; rdfs:label ?title . ?t rdfs:label ?tname ." with a FILTER(CONTAINS)
    # Injects: "; kg:hasTopic ?t" so the paper is actually linked to the topic
    if "kg:Work" in raw and "kg:hasTopic" not in raw:
        m = re.search(
            r"(a\s+kg:Work\b.*?rdfs:label\s+\?\w+)\s*\.\s*(\?(\w+)\s+rdfs:label)",
            raw, re.DOTALL | re.IGNORECASE,
        )
        if m and re.search(r"FILTER\s*\(\s*CONTAINS\s*\(\s*LCASE", raw, re.IGNORECASE):
            topic_var = m.group(3)
            raw = raw[:m.end(1)] + f" ; kg:hasTopic ?{topic_var}" + raw[m.end(1):]
    # Fix: kg:label → rdfs:label
    raw = re.sub(r"\bkg:label\b", "rdfs:label", raw)
    # Fix: self-referential citation  ?x kg:cites ?x  →  ?citing kg:cites ?x
    raw = re.sub(r"(\?(\w+))\s+kg:cites\s+\1\b", r"?citing kg:cites \1", raw)
    # Fix: LIMIT before ORDER BY — swap them  (SPARQL requires ORDER BY then LIMIT)
    raw = re.sub(
        r"(LIMIT\s+\d+)\s+(ORDER\s+BY\s+\S+(?:\s+\S+)?)",
        r"\2 \1",
        raw,
        flags=re.IGNORECASE,
    )
    # Fix: ORDER BY references a variable not present in SELECT → drop the ORDER BY
    select_match = re.search(r"SELECT\b(.+?)\bWHERE\b", raw, re.DOTALL | re.IGNORECASE)
    orderby_match = re.search(r"ORDER\s+BY\s+(?:ASC|DESC)?\s*\(\?(\w+)\)", raw, re.IGNORECASE)
    if select_match and orderby_match:
        selected_text = select_match.group(1)
        order_var = orderby_match.group(1)
        if f"?{order_var}" not in selected_text and f"AS ?{order_var}" not in selected_text:
            raw = re.sub(r"\s*ORDER\s+BY\s+\S+(?:\s*\(\??\w+\))?", "", raw, flags=re.IGNORECASE)
    # Fix: SELECT ?title but WHERE never binds it — inject label triple
    if "?title" in raw:
        where_body = re.search(r"WHERE\s*\{(.+?)\}", raw, re.DOTALL | re.IGNORECASE)
        if where_body and "?title" not in where_body.group(1):
            raw = re.sub(
                r"(\?\w+\s+(?:a\s+kg:\w+|kg:\w+\s+\?\w+)\s*\.)",
                r"\1 ?w rdfs:label ?title .",
                raw,
                count=1,
            )
    return raw.strip()


def _run_via_sparql_lambda(sparql: str) -> dict:
    client = boto3.client("lambda")
    event_payload = json.dumps({
        "body": json.dumps({"query": sparql}),
        "requestContext": {"authorizer": {"jwt": {"claims": {}}}},
    })
    resp = client.invoke(
        FunctionName=SPARQL_FUNCTION_NAME,
        InvocationType="RequestResponse",
        Payload=event_payload.encode(),
    )
    raw = resp["Payload"].read()

    # Lambda function-level error (timeout, crash) — no "body" key
    if resp.get("FunctionError"):
        err_payload = json.loads(raw)
        msg = err_payload.get("errorMessage", "SPARQL Lambda failed")
        raise RuntimeError(msg)

    outer = json.loads(raw)
    if "body" not in outer:
        raise RuntimeError(f"Unexpected SPARQL Lambda response: {raw[:200]}")

    body = json.loads(outer["body"])
    if "error" in body:
        raise RuntimeError(body.get("detail") or body["error"])
    return body.get("result", {})


def handler(event: dict, context) -> dict:
    try:
        body = json.loads(event.get("body") or "{}")
        question = (body.get("question") or "").strip()
        if not question:
            return json_response(400, {"error": "question is required"})

        print(f"[NL] question: {question!r}")

        raw = _call_ollama(question)
        print(f"[NL] ollama raw: {raw!r}")

        sparql = _extract_sparql(raw)
        print(f"[NL] sparql: {sparql!r}")

        try:
            result = _run_via_sparql_lambda(sparql)
            bindings = result.get("results", {}).get("bindings", [])
            vars_ = result.get("head", {}).get("vars", [])
            print(f"[NL] result vars: {vars_}, rows: {len(bindings)}")
            if bindings:
                print(f"[NL] first row: {bindings[0]}")
            return json_response(200, {"sparql": sparql, "result": result})
        except Exception as sparql_err:
            print(f"[NL] sparql_error: {sparql_err}")
            return json_response(200, {"sparql": sparql, "sparql_error": str(sparql_err)})

    except Exception as exc:
        print(f"[NL] handler error: {exc}")
        return json_response(500, {"error": str(exc)})
