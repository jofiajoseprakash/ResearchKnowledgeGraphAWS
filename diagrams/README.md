# Architecture Diagrams

This directory contains the executable diagram script for the Research Knowledge Graph AWS architecture.

## Render

From the project root:

```bash
uv run python diagrams/architecture_diagram.py
```

The script writes these files to the project root:

```text
research_kg_aws.png
research_kg_aws.svg
```

## Requirements

The Python dependency is managed by `uv` through `pyproject.toml`.

The `diagrams` package also requires the Graphviz system executable `dot`. On macOS:

```bash
brew install graphviz
```

## Architecture

The diagram shows:

- API Gateway and Cognito for authenticated API access.
- Lambda query handlers backed by Neptune Serverless.
- Step Functions orchestration for OpenAlex ingestion.
- S3 buckets for raw, processed, and RDF data.
- DynamoDB for ingestion job status.
- CloudWatch for logs, metrics, and alarms.
