# ResearchKnowledgeGraphAWS

AWS-native knowledge graph project for scholarly metadata from OpenAlex.

The project ingests research papers, authors, institutions, journals, topics, and citations from OpenAlex, converts them into RDF/Turtle, bulk loads them into Amazon Neptune Serverless, and exposes graph query APIs through API Gateway and Lambda.

## Architecture

```text
OpenAlex API
  -> Fetch Lambda
  -> S3 raw JSON
  -> Transform Lambda
  -> S3 RDF Turtle
  -> Neptune bulk loader
  -> Neptune Serverless RDF/SPARQL graph
  -> API Gateway + Lambda query APIs
```

Rendered architecture diagrams:

- `research_kg_aws.png`
- `research_kg_aws.svg`

Generate them with:

```bash
uv run python diagrams/architecture_diagram.py
```

## Terraform or CDK?

This project uses **AWS CDK** as the infrastructure-as-code tool. Terraform is not required for v1 because CDK creates the VPC, S3 buckets, DynamoDB table, Neptune cluster, Lambda functions, Step Functions workflow, API Gateway, Cognito, and CloudWatch alarm.

Use one infrastructure owner per resource. Adding Terraform now would duplicate the CDK stack and make deployments harder to reason about.

## Project Layout

```text
src/researchknowledgegraphaws/
  api/          Lambda handlers for health, query, lookup, and ingestion APIs
  ingestion/    OpenAlex fetch, normalization, RDF writer, and loader tasks
  infra/        AWS CDK app and stack
  shared/       Config, HTTP, and SPARQL helpers

diagrams/       Architecture diagram script
docs/           Architecture, schema, deployment, and SPARQL examples
tests/          Unit tests
```

## Local Development

```bash
uv sync
uv run pytest
uv run python diagrams/architecture_diagram.py
```

## Demo UI

The repo includes a static demo UI in `frontend/`.

Open it locally:

```bash
uv run python -m http.server 5174 --bind 127.0.0.1 --directory frontend
```

Then open:

```text
http://127.0.0.1:5174
```

Do not open `frontend/index.html` directly as a `file://` URL. Browsers send `Origin: null` for local files, and API Gateway CORS rejects that origin.

Enter the API URL from CDK output, then sign in with a Cognito user via the sign-in panel.

**Preset queries** — click an example or type a phrase to run a SPARQL template:

```text
Show the citation graph
Show papers and authors
Show papers by topic
Show authors and institutions
What are the top topics?
Show recent papers
```

**Ask AI** — type any plain-English question and click "✦ Ask AI". The NL Lambda translates it to SPARQL via Ollama (`qwen2.5:0.5b`) and executes it against Neptune. The generated SPARQL is shown inline. Results are rendered as a force-directed graph with papers, topics, and authors connected. Clicking a node highlights its neighbours and shows an OpenAlex link.

## CDK

Synthesize the AWS stack:

```bash
uv run python -m researchknowledgegraphaws.infra.app
```

Deploy after configuring AWS credentials and installing the AWS CDK CLI:

```bash
npx aws-cdk@latest bootstrap aws://ACCOUNT_ID/us-east-1
npx aws-cdk@latest deploy
```

## API Surface

- `GET /health`
- `POST /auth`
- `GET /works/{work_id}`
- `GET /works/{work_id}/citations`
- `GET /authors/{author_id}`
- `GET /authors/{author_id}/network`
- `GET /topics/{topic_id}/works`
- `POST /query/sparql`
- `POST /query/nl`
- `POST /ingest/jobs`
- `GET /ingest/jobs/{job_id}`

All routes except `/health` and `/auth` require a Cognito JWT.

## First Demo

For a polished product demo, use the curated complete dataset:

```json
{
  "source": "demo",
  "limit": 8
}
```

This loads a small readable graph where every cited paper has a title, year, authors, topics, institutions, source, and publisher.

For live OpenAlex data, use a bounded search:

```json
{
  "source": "openalex",
  "search": "artificial intelligence",
  "limit": 500
}
```

Then query the graph for papers, authors, institutions, topics, and citation relationships.

## Demo SPARQL Queries

Readable citation graph:

```sparql
PREFIX kg: <https://example.org/research-kg/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

CONSTRUCT {
  ?work kg:cites ?citedWork .
  ?work rdfs:label ?workTitle .
  ?citedWork rdfs:label ?citedTitle .
}
WHERE {
  ?work a kg:Work ;
        rdfs:label ?workTitle ;
        kg:cites ?citedWork .
  ?citedWork rdfs:label ?citedTitle .
}
LIMIT 50
```

Research intelligence summary:

```sparql
PREFIX kg: <https://example.org/research-kg/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?topicName (COUNT(?work) AS ?paperCount)
WHERE {
  ?work kg:hasTopic ?topic .
  ?topic rdfs:label ?topicName .
}
GROUP BY ?topicName
ORDER BY DESC(?paperCount)
```
