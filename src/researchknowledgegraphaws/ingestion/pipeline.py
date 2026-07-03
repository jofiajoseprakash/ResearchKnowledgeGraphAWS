"""Lambda tasks used by the Step Functions ingestion workflow."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
from urllib import request

import boto3

from researchknowledgegraphaws.ingestion.demo_dataset import get_demo_works
from researchknowledgegraphaws.ingestion.models import parse_work
from researchknowledgegraphaws.ingestion.openalex_client import fetch_works
from researchknowledgegraphaws.ingestion.rdf_writer import works_to_turtle
from researchknowledgegraphaws.shared.config import get_settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clear_graph_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Drop all triples from Neptune. Invoke directly via AWS CLI — not exposed via API Gateway."""
    settings = get_settings()
    data = b"update=CLEAR+ALL"
    req = request.Request(
        f"{settings.neptune_url}/sparql",
        data=data,
        headers={"content-type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    return {"status": "cleared", "response": body}


def _put_job_status(job_id: str, status: str, **extra: Any) -> None:
    settings = get_settings()
    if not settings.job_table_name:
        return
    item = {"job_id": job_id, "status": status, "updated_at": _now(), **extra}
    boto3.resource("dynamodb").Table(settings.job_table_name).put_item(Item=item)


def fetch_openalex_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    settings = get_settings()
    job_id = event["job_id"]
    source = event.get("source", "openalex")
    search = event.get("search", "artificial intelligence")
    limit = int(event.get("limit", 500))
    _put_job_status(job_id, "FETCHING", source=source, search=search, limit=limit)

    if source == "demo":
        works = get_demo_works(limit=limit)
    elif source == "openalex":
        works = fetch_works(search=search, limit=limit)
    else:
        raise ValueError("source must be either 'openalex' or 'demo'")

    raw_key = f"{source}/{job_id}/works.json"
    boto3.client("s3").put_object(
        Bucket=settings.raw_bucket_name,
        Key=raw_key,
        Body=json.dumps({"works": works}).encode("utf-8"),
        ContentType="application/json",
    )
    _put_job_status(job_id, "FETCHED", source=source, raw_key=raw_key, work_count=len(works))
    return {**event, "raw_key": raw_key, "work_count": len(works)}


def transform_rdf_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    settings = get_settings()
    job_id = event["job_id"]
    _put_job_status(job_id, "TRANSFORMING", raw_key=event["raw_key"])

    s3 = boto3.client("s3")
    raw_object = s3.get_object(Bucket=settings.raw_bucket_name, Key=event["raw_key"])
    raw_payload = json.loads(raw_object["Body"].read().decode("utf-8"))
    works = [parse_work(payload) for payload in raw_payload.get("works") or []]
    turtle = works_to_turtle(works)

    source = event.get("source", "openalex")
    rdf_key = f"{source}/{job_id}/works.ttl"
    s3.put_object(
        Bucket=settings.rdf_bucket_name,
        Key=rdf_key,
        Body=turtle.encode("utf-8"),
        ContentType="text/turtle",
    )
    _put_job_status(job_id, "TRANSFORMED", rdf_key=rdf_key, triple_source_count=len(works))
    return {**event, "rdf_key": rdf_key, "rdf_s3_uri": f"s3://{settings.rdf_bucket_name}/{rdf_key}"}


def start_loader_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    settings = get_settings()
    job_id = event["job_id"]
    _put_job_status(job_id, "LOADING", rdf_key=event["rdf_key"])

    payload = {
        "source": f"s3://{settings.rdf_bucket_name}/{event['rdf_key']}",
        "format": "turtle",
        "iamRoleArn": settings.neptune_loader_role_arn,
        "region": settings.aws_region,
        "failOnError": "TRUE",
        "parallelism": "MEDIUM",
        "updateSingleCardinalityProperties": "FALSE",
        "queueRequest": "TRUE",
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{settings.neptune_url}/loader",
        data=data,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        loader_response = json.loads(response.read().decode("utf-8"))

    _put_job_status(job_id, "LOAD_SUBMITTED", loader_response=loader_response)
    return {**event, "loader_response": loader_response}
