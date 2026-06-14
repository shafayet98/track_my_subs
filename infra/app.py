#!/usr/bin/env python3
"""CDK app entry point for track_my_subs.

Deploys into the audrie98 account (390843337949), ap-southeast-2. See
docs/plans/AWS_deployment.md and the `aws-deploy-account` memory.
"""

import aws_cdk as cdk

from stacks.backend_stack import BackendStack
from stacks.data_stack import DataStack
from stacks.frontend_stack import FrontendStack
from stacks.network_stack import NetworkStack

# Pinned target so synth is deterministic and needs no environment lookups.
ENV = cdk.Environment(account="390843337949", region="ap-southeast-2")
PREFIX = "TrackMySubs"

app = cdk.App()

network = NetworkStack(app, f"{PREFIX}-Network", env=ENV)

data = DataStack(
    app,
    f"{PREFIX}-Data",
    vpc=network.vpc,
    env=ENV,
)

BackendStack(
    app,
    f"{PREFIX}-Backend",
    vpc=network.vpc,
    database=data.database,
    db_secret=data.db_secret,
    app_secret=data.app_secret,
    env=ENV,
)

FrontendStack(app, f"{PREFIX}-Frontend", env=ENV)

app.synth()
