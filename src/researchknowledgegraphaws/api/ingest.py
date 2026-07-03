"""Ingestion job API Lambda handlers."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import boto3

from researchknowledgegraphaws.shared.config import get_settings
from researchknowledgegraphaws.shared.http import json_response, parse_json_body


def start_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    settings = get_settings()
    if not settings.state_machine_arn:
        return json_response(500, {"error": "INGESTION_STATE_MACHINE_ARN is not configured"})

    try:
        body = parse_json_body(event)
    except ValueError as exc:
        return json_response(400, {"error": str(exc)})

    source = str(body.get("source", "openalex")).lower()
    if source not in {"openalex", "demo"}:
        return json_response(400, {"error": "source must be either 'openalex' or 'demo'"})

    search = str(body.get("search", "artificial intelligence"))
    limit = int(body.get("limit", 500))
    job_id = str(uuid4())
    payload = {"job_id": job_id, "source": source, "search": search, "limit": limit}

    boto3.client("stepfunctions").start_execution(
        stateMachineArn=settings.state_machine_arn,
        name=f"research-kg-{job_id}",
        input=json.dumps(payload),
    )
    return json_response(202, {"job_id": job_id, "status": "STARTED", "input": payload})


def status_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    settings = get_settings()
    job_id = (event.get("pathParameters") or {}).get("job_id")
    if not job_id:
        return json_response(400, {"error": "job_id path parameter is required"})
    if not settings.job_table_name:
        return json_response(500, {"error": "JOB_TABLE_NAME is not configured"})

    response = boto3.resource("dynamodb").Table(settings.job_table_name).get_item(
        Key={"job_id": job_id}
    )
    item = response.get("Item")
    if not item:
        return json_response(404, {"error": "Job not found", "job_id": job_id})
    return json_response(200, {"job": item})
