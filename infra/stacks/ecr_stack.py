"""ECR stack — the API image repository.

Kept separate from the backend service stack so the repo's lifecycle is
independent: we deploy this first, push the image, then deploy the Fargate
service. That avoids the chicken-and-egg where the service can't start (no image)
and a rollback would otherwise delete the repo too.
"""

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_ecr as ecr
from constructs import Construct


class EcrStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.repository = ecr.Repository(
            self,
            "ApiRepository",
            repository_name="track-my-subs-api",
            image_scan_on_push=True,
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
        )
