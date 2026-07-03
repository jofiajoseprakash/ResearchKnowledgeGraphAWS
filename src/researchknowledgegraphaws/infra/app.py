"""CDK app entrypoint."""

from __future__ import annotations

import os
from pathlib import Path

import aws_cdk as cdk

from researchknowledgegraphaws.infra.stack import ResearchKnowledgeGraphStack


def main() -> None:
    project_root = Path(__file__).resolve().parents[3]
    app = cdk.App(outdir=str(project_root / "cdk.out"))
    project_name = app.node.try_get_context("projectName") or "research-kg"
    default_region = app.node.try_get_context("defaultRegion") or "us-east-1"
    env = cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION", default_region),
    )
    ResearchKnowledgeGraphStack(
        app,
        "ResearchKnowledgeGraphStack",
        project_name=project_name,
        env=env,
    )
    app.synth()


if __name__ == "__main__":
    main()
