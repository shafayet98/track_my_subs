"""CI/CD stack — GitHub OIDC provider + a scoped deploy role.

GitHub Actions authenticates to AWS via OIDC (no long-lived keys). Trust is
pinned to this repo's `main` branch, so only merges to main can assume the role.
The role can run `cdk deploy` (by assuming the CDK bootstrap roles) plus the
direct steps the workflow does itself: push to ECR, run the migration ECS task,
sync the SPA bucket, and invalidate CloudFront.

Deploy this stack once (IAM is free); it is intentionally NOT redeployed by the
CD pipeline (the pipeline shouldn't rewrite its own permissions).
"""

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

GITHUB_REPO = "shafayet98/track_my_subs"
GITHUB_OIDC_URL = "https://token.actions.githubusercontent.com"
DEPLOY_ROLE_NAME = "github-actions-deploy"


class CicdStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        provider = iam.OpenIdConnectProvider(
            self,
            "GithubOidc",
            url=GITHUB_OIDC_URL,
            client_ids=["sts.amazonaws.com"],
        )

        # Only the main branch of this repo may assume the role.
        principal = iam.OpenIdConnectPrincipal(
            provider,
            conditions={
                "StringEquals": {
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    "token.actions.githubusercontent.com:sub": (
                        f"repo:{GITHUB_REPO}:ref:refs/heads/main"
                    ),
                }
            },
        )

        role = iam.Role(
            self,
            "DeployRole",
            role_name=DEPLOY_ROLE_NAME,
            assumed_by=principal,
            description="Assumed by GitHub Actions (main) to deploy track_my_subs",
        )

        account, region = self.account, self.region

        # cdk deploy works by assuming the CDK bootstrap roles.
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["sts:AssumeRole"],
                resources=[f"arn:aws:iam::{account}:role/cdk-hnb659fds-*"],
            )
        )
        # ECR: auth (account-wide) + push/pull on the API repo.
        role.add_to_policy(
            iam.PolicyStatement(actions=["ecr:GetAuthorizationToken"], resources=["*"])
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:InitiateLayerUpload",
                    "ecr:UploadLayerPart",
                    "ecr:CompleteLayerUpload",
                    "ecr:PutImage",
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                ],
                resources=[f"arn:aws:ecr:{region}:{account}:repository/track-my-subs-api"],
            )
        )
        # ECS: discover the service + run the one-off migration task. The
        # migration runs pre-rollout on the new image, so we register a one-off
        # task-def revision (cloned from the live one, image swapped) — hence
        # RegisterTaskDefinition.
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ecs:ListClusters",
                    "ecs:ListServices",
                    "ecs:DescribeServices",
                    "ecs:DescribeTaskDefinition",
                    "ecs:RegisterTaskDefinition",
                    "ecs:RunTask",
                    "ecs:DescribeTasks",
                ],
                resources=["*"],
            )
        )
        # Let RegisterTaskDefinition / RunTask pass the task + execution roles to ECS.
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=["*"],
                conditions={"StringEquals": {"iam:PassedToService": "ecs-tasks.amazonaws.com"}},
            )
        )
        # SPA upload to the frontend bucket(s).
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket", "s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
                resources=[
                    "arn:aws:s3:::trackmysubs-frontend-*",
                    "arn:aws:s3:::trackmysubs-frontend-*/*",
                ],
            )
        )
        # CloudFront invalidation + reading stack outputs.
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["cloudfront:CreateInvalidation", "cloudfront:GetInvalidation"],
                resources=["*"],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(actions=["cloudformation:DescribeStacks"], resources=["*"])
        )

        CfnOutput(self, "DeployRoleArn", value=role.role_arn)
        CfnOutput(self, "OidcProviderArn", value=provider.open_id_connect_provider_arn)
