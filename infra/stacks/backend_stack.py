"""Backend stack — ECR + a Fargate API service behind an ALB.

The task pulls its image from ECR (built/pushed separately, so synth/deploy need
no local Docker), reads DB creds + app secrets from Secrets Manager, runs in
private subnets, and is allowed to reach RDS. Scans run in-process in the API
(Phase 4 background tasks). A scheduled Fargate task (EventBridge → RunTask)
runs the daily alert worker from the same image, allowed to send via SES.
"""

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk import aws_route53 as route53
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_ses as ses
from constructs import Construct

from stacks.data_stack import DB_NAME

# Sender for alert emails. A domain identity (DKIM-signed via the hosted zone)
# sends from any address on the domain without per-address verification.
ALERT_SENDER = "alerts@shafcode.xyz"
APP_BASE_URL = "https://shafcode.xyz"

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

        # Image tag to run. CD passes the commit SHA (`-c imageTag=<sha>`) so the
        # task definition changes and ECS rolls onto the new image; defaults to
        # `latest` for manual deploys.
        image_tag = self.node.try_get_context("imageTag") or "latest"

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
                image=ecs.ContainerImage.from_ecr_repository(repository, image_tag),
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

        # --- Alert worker: SES identity + daily scheduled Fargate task --------

        # Verified sender. Public-hosted-zone identity wires DKIM CNAMEs in the
        # zone automatically, so mail from the domain is signed and deliverable.
        ses.EmailIdentity(
            self,
            "AlertSenderIdentity",
            identity=ses.Identity.public_hosted_zone(zone),
        )

        # The worker reuses the API image but overrides the command to run the
        # alert pass once and exit. DB creds come from the same secret; the
        # entrypoint composes DATABASE_URL. SES creds come from the task role.
        worker_task = ecs.FargateTaskDefinition(
            self, "AlertWorkerTask", cpu=256, memory_limit_mib=512
        )
        worker_task.add_container(
            "AlertWorker",
            image=ecs.ContainerImage.from_ecr_repository(repository, image_tag),
            command=["python", "-m", "app.worker.alerts"],
            environment={
                "DB_HOST": database.db_instance_endpoint_address,
                "DB_PORT": database.db_instance_endpoint_port,
                "DB_NAME": DB_NAME,
                "AWS_REGION": self.region,
                "SES_SENDER": ALERT_SENDER,
                "APP_BASE_URL": APP_BASE_URL,
            },
            secrets={
                "DB_USER": ecs.Secret.from_secrets_manager(db_secret, "username"),
                "DB_PASSWORD": ecs.Secret.from_secrets_manager(db_secret, "password"),
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="alert-worker",
                log_retention=logs.RetentionDays.ONE_MONTH,
            ),
        )
        worker_task.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"],
            )
        )

        # Run the worker in the same SG as the API so the existing RDS ingress
        # rule covers it (one-way backend → data dependency stays intact).
        worker_sg = service.service.connections.security_groups[0]
        events.Rule(
            self,
            "DailyAlertSchedule",
            # 14:00 UTC daily — a fixed off-peak hour; lead-time windowing in the
            # worker means the exact minute doesn't matter.
            schedule=events.Schedule.cron(minute="0", hour="14"),
            targets=[
                targets.EcsTask(
                    cluster=cluster,
                    task_definition=worker_task,
                    subnet_selection=ec2.SubnetSelection(
                        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                    ),
                    security_groups=[worker_sg],
                )
            ],
        )

        CfnOutput(self, "EcrRepositoryUri", value=repository.repository_uri)
        CfnOutput(self, "ApiUrl", value=f"https://{API_DOMAIN}")
        CfnOutput(self, "AlbDnsName", value=service.load_balancer.load_balancer_dns_name)
