# Research Knowledge Graph Architecture Diagram

## File

- `diagrams/architecture.drawio` — editable draw.io source using official AWS Architecture Icons

## How to View

**Option 1: Browser (no install needed)**
1. Go to [https://app.diagrams.net](https://app.diagrams.net)
2. Click "Open Existing Diagram"
3. Pick `diagrams/architecture.drawio`

**Option 2: VS Code extension**
Install the [Draw.io Integration](https://marketplace.visualstudio.com/items?itemName=hediet.vscode-drawio) extension and open the file directly.

**Option 3: draw.io Desktop**
Install from [https://github.com/jgraph/drawio-desktop/releases](https://github.com/jgraph/drawio-desktop/releases) and use **File → Export As → PNG/SVG/PDF** to render an image.

## What the Diagram Shows

The diagram represents the full serverless architecture with three concurrent flows.

### External Entities (left side)
- **Client (Web UI)** — the browser-based frontend
- **OpenAlex API** — the upstream scholarly metadata source

### AWS Cloud (everything inside the outer boundary)

**Public-facing layer**
- **API Gateway (HTTP API v2)** — the single HTTPS entry point
- **Cognito User Pool** — issues and validates JWTs

**Compute (outside VPC, has internet egress)**
- **Auth Lambda** — bridges sign-in to Cognito's `InitiateAuth`
- **NL Lambda** — calls Ollama to generate SPARQL, then invokes the SPARQL Lambda
- **Ingest Start Lambda** — kicks off the ingestion state machine
- **Fetch Lambda** — pages through the OpenAlex API
- **Transform Lambda** — converts raw JSON to RDF Turtle
- **EC2 (Ollama)** — runs `qwen2.5:0.5b` exposed on port 11434

**Orchestration**
- **Step Functions** — three-stage state machine: Fetch → Transform → Load

**VPC (purple boundary, no internet egress)**
- **Loader Lambda** — POSTs to Neptune's `/loader` endpoint
- **SPARQL Lambda** — proxies validated SPARQL queries to Neptune
- **Amazon Neptune Serverless** — RDF triple store, SPARQL endpoint on port 8182

**Data layer**
- **S3 Raw** — raw OpenAlex JSON
- **S3 RDF** — Turtle files ready for Neptune bulk loading
- **DynamoDB** — ingestion job status tracking

**Observability**
- **CloudWatch** — Lambda logs, Step Functions execution metrics, alarms

## The Three Flows

### Flow 1: Authentication
```
Client → API Gateway → Auth Lambda → Cognito (InitiateAuth) → JWT returned
```

### Flow 2: Structured SPARQL Query
```
Client → API Gateway → Cognito (JWT verify) → SPARQL Lambda (in VPC) → Neptune :8182
```

### Flow 3: Natural Language Query
```
Client → API Gateway → Cognito (JWT verify) → NL Lambda (outside VPC)
                                                ├─► EC2 Ollama  (generates SPARQL)
                                                └─► SPARQL Lambda (lambda:Invoke)
                                                          └─► Neptune :8182
```

### Flow 4: Ingestion
```
Client → API Gateway → Ingest Start Lambda → Step Functions
                                                ├─► Fetch Lambda → OpenAlex API → S3 Raw
                                                ├─► Transform Lambda → S3 Raw → S3 RDF
                                                └─► Loader Lambda → Neptune /loader
                                                          Neptune → bulk pull from S3 RDF
                                                Step Functions → DynamoDB (job state)
```

## Key Design Decisions

1. **VPC boundary** — Neptune sits in a private VPC subnet with no internet egress. Only Lambdas attached to the `lambda_sg` security group can reach it on port 8182.
2. **Lambda-to-Lambda bridge** — the NL Lambda cannot be both outside the VPC (for Ollama) and inside (for Neptune). It invokes the SPARQL Lambda via the AWS SDK to cross the boundary without needing a NAT gateway.
3. **S3 gateway endpoint** — bulk loads happen entirely inside the AWS network, no internet traffic.
4. **Bulk loading uses an IAM role with `rds.amazonaws.com` as the principal** — Neptune assumes this role to pull from S3 directly, the Lambda only initiates the load.
5. **Step Functions for ingestion** — every stage produces a replayable S3 artifact, every transition is observable in CloudWatch.
6. **One CDK stack** — all resources, IAM grants and environment wiring live in one Python module.

## Conventions Used

- Solid arrows are primary request paths
- Dashed arrows are async, async data pulls or auxiliary connections (auth checks, logging, bulk pull)
- Icons follow the AWS Architecture Icons standard (`mxgraph.aws4` stencil in draw.io)
- Service colour coding follows AWS Well-Architected guidance: compute orange (`#ED7100`), application integration pink (`#E7157B`), database magenta (`#C925D1`), storage green (`#7AA116`), security red (`#DD344C`), networking purple (`#8C4FFF`)
