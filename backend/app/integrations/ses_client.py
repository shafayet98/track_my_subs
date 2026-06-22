"""AWS SES email sender for notification alerts.

Thin wrapper over the SES `send_email` API. boto3 is synchronous, so callers
run `send_email` in a threadpool (see the worker). Credentials come from the
task role / environment — never hardcoded, never logged. Email bodies contain
parsed facts only (merchant, amount, date), never any mailbox content.
"""

from __future__ import annotations

import boto3

from app.core.config import settings


class SesClient:
    """Sends plain + HTML alert emails from the configured SES sender."""

    def __init__(self, sender: str, region: str) -> None:
        self._sender = sender
        self._client = boto3.client("ses", region_name=region)

    @classmethod
    def from_settings(cls) -> SesClient:
        return cls(sender=settings.ses_sender, region=settings.aws_region)

    def send_email(self, *, to: str, subject: str, text_body: str, html_body: str) -> str:
        """Send one email; returns the SES message id."""
        resp = self._client.send_email(
            Source=self._sender,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                },
            },
        )
        return resp["MessageId"]
