"""Provider-agnostic email types and helpers shared by the email integrations.

The agent only ever needs two operations against a mailbox — narrow to
candidates, then read one email — so both the Gmail-API client
(``gmail.GmailClient``) and the IMAP client (``email_imap.ImapClient``) satisfy
the :class:`EmailReader` protocol below. Keeping the dataclasses and text
normalisation here lets the two clients stay independent while returning
identical shapes to the agent loop and tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from bs4 import BeautifulSoup

# Cap the plaintext we hand the agent — receipts are short; anything longer is
# almost certainly boilerplate/quoted threads.
MAX_BODY_CHARS = 20_000


@dataclass
class EmailCandidate:
    message_id: str
    sender: str
    subject: str
    date: str


@dataclass
class EmailContent:
    message_id: str
    sender: str
    subject: str
    date: str
    body: str


class EmailReader(Protocol):
    """The read-only mailbox surface the agent depends on (Gmail or IMAP)."""

    def search_candidates(self, *, after: datetime | None = None) -> list[EmailCandidate]: ...

    def get_email(self, message_id: str) -> EmailContent: ...


def html_to_text(html: str) -> str:
    """Strip HTML to its visible text (newlines between blocks)."""
    return BeautifulSoup(html, "html.parser").get_text(separator="\n")


def normalize_text(text: str) -> str:
    """Collapse blank lines, trim each line, and length-cap for the agent."""
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return text[:MAX_BODY_CHARS]
