"""Backend stack — ECR + a Fargate API service behind an ALB.

The task pulls its image from ECR (built/pushed separately, so synth/deploy need
no local Docker), reads DB creds + app secrets from Secrets Manager, runs in
private subnets, and is allowed to reach RDS. Scans run in-process in the API
(Phase 4 background tasks); a dedicated worker service is a later change.
"""

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_rds as rds
from aws_cdk import aws_route53 as route53
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from stacks.data_stack import DB_NAME

IMAGE_TAG = "latest"

# Custom domain for the API (audrie98). The hosted zone for shafcode.xyz lives in
# this account; the ACM cert is validated via DNS in that zone. Referenced by
# id/arn (no lookups) so `cdk synth` stays offline for CI.
API_DOMAIN = "api.shafcode.xyz"
HOSTED_ZONE_ID = "Z0858754AS09Y4TNXSF5"
HOSTED_ZONE_NAME = "shafcode.xyz"
API_CERTIFICATE_ARN = (
    "arn:aws:acm:ap-southeast-2:390843337949:certificate/69731ecd-68f6-4de1-a978-1a3745209036"
)


class BackendStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc,
        repository: ecr.IRepository,
        database: rds.DatabaseInstance,
        db_secret: secretsmanager.ISecret,
        app_secret: secretsmanager.ISecret,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)

        zone = route53.HostedZone.from_hosted_zone_attributes(
            self,
            "Zone",
            hosted_zone_id=HOSTED_ZONE_ID,
            zone_name=HOSTED_ZONE_NAME,
        )
        certificate = acm.Certificate.from_certificate_arn(
            self, "ApiCertificate", API_CERTIFICATE_ARN
        )

        # DB connection: host/port/name as env, user/password from the RDS secret.
        # The container entrypoint composes DATABASE_URL from these. The OAuth
        # redirect URI is fixed now that the API domain is known (not a secret).
        environment = {
            "DB_HOST": database.db_instance_endpoint_address,
            "DB_PORT": database.db_instance_endpoint_port,
            "DB_NAME": DB_NAME,
            "GOOGLE_OAUTH_REDIRECT_URI": f"https://{API_DOMAIN}/api/accounts/gmail/callback",
        }
        secrets = {
            "DB_USER": ecs.Secret.from_secrets_manager(db_secret, "username"),
            "DB_PASSWORD": ecs.Secret.from_secrets_manager(db_secret, "password"),
            "ANTHROPIC_API_KEY": ecs.Secret.from_secrets_manager(app_secret, "ANTHROPIC_API_KEY"),
            "JWT_SECRET": ecs.Secret.from_secrets_manager(app_secret, "JWT_SECRET"),
            "TOKEN_ENCRYPTION_KEY": ecs.Secret.from_secrets_manager(
                app_secret, "TOKEN_ENCRYPTION_KEY"
            ),
            "GOOGLE_OAUTH_CLIENT_ID": ecs.Secret.from_secrets_manager(
                app_secret, "GOOGLE_OAUTH_CLIENT_ID"
            ),
            "GOOGLE_OAUTH_CLIENT_SECRET": ecs.Secret.from_secrets_manager(
                app_secret, "GOOGLE_OAUTH_CLIENT_SECRET"
            ),
            "FRONTEND_ORIGIN": ecs.Secret.from_secrets_manager(app_secret, "FRONTEND_ORIGIN"),
        }

        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "ApiService",
            cluster=cluster,
            cpu=512,
            memory_limit_mib=1024,
            desired_count=1,
            min_healthy_percent=100,
            max_healthy_percent=200,
            public_load_balancer=True,
            # HTTPS at api.shafcode.xyz; HTTP is redirected to HTTPS. The pattern
            # also creates the A-alias record in the hosted zone.
            protocol=elbv2.ApplicationProtocol.HTTPS,
            certificate=certificate,
            domain_name=API_DOMAIN,
            domain_zone=zone,
            redirect_http=True,
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(repository, IMAGE_TAG),
                container_port=8000,
                environment=environment,
                secrets=secrets,
                log_driver=ecs.LogDrivers.aws_logs(stream_prefix="api"),
            ),
        )

        service.target_group.configure_health_check(
            path="/api/health",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
        )

        # Open Postgres to the API task SG. Declaring the ingress rule here (in the
        # backend stack) keeps the cross-stack dependency one-way: backend → data.
        ec2.CfnSecurityGroupIngress(
            self,
            "DbIngressFromApi",
            group_id=database.connections.security_groups[0].security_group_id,
            source_security_group_id=service.service.connections.security_groups[
                0
            ].security_group_id,
            ip_protocol="tcp",
            from_port=5432,
            to_port=5432,
            description="API tasks to Postgres",
        )

        CfnOutput(self, "EcrRepositoryUri", value=repository.repository_uri)
        CfnOutput(self, "ApiUrl", value=f"https://{API_DOMAIN}")
        CfnOutput(self, "AlbDnsName", value=service.load_balancer.load_balancer_dns_name)
