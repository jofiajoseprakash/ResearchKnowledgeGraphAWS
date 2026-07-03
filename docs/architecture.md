# Architecture

The project builds a serverless AWS knowledge graph for scholarly metadata from OpenAlex.

```text
INGESTION PATH
  OpenAlex -> Fetch Lambda -> S3 raw JSON
           -> Transform Lambda -> S3 RDF Turtle
           -> Loader Lambda -> Neptune Serverless
  Orchestrated by Step Functions

STRUCTURED QUERY PATH
  Client -> API Gateway -> Cognito -> SPARQL Lambda (VPC) -> Neptune :8182

NATURAL LANGUAGE QUERY PATH
  Client -> API Gateway -> Cognito -> NL Lambda (outside VPC)
                                       -> Ollama on EC2 (qwen2.5:0.5b)
                                       -> [Lambda invoke]
                                           -> SPARQL Lambda (VPC) -> Neptune :8182
```

## Infrastructure Choice

This project uses AWS CDK, not Terraform. CDK is the single source of truth for infrastructure in v1. Terraform is not required unless the project later needs to integrate with an existing Terraform-managed platform.

## Network Shape

- Neptune runs in private isolated subnets with no internet gateway.
- SPARQL and loader Lambdas run inside the VPC and reach Neptune on port `8182`.
- Fetch, transform, and NL Lambdas run outside the VPC — Fetch needs the OpenAlex API, NL needs the Ollama EC2 public IP.
- The NL Lambda reaches Neptune by invoking the SPARQL Lambda via the AWS SDK (Lambda-to-Lambda). No NAT gateway or VPC peering required.
- S3 and DynamoDB gateway endpoints are configured for private subnet access.

## Data Flow

1. `POST /ingest/jobs` starts a Step Functions workflow.
2. Fetch Lambda calls the OpenAlex API and stores raw JSON in S3.
3. Transform Lambda normalizes the records and writes Turtle RDF to S3.
4. Loader Lambda submits the RDF file to the Neptune bulk loader.
5. SPARQL Lambda queries Neptune with read-only SPARQL.
6. NL Lambda translates plain-English questions to SPARQL via Ollama, then invokes the SPARQL Lambda internally.
