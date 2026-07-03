"""Environment-backed settings."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    aws_region: str
    neptune_endpoint: str
    neptune_port: int
    job_table_name: str
    raw_bucket_name: str
    processed_bucket_name: str
    rdf_bucket_name: str
    state_machine_arn: str
    neptune_loader_role_arn: str

    @property
    def neptune_url(self) -> str:
        return f"https://{self.neptune_endpoint}:{self.neptune_port}"


def get_settings() -> Settings:
    return Settings(
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        neptune_endpoint=os.getenv("NEPTUNE_ENDPOINT", "localhost"),
        neptune_port=int(os.getenv("NEPTUNE_PORT", "8182")),
        job_table_name=os.getenv("JOB_TABLE_NAME", ""),
        raw_bucket_name=os.getenv("RAW_BUCKET_NAME", ""),
        processed_bucket_name=os.getenv("PROCESSED_BUCKET_NAME", ""),
        rdf_bucket_name=os.getenv("RDF_BUCKET_NAME", ""),
        state_machine_arn=os.getenv("INGESTION_STATE_MACHINE_ARN", ""),
        neptune_loader_role_arn=os.getenv("NEPTUNE_LOADER_ROLE_ARN", ""),
    )
