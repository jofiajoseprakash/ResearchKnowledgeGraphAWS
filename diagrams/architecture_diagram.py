"""Render the AWS architecture diagram for the Research Knowledge Graph project."""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb, Neptune
from diagrams.aws.integration import StepFunctions
from diagrams.aws.management import Cloudwatch
from diagrams.aws.network import APIGateway, PrivateSubnet, VPC
from diagrams.aws.security import Cognito
from diagrams.aws.storage import S3
from diagrams.onprem.client import Users
from diagrams.programming.flowchart import Database


GRAPH_ATTR = {
    "fontsize": "24",
    "bgcolor": "white",
    "pad": "0.4",
    "splines": "ortho",
    "nodesep": "0.7",
    "ranksep": "1.0",
}

NODE_ATTR = {
    "fontsize": "12",
}

EDGE_ATTR = {
    "fontsize": "10",
}

REGION_ATTR = {
    "bgcolor": "#fff7fb",
    "color": "#ff2d8f",
    "fontcolor": "#111111",
    "fontsize": "18",
    "penwidth": "2.0",
    "style": "rounded",
}

SECTION_ATTR = {
    "bgcolor": "#ffffff",
    "color": "#b9c0ca",
    "fontcolor": "#333333",
    "fontsize": "14",
    "penwidth": "1.2",
    "style": "rounded,dashed",
}

VPC_ATTR = {
    "bgcolor": "#f7fbff",
    "color": "#7d3cff",
    "fontcolor": "#333333",
    "fontsize": "14",
    "penwidth": "1.4",
    "style": "rounded",
}

SUBNET_ATTR = {
    "bgcolor": "#f4fffb",
    "color": "#00a88f",
    "fontcolor": "#333333",
    "fontsize": "13",
    "penwidth": "1.2",
    "style": "rounded",
}


def build_diagram() -> None:
    """Generate PNG and SVG architecture diagrams in the project root."""
    with Diagram(
        "Research Knowledge Graph on AWS",
        filename="research_kg_aws",
        outformat=["png", "svg"],
        show=False,
        direction="LR",
        graph_attr=GRAPH_ATTR,
        node_attr=NODE_ATTR,
        edge_attr=EDGE_ATTR,
    ):
        user = Users("User / Admin")
        openalex = Database("OpenAlex API\nWorks, Authors,\nInstitutions, Topics")

        with Cluster(
            "AWS Account: Research Knowledge Graph\nAWS Region: us-east-1",
            graph_attr=REGION_ATTR,
        ):
            with Cluster("Edge and Identity", graph_attr=SECTION_ATTR):
                api = APIGateway("API Gateway")
                auth = Cognito("Cognito\nJWT Auth")

            with Cluster("Application VPC", graph_attr=VPC_ATTR):
                vpc = VPC("VPC")
                with Cluster("Private Subnets", graph_attr=SUBNET_ATTR):
                    private_subnet = PrivateSubnet("Private\nSubnets")
                    query_api = Lambda("Query API\nLambdas")
                    ingest_api = Lambda("Ingestion Starter\nLambda")
                    graph = Neptune("Neptune Serverless\nRDF / SPARQL")

            with Cluster("Ingestion Workflow", graph_attr=SECTION_ATTR):
                workflow = StepFunctions("Step Functions")
                fetch = Lambda("Fetch\nOpenAlex Data")
                transform = Lambda("Normalize +\nGenerate RDF")
                loader = Lambda("Start Neptune\nBulk Loader")

            with Cluster("Data Lake Buckets", graph_attr=SECTION_ATTR):
                raw = S3("S3 Raw Data\nOpenAlex JSON")
                processed = S3("S3 Processed Data\nNormalized JSON")
                rdf = S3("S3 RDF Files\nTurtle")

            with Cluster("Operations", graph_attr=SECTION_ATTR):
                jobs = Dynamodb("DynamoDB\nJob Status")
                logs = Cloudwatch("CloudWatch\nLogs / Metrics / Alarms")

        user >> api
        api >> auth
        api >> query_api
        api >> ingest_api

        vpc >> private_subnet
        query_api >> Edge(label="SPARQL queries") >> graph
        query_api >> Edge(label="job reads") >> jobs

        ingest_api >> Edge(label="start job") >> workflow
        workflow >> fetch >> Edge(label="fetch metadata") >> openalex
        fetch >> Edge(label="store raw payloads") >> raw

        workflow >> transform
        raw >> transform
        transform >> processed
        transform >> rdf

        workflow >> loader
        rdf >> loader
        loader >> Edge(label="bulk load RDF") >> graph

        workflow >> Edge(label="status updates") >> jobs

        api >> logs
        query_api >> logs
        ingest_api >> logs
        workflow >> logs
        fetch >> logs
        transform >> logs
        loader >> logs


if __name__ == "__main__":
    build_diagram()
