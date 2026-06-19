"""Gmail OAuth2 + read-only email fetching.

Privacy is binding here (see .claude/rules/security.md):

- Scope is ``gmail.readonly`` **only** — never write/send/delete.
- Candidate search uses Gmail's ``metadata`` format (From/Subject/Date) so we
  never pull bodies just to triage.
- ``get_email`` returns a trimmed plaintext body for the agent to inspect
  **in memory**. Raw bodies are never persisted anywhere; only the message id
  is stored later (for provenance/dedup on payments).

The synchronous Google SDK is wrapped behind small helpers; callers on the
async path should run them via ``run_in_threadpool``.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime

from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.core.config import settings

# Heuristic pre-filter: subscription/billing signals. The LLM does the real
# triage; this just narrows the candidate set so token spend tracks candidates,
# not the whole mailbox.
CANDIDATE_QUERY = (
    "subscription OR receipt OR invoice OR "
    '"payment received" OR "your plan" OR renewal OR '
    '"payment failed" OR "payment due"'
)

# Cap the plaintext we hand the agent — receipts are short; anything longer is
# almost certainly boilerplate/quoted threads.
MAX_BODY_CHARS = 20_000

_TOKEN_URI = "https://oauth2.googleapis.com/token"


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": _TOKEN_URI,
            "redirect_uris": [settings.google_oauth_redirect_uri],
        }
    }


def _flow() -> Flow:
    # Disable PKCE: a new Flow is built for the auth-URL and token-exchange steps,
    # so an auto-generated code_verifier wouldn't survive between them and Google
    # would reject the exchange with invalid_grant. This is a confidential "web"
    # client (it has a client_secret), so PKCE isn't required.
    return Flow.from_client_config(
        _client_config(),
        scopes=[settings.gmail_scope],
        redirect_uri=settings.google_oauth_redirect_uri,
        autogenerate_code_verifier=False,
    )


def build_authorization_url(state: str) -> str:
    """Build Google's consent URL. Pure string-building — no network.

    ``access_type=offline`` + ``prompt=consent`` ensures Google returns a
    refresh token (which we encrypt and store).
    """
    url, _ = _flow().authorization_url(
        state=state,
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    return url


@dataclass
class OAuthResult:
    email_address: str
    refresh_token: str


def exchange_code(code: str) -> OAuthResult:
    """Exchange an authorization code for credentials (network call).

    Returns the connected mailbox address and the long-lived refresh token.
    """
    flow = _flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    profile = service.users().getProfile(userId="me").execute()
    return OAuthResult(email_address=profile["emailAddress"], refresh_token=creds.refresh_token)


def _credentials_from_refresh_token(refresh_token: str) -> Credentials:
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=_TOKEN_URI,
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=[settings.gmail_scope],
    )


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


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _decode_part(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")


def _collect_bodies(payload: dict, plain: list[str], html: list[str]) -> None:
    """Walk the MIME tree, collecting text/plain and text/html bodies."""
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")
    if data:
        if mime == "text/plain":
            plain.append(_decode_part(data))
        elif mime == "text/html":
            html.append(_decode_part(data))
    for part in payload.get("parts", []):
        _collect_bodies(part, plain, html)


def _extract_plaintext(payload: dict) -> str:
    """Prefer text/plain; fall back to HTML stripped to text. Length-capped."""
    plain: list[str] = []
    html: list[str] = []
    _collect_bodies(payload, plain, html)
    if plain:
        text = "\n".join(plain)
    elif html:
        text = BeautifulSoup("\n".join(html), "html.parser").get_text(separator="\n")
    else:
        text = ""
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return text[:MAX_BODY_CHARS]


class GmailClient:
    """Thin read-only wrapper over a Gmail API ``service`` object."""

    def __init__(self, service) -> None:
        self._service = service

    @classmethod
    def from_refresh_token(cls, refresh_token: str) -> GmailClient:
        creds = _credentials_from_refresh_token(refresh_token)
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return cls(service)

    def search_candidates(
        self,
        *,
        after: datetime | None = None,
        max_results: int = 100,
    ) -> list[EmailCandidate]:
        """Heuristic narrowing → lightweight candidates (id/from/subject/date).

        Uses ``format=metadata`` so no body is fetched during triage.
        """
        query = CANDIDATE_QUERY
        if after is not None:
            query = f"{query} after:{after.strftime('%Y/%m/%d')}"

        listing = (
            self._service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        candidates: list[EmailCandidate] = []
        for ref in listing.get("messages", []):
            msg = (
                self._service.users()
                .messages()
                .get(
                    userId="me",
                    id=ref["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                )
                .execute()
            )
            headers = msg.get("payload", {}).get("headers", [])
            candidates.append(
                EmailCandidate(
                    message_id=msg["id"],
                    sender=_header(headers, "From"),
                    subject=_header(headers, "Subject"),
                    date=_header(headers, "Date"),
                )
            )
        return candidates

    def get_email(self, message_id: str) -> EmailContent:
        """Fetch one email's headers + trimmed plaintext body (in-memory use)."""
        msg = (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        return EmailContent(
            message_id=msg["id"],
            sender=_header(headers, "From"),
            subject=_header(headers, "Subject"),
            date=_header(headers, "Date"),
            body=_extract_plaintext(payload),
        )
