"""GmailClient parsing tests — the Gmail API boundary is faked (no network).

The fake mirrors the googleapiclient builder shape:
``service.users().messages().list(...).execute()`` and ``.get(...).execute()``.
"""

import base64
from datetime import datetime

from app.integrations.gmail import GmailClient


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8")


def _headers(sender: str, subject: str, date: str) -> list[dict]:
    return [
        {"name": "From", "value": sender},
        {"name": "Subject", "value": subject},
        {"name": "Date", "value": date},
    ]


class _Exec:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class _Messages:
    def __init__(self, list_resp, get_map, pages=None):
        self._list_resp = list_resp
        self._get_map = get_map
        self._pages = pages or {}  # pageToken -> list response
        self.list_calls = []

    def list(self, **kwargs):
        self.list_kwargs = kwargs
        self.list_calls.append(kwargs)
        token = kwargs.get("pageToken")
        if token is not None:
            return _Exec(self._pages[token])
        return _Exec(self._list_resp)

    def get(self, *, userId, id, **kwargs):  # noqa: N803 (Gmail API param name)
        return _Exec(self._get_map[id])


class _Users:
    def __init__(self, messages):
        self._messages = messages

    def messages(self):
        return self._messages


class _FakeService:
    def __init__(self, list_resp, get_map, pages=None):
        self._messages = _Messages(list_resp, get_map, pages)

    def users(self):
        return _Users(self._messages)


def test_search_candidates_returns_lightweight_rows():
    list_resp = {"messages": [{"id": "m1"}, {"id": "m2"}]}
    get_map = {
        "m1": {
            "id": "m1",
            "payload": {"headers": _headers("Netflix <info@netflix.com>", "Your receipt", "D1")},
        },
        "m2": {
            "id": "m2",
            "payload": {"headers": _headers("AWS <no-reply@aws.amazon.com>", "Invoice", "D2")},
        },
    }
    client = GmailClient(_FakeService(list_resp, get_map))

    candidates = client.search_candidates()

    assert [c.message_id for c in candidates] == ["m1", "m2"]
    assert candidates[0].sender == "Netflix <info@netflix.com>"
    assert candidates[0].subject == "Your receipt"
    assert candidates[1].date == "D2"
    # Triage must use metadata format — never pull bodies to narrow.
    assert client._service.users().messages().list_kwargs["q"]


def test_search_candidates_paginates_all_pages():
    # Page 1 points at page 2 via nextPageToken; page 2 is the last page.
    list_resp = {"messages": [{"id": "m1"}], "nextPageToken": "p2"}
    pages = {"p2": {"messages": [{"id": "m2"}, {"id": "m3"}]}}
    get_map = {
        mid: {"id": mid, "payload": {"headers": _headers(f"{mid}@x.com", "s", "d")}}
        for mid in ("m1", "m2", "m3")
    }
    client = GmailClient(_FakeService(list_resp, get_map, pages=pages))

    candidates = client.search_candidates()

    # All pages accumulated — no 100-cap, no dropped page.
    assert [c.message_id for c in candidates] == ["m1", "m2", "m3"]
    # It actually followed the nextPageToken into page 2.
    calls = client._service.users().messages().list_calls
    assert calls[0]["pageToken"] is None
    assert calls[1]["pageToken"] == "p2"


def test_search_candidates_empty_inbox():
    client = GmailClient(_FakeService({}, {}))
    assert client.search_candidates() == []


def test_search_candidates_applies_after_date():
    client = GmailClient(_FakeService({}, {}))

    client.search_candidates(after=datetime(2026, 6, 6, 12, 0, 0))

    q = client._service.users().messages().list_kwargs["q"]
    assert "after:2026/06/06" in q


def test_search_candidates_no_date_filter_by_default():
    client = GmailClient(_FakeService({}, {}))

    client.search_candidates()

    q = client._service.users().messages().list_kwargs["q"]
    assert "after:" not in q


def test_get_email_prefers_plaintext():
    msg = {
        "id": "m1",
        "payload": {
            "headers": _headers("Spotify <no-reply@spotify.com>", "Receipt", "D1"),
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64("Paid $9.99 on June 1")}},
                {"mimeType": "text/html", "body": {"data": _b64("<p>ignored</p>")}},
            ],
        },
    }
    client = GmailClient(_FakeService({}, {"m1": msg}))

    email = client.get_email("m1")

    assert email.message_id == "m1"
    assert email.sender == "Spotify <no-reply@spotify.com>"
    assert email.body == "Paid $9.99 on June 1"


def test_get_email_strips_html_when_no_plaintext():
    html = "<html><body><h1>Stan</h1><p>Charged <b>$10</b></p></body></html>"
    msg = {
        "id": "m2",
        "payload": {
            "headers": _headers("Stan <billing@stan.com.au>", "Renewal", "D2"),
            "mimeType": "text/html",
            "body": {"data": _b64(html)},
        },
    }
    client = GmailClient(_FakeService({}, {"m2": msg}))

    email = client.get_email("m2")

    assert "Stan" in email.body
    assert "Charged" in email.body
    assert "<" not in email.body  # tags stripped


def test_get_email_caps_body_length():
    from app.integrations.gmail import MAX_BODY_CHARS

    long_text = "x" * (MAX_BODY_CHARS + 5000)
    msg = {
        "id": "m3",
        "payload": {
            "headers": _headers("a@b.com", "s", "d"),
            "mimeType": "text/plain",
            "body": {"data": _b64(long_text)},
        },
    }
    client = GmailClient(_FakeService({}, {"m3": msg}))

    email = client.get_email("m3")

    assert len(email.body) == MAX_BODY_CHARS
