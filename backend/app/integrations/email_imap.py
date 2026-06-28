"""IMAP + App Password read-only email fetching.

An alternative to the Gmail-API/OAuth path that avoids Google's restricted-scope
verification entirely: the user generates a 16-char App Password and we read mail
over ``imap.gmail.com`` (or any IMAP host) directly. See
``docs/local-app-email-access.md`` and ``.claude/rules/security.md`` for the
deliberate credential trade-off (an app password is a full-mailbox credential;
we only ever read).

Read-only is enforced two ways: the mailbox is opened with ``readonly=True``
(IMAP ``EXAMINE``) and bodies are fetched with ``BODY.PEEK`` — neither sets the
``\\Seen`` flag, so scanning never mutates the mailbox. Like the Gmail client,
triage pulls headers only; raw bodies are read in-memory and never persisted.

The blocking ``imaplib`` calls are wrapped in small synchronous methods; async
callers run them via ``run_in_threadpool``.
"""

from __future__ import annotations

import email
import imaplib
from datetime import datetime
from email.header import decode_header, make_header
from email.message import Message

from app.integrations.email_common import (
    EmailCandidate,
    EmailContent,
    html_to_text,
    normalize_text,
)
from app.integrations.gmail import CANDIDATE_QUERY

# Gmail hosts support the X-GM-RAW search extension, which accepts the exact
# Gmail query syntax we already tuned for the OAuth path. Other providers fall
# back to a per-keyword SUBJECT search (no shared cross-provider raw syntax).
_GMAIL_HOSTS = {"imap.gmail.com", "imap.googlemail.com"}
_GENERIC_SUBJECT_TERMS = (
    "subscription",
    "receipt",
    "invoice",
    "payment",
    "renewal",
    "plan",
)


def _imap_quote(value: str) -> str:
    """Wrap a value as an IMAP quoted-string (escaping ``\\`` and ``"``)."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


class ImapClient:
    """Thin read-only wrapper over an IMAP mailbox."""

    def __init__(self, host: str, email_address: str, app_password: str) -> None:
        self._host = host
        self._email_address = email_address
        self._app_password = app_password

    @classmethod
    def from_credentials(cls, host: str, email_address: str, app_password: str) -> ImapClient:
        return cls(host, email_address, app_password)

    def _connect(self) -> imaplib.IMAP4_SSL:
        conn = imaplib.IMAP4_SSL(self._host)
        conn.login(self._email_address, self._app_password)
        # readonly=True opens the mailbox with EXAMINE — reads never set \Seen.
        conn.select("INBOX", readonly=True)
        return conn

    def check_login(self) -> None:
        """Open and close a connection to validate credentials (raises on fail)."""
        conn = self._connect()
        conn.logout()

    def _search_uids(self, conn: imaplib.IMAP4_SSL, *, after: datetime | None) -> list[bytes]:
        if self._host in _GMAIL_HOSTS:
            query = CANDIDATE_QUERY
            if after is not None:
                query = f"{query} after:{after.strftime('%Y/%m/%d')}"
            _typ, data = conn.uid("SEARCH", None, "X-GM-RAW", _imap_quote(query))
            return data[0].split() if data and data[0] else []

        # Generic IMAP: union per-keyword SUBJECT searches (no raw query syntax).
        since = ["SINCE", after.strftime("%d-%b-%Y")] if after is not None else []
        seen: set[bytes] = set()
        ordered: list[bytes] = []
        for term in _GENERIC_SUBJECT_TERMS:
            _typ, data = conn.uid("SEARCH", None, *since, "SUBJECT", term)
            if not data or not data[0]:
                continue
            for uid in data[0].split():
                if uid not in seen:
                    seen.add(uid)
                    ordered.append(uid)
        return ordered

    def search_candidates(self, *, after: datetime | None = None) -> list[EmailCandidate]:
        """Narrow the mailbox to lightweight candidates (id/from/subject/date).

        Fetches header fields only via ``BODY.PEEK`` — no bodies during triage.
        ``message_id`` is the IMAP UID (stable within this mailbox).
        """
        conn = self._connect()
        try:
            candidates: list[EmailCandidate] = []
            for uid in self._search_uids(conn, after=after):
                _typ, data = conn.uid(
                    "FETCH",
                    uid,
                    "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])",
                )
                header_bytes = b""
                for item in data:
                    if isinstance(item, tuple) and len(item) == 2:
                        header_bytes = item[1]
                        break
                headers = email.message_from_bytes(header_bytes)
                candidates.append(
                    EmailCandidate(
                        message_id=uid.decode(),
                        sender=_decode_header(headers.get("From")),
                        subject=_decode_header(headers.get("Subject")),
                        date=_decode_header(headers.get("Date")),
                    )
                )
            return candidates
        finally:
            conn.logout()

    def get_email(self, message_id: str) -> EmailContent:
        """Fetch one email's headers + trimmed plaintext body (in-memory use)."""
        conn = self._connect()
        try:
            _typ, data = conn.uid("FETCH", message_id, "(BODY.PEEK[])")
            raw = b""
            for item in data:
                if isinstance(item, tuple) and len(item) == 2:
                    raw = item[1]
                    break
            msg = email.message_from_bytes(raw)
            return EmailContent(
                message_id=message_id,
                sender=_decode_header(msg.get("From")),
                subject=_decode_header(msg.get("Subject")),
                date=_decode_header(msg.get("Date")),
                body=_extract_body(msg),
            )
        finally:
            conn.logout()


def _extract_body(msg: Message) -> str:
    """Prefer text/plain; fall back to HTML stripped to text. Length-capped."""
    plain: list[str] = []
    html: list[str] = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        disposition = str(part.get("Content-Disposition") or "")
        if "attachment" in disposition.lower():
            continue
        content_type = part.get_content_type()
        if content_type not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        charset = part.get_content_charset() or "utf-8"
        try:
            decoded = payload.decode(charset, errors="replace")
        except LookupError:
            decoded = payload.decode("utf-8", errors="replace")
        (plain if content_type == "text/plain" else html).append(decoded)

    if plain:
        text = "\n".join(plain)
    elif html:
        text = html_to_text("\n".join(html))
    else:
        text = ""
    return normalize_text(text)
