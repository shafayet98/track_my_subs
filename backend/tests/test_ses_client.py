"""SES client against a moto-mocked SES — exercises the real boto3 call path.

Unlike the worker tests (which stub the whole client), this drives boto3's
actual `send_email`, so a wrong parameter shape or response key fails here.
No real AWS, no network, no cost.
"""

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from app.integrations.ses_client import SesClient

REGION = "ap-southeast-2"
SENDER = "alerts@example.com"


@mock_aws
def test_send_email_returns_message_id():
    # Sandbox rule: the sender identity must be verified before sending.
    boto3.client("ses", region_name=REGION).verify_email_identity(EmailAddress=SENDER)

    message_id = SesClient(sender=SENDER, region=REGION).send_email(
        to="user@example.com",
        subject="track_my_subs test",
        text_body="Netflix renews tomorrow.",
        html_body="<p>Netflix renews tomorrow.</p>",
    )

    assert message_id


@mock_aws
def test_send_email_fails_for_unverified_sender():
    # No verify_email_identity → SES rejects, surfacing as a boto ClientError.
    with pytest.raises(ClientError):
        SesClient(sender="unverified@example.com", region=REGION).send_email(
            to="user@example.com",
            subject="s",
            text_body="t",
            html_body="<p>t</p>",
        )
