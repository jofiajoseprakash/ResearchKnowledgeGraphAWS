# Deployment

## Prerequisites

- AWS credentials configured locally.
- AWS CDK bootstrapped in the target account and region.
- `uv` installed.

## Local Checks

```bash
uv run pytest
uv run python -m researchknowledgegraphaws.infra.app
uv run python diagrams/architecture_diagram.py
```

## Bootstrap CDK

```bash
npx aws-cdk@latest bootstrap aws://ACCOUNT_ID/us-east-1
```

## Deploy

```bash
npx aws-cdk@latest deploy
```

The stack outputs:

- API URL
- Cognito User Pool ID
- Cognito User Pool Client ID
- Neptune endpoint
- RDF S3 bucket name

## Start an Ingestion Job

After creating a Cognito user and obtaining a JWT:

For a complete readable demo dataset:

```bash
curl -X POST "$API_URL/ingest/jobs" \
  -H "authorization: Bearer $JWT" \
  -H "content-type: application/json" \
  -d '{"source":"demo","limit":8}'
```

For live OpenAlex search data:

```bash
curl -X POST "$API_URL/ingest/jobs" \
  -H "authorization: Bearer $JWT" \
  -H "content-type: application/json" \
  -d '{"source":"openalex","search":"artificial intelligence","limit":500}'
```

## Ollama Setup (Natural Language Queries)

The NL query endpoint requires an Ollama server reachable from the NL Lambda.

1. Launch an EC2 instance (t3.medium or larger) in a public subnet.
2. Install and start Ollama:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull qwen2.5:0.5b
```

3. Set the `OLLAMA_URL` environment variable on the NL Lambda to the EC2 public IP:

```text
OLLAMA_URL=http://<ec2-public-ip>:11434
```

The NL Lambda also needs the `SPARQL_FUNCTION_NAME` environment variable set to the SPARQL Lambda's function name — the CDK stack wires this automatically.

## Notes

The v1 stack uses `RemovalPolicy.DESTROY` for learning and iteration. Change this before using the stack for production data.
