"""AWS CDK stack for the Research Knowledge Graph."""

from __future__ import annotations

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigatewayv2 as apigwv2,
    aws_cognito as cognito,
    aws_cloudwatch as cloudwatch,
    aws_dynamodb as dynamodb,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_neptune as neptune,
    aws_s3 as s3,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
)
from aws_cdk.aws_apigatewayv2_authorizers import HttpUserPoolAuthorizer
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from constructs import Construct


SRC_DIR = Path(__file__).resolve().parents[2]


class ResearchKnowledgeGraphStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        project_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )
        vpc.add_gateway_endpoint("S3Endpoint", service=ec2.GatewayVpcEndpointAwsService.S3)
        vpc.add_gateway_endpoint(
            "DynamoDbEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
        )

        raw_bucket = self._bucket("RawBucket", f"{project_name}-raw")
        processed_bucket = self._bucket("ProcessedBucket", f"{project_name}-processed")
        rdf_bucket = self._bucket("RdfBucket", f"{project_name}-rdf")

        job_table = dynamodb.Table(
            self,
            "IngestionJobsTable",
            partition_key=dynamodb.Attribute(
                name="job_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        lambda_sg = ec2.SecurityGroup(self, "LambdaSecurityGroup", vpc=vpc)
        neptune_sg = ec2.SecurityGroup(self, "NeptuneSecurityGroup", vpc=vpc)
        neptune_sg.add_ingress_rule(
            lambda_sg,
            ec2.Port.tcp(8182),
            "Allow VPC Lambda functions to query Neptune",
        )

        loader_role = iam.Role(
            self,
            "NeptuneLoaderRole",
            assumed_by=iam.ServicePrincipal("rds.amazonaws.com"),
        )
        rdf_bucket.grant_read(loader_role)

        subnet_group = neptune.CfnDBSubnetGroup(
            self,
            "NeptuneSubnetGroup",
            db_subnet_group_description="Private subnets for Research Knowledge Graph Neptune",
            subnet_ids=[subnet.subnet_id for subnet in vpc.isolated_subnets],
        )

        cluster = neptune.CfnDBCluster(
            self,
            "NeptuneCluster",
            db_cluster_identifier=f"{project_name}-neptune",
            db_subnet_group_name=subnet_group.ref,
            iam_auth_enabled=False,
            storage_encrypted=True,
            vpc_security_group_ids=[neptune_sg.security_group_id],
            associated_roles=[
                neptune.CfnDBCluster.DBClusterRoleProperty(role_arn=loader_role.role_arn)
            ],
            serverless_scaling_configuration=neptune.CfnDBCluster.ServerlessScalingConfigurationProperty(
                min_capacity=1,
                max_capacity=4,
            ),
        )

        instance = neptune.CfnDBInstance(
            self,
            "NeptuneServerlessInstance",
            db_cluster_identifier=cluster.ref,
            db_instance_class="db.serverless",
        )
        instance.add_dependency(cluster)

        ollama_role = iam.Role(
            self,
            "OllamaInstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
            ],
        )

        ollama_sg = ec2.SecurityGroup(
            self,
            "OllamaSecurityGroup",
            vpc=vpc,
            description="Ollama EC2 — port 11434 open to Lambda (no fixed egress IP)",
        )
        ollama_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(11434),
            "Ollama API — NL Lambda has no fixed IP so open to internet",
        )

        ollama_userdata = ec2.UserData.for_linux()
        ollama_userdata.add_commands(
            "apt-get update -y",
            "snap install amazon-ssm-agent --classic",
            "systemctl enable snap.amazon-ssm-agent.amazon-ssm-agent.service",
            "systemctl start snap.amazon-ssm-agent.amazon-ssm-agent.service",
            "curl -fsSL https://ollama.com/install.sh | sh",
            "mkdir -p /etc/systemd/system/ollama.service.d",
            "printf '[Service]\\nEnvironment=\"OLLAMA_HOST=0.0.0.0\"\\n' > /etc/systemd/system/ollama.service.d/override.conf",
            "systemctl daemon-reload",
            "systemctl enable ollama",
            "systemctl start ollama",
            "sleep 20",
            "ollama pull qwen2.5:0.5b",
        )

        ollama_instance = ec2.Instance(
            self,
            "OllamaInstance",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
            machine_image=ec2.MachineImage.from_ssm_parameter(
                "/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id",
                os=ec2.OperatingSystemType.LINUX,
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=ollama_sg,
            role=ollama_role,
            user_data=ollama_userdata,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/sda1",
                    volume=ec2.BlockDeviceVolume.ebs(20),
                )
            ],
        )

        base_env = {
            "JOB_TABLE_NAME": job_table.table_name,
            "RAW_BUCKET_NAME": raw_bucket.bucket_name,
            "PROCESSED_BUCKET_NAME": processed_bucket.bucket_name,
            "RDF_BUCKET_NAME": rdf_bucket.bucket_name,
            "NEPTUNE_ENDPOINT": cluster.attr_endpoint,
            "NEPTUNE_PORT": "8182",
            "NEPTUNE_LOADER_ROLE_ARN": loader_role.role_arn,
        }

        health_fn = self._lambda("HealthFunction", "researchknowledgegraphaws.api.health.handler")
        sparql_fn = self._lambda(
            "SparqlFunction",
            "researchknowledgegraphaws.api.sparql.handler",
            environment=base_env,
            timeout=Duration.seconds(60),
            vpc=vpc,
            security_groups=[lambda_sg],
        )
        works_fn = self._lambda(
            "WorksFunction",
            "researchknowledgegraphaws.api.works.handler",
            environment=base_env,
            vpc=vpc,
            security_groups=[lambda_sg],
        )
        citations_fn = self._lambda(
            "CitationsFunction",
            "researchknowledgegraphaws.api.works.citations_handler",
            environment=base_env,
            vpc=vpc,
            security_groups=[lambda_sg],
        )
        authors_fn = self._lambda(
            "AuthorsFunction",
            "researchknowledgegraphaws.api.authors.handler",
            environment=base_env,
            vpc=vpc,
            security_groups=[lambda_sg],
        )
        author_network_fn = self._lambda(
            "AuthorNetworkFunction",
            "researchknowledgegraphaws.api.authors.network_handler",
            environment=base_env,
            vpc=vpc,
            security_groups=[lambda_sg],
        )
        topic_works_fn = self._lambda(
            "TopicWorksFunction",
            "researchknowledgegraphaws.api.topics.works_handler",
            environment=base_env,
            vpc=vpc,
            security_groups=[lambda_sg],
        )

        fetch_fn = self._lambda(
            "FetchOpenAlexFunction",
            "researchknowledgegraphaws.ingestion.pipeline.fetch_openalex_handler",
            environment=base_env,
            timeout=Duration.minutes(5),
        )
        transform_fn = self._lambda(
            "TransformRdfFunction",
            "researchknowledgegraphaws.ingestion.pipeline.transform_rdf_handler",
            environment=base_env,
            timeout=Duration.minutes(5),
        )
        loader_fn = self._lambda(
            "StartNeptuneLoaderFunction",
            "researchknowledgegraphaws.ingestion.pipeline.start_loader_handler",
            environment=base_env,
            timeout=Duration.minutes(2),
            vpc=vpc,
            security_groups=[lambda_sg],
        )

        raw_bucket.grant_write(fetch_fn)
        raw_bucket.grant_read(transform_fn)
        rdf_bucket.grant_write(transform_fn)
        job_table.grant_read_write_data(fetch_fn)
        job_table.grant_read_write_data(transform_fn)
        job_table.grant_read_write_data(loader_fn)
        job_table.grant_read_data(sparql_fn)

        self._lambda(
            "ClearGraphFunction",
            "researchknowledgegraphaws.ingestion.pipeline.clear_graph_handler",
            environment=base_env,
            vpc=vpc,
            security_groups=[lambda_sg],
        )

        state_machine = sfn.StateMachine(
            self,
            "IngestionStateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(
                tasks.LambdaInvoke(
                    self,
                    "Fetch OpenAlex",
                    lambda_function=fetch_fn,
                    payload_response_only=True,
                )
                .next(
                    tasks.LambdaInvoke(
                        self,
                        "Transform RDF",
                        lambda_function=transform_fn,
                        payload_response_only=True,
                    )
                )
                .next(
                    tasks.LambdaInvoke(
                        self,
                        "Start Neptune Loader",
                        lambda_function=loader_fn,
                        payload_response_only=True,
                    )
                )
            ),
            timeout=Duration.minutes(15),
        )

        ingest_start_fn = self._lambda(
            "IngestStartFunction",
            "researchknowledgegraphaws.api.ingest.start_handler",
            environment={**base_env, "INGESTION_STATE_MACHINE_ARN": state_machine.state_machine_arn},
        )
        ingest_status_fn = self._lambda(
            "IngestStatusFunction",
            "researchknowledgegraphaws.api.ingest.status_handler",
            environment=base_env,
        )
        state_machine.grant_start_execution(ingest_start_fn)
        job_table.grant_read_data(ingest_status_fn)

        user_pool = cognito.UserPool(
            self,
            "UserPool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            removal_policy=RemovalPolicy.DESTROY,
        )
        user_pool_client = user_pool.add_client(
            "ApiClient",
            auth_flows=cognito.AuthFlow(user_password=True, user_srp=True),
        )
        authorizer = HttpUserPoolAuthorizer(
            "UserPoolAuthorizer",
            user_pool,
            user_pool_clients=[user_pool_client],
        )

        auth_fn = self._lambda(
            "AuthFunction",
            "researchknowledgegraphaws.api.auth.handler",
            environment={"COGNITO_CLIENT_ID": user_pool_client.user_pool_client_id},
        )
        auth_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cognito-idp:InitiateAuth"],
                resources=[user_pool.user_pool_arn],
            )
        )

        nl_fn = self._lambda(
            "NLQueryFunction",
            "researchknowledgegraphaws.api.nl.handler",
            environment={
                "OLLAMA_URL": f"http://{ollama_instance.instance_public_dns_name}:11434",
                "OLLAMA_MODEL": "qwen2.5:0.5b",
                "SPARQL_FUNCTION_NAME": sparql_fn.function_name,
            },
            timeout=Duration.seconds(90),
        )
        nl_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[sparql_fn.function_arn],
            )
        )

        http_api = apigwv2.HttpApi(
            self,
            "HttpApi",
            api_name=f"{project_name}-api",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_headers=["authorization", "content-type"],
                allow_methods=[
                    apigwv2.CorsHttpMethod.GET,
                    apigwv2.CorsHttpMethod.POST,
                    apigwv2.CorsHttpMethod.OPTIONS,
                ],
                allow_origins=["*"],
            ),
        )
        self._route(http_api, "/health", [apigwv2.HttpMethod.GET], health_fn)
        self._route(http_api, "/auth", [apigwv2.HttpMethod.POST], auth_fn)
        self._route(http_api, "/query/sparql", [apigwv2.HttpMethod.POST], sparql_fn, authorizer)
        self._route(http_api, "/query/nl", [apigwv2.HttpMethod.POST], nl_fn, authorizer)
        self._route(http_api, "/works/{work_id}", [apigwv2.HttpMethod.GET], works_fn, authorizer)
        self._route(
            http_api,
            "/works/{work_id}/citations",
            [apigwv2.HttpMethod.GET],
            citations_fn,
            authorizer,
        )
        self._route(http_api, "/authors/{author_id}", [apigwv2.HttpMethod.GET], authors_fn, authorizer)
        self._route(
            http_api,
            "/authors/{author_id}/network",
            [apigwv2.HttpMethod.GET],
            author_network_fn,
            authorizer,
        )
        self._route(
            http_api,
            "/topics/{topic_id}/works",
            [apigwv2.HttpMethod.GET],
            topic_works_fn,
            authorizer,
        )
        self._route(http_api, "/ingest/jobs", [apigwv2.HttpMethod.POST], ingest_start_fn, authorizer)
        self._route(
            http_api,
            "/ingest/jobs/{job_id}",
            [apigwv2.HttpMethod.GET],
            ingest_status_fn,
            authorizer,
        )

        cloudwatch.Alarm(
            self,
            "IngestionFailedAlarm",
            metric=state_machine.metric_failed(),
            threshold=1,
            evaluation_periods=1,
        )

        CfnOutput(self, "ApiUrl", value=http_api.api_endpoint)
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)
        CfnOutput(self, "NeptuneEndpoint", value=cluster.attr_endpoint)
        CfnOutput(self, "RdfBucketName", value=rdf_bucket.bucket_name)
        CfnOutput(self, "OllamaInstanceId", value=ollama_instance.instance_id)
        CfnOutput(self, "OllamaPublicIp", value=ollama_instance.instance_public_ip)
        CfnOutput(self, "OllamaPublicDns", value=ollama_instance.instance_public_dns_name)

    def _bucket(self, construct_id: str, bucket_name_prefix: str) -> s3.Bucket:
        return s3.Bucket(
            self,
            construct_id,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _lambda(
        self,
        construct_id: str,
        handler: str,
        *,
        environment: dict[str, str] | None = None,
        timeout: Duration = Duration.seconds(30),
        vpc: ec2.IVpc | None = None,
        security_groups: list[ec2.ISecurityGroup] | None = None,
    ) -> lambda_.Function:
        return lambda_.Function(
            self,
            construct_id,
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler=handler,
            code=lambda_.Code.from_asset(str(SRC_DIR)),
            memory_size=512,
            timeout=timeout,
            environment=environment or {},
            vpc=vpc,
            security_groups=security_groups,
        )

    def _route(
        self,
        http_api: apigwv2.HttpApi,
        path: str,
        methods: list[apigwv2.HttpMethod],
        function: lambda_.IFunction,
        authorizer: HttpUserPoolAuthorizer | None = None,
    ) -> None:
        http_api.add_routes(
            path=path,
            methods=methods,
            integration=HttpLambdaIntegration(f"{function.node.id}Integration", function),
            authorizer=authorizer,
        )
