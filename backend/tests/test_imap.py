"""ImapClient tests — the imaplib boundary is faked (no network).

The fake mirrors the ``imaplib.IMAP4_SSL`` surface the client uses:
``login``, ``select``, ``uid("SEARCH"/"FETCH", ...)``, and ``logout``. It records
calls so we can assert read-only behaviour (EXAMINE + BODY.PEEK, never \\Seen).
"""

from datetime import datetime

import pytest

from app.integrations.email_common import MAX_BODY_CHARS
from app.integrations.email_imap import ImapClient


def _header_blob(sender: str, subject: str, date: str) -> bytes:
    return f"From: {sender}\r\nSubject: {subject}\r\nDate: {date}\r\n\r\n".encode()


class FakeIMAP:
    """Records calls; returns canned SEARCH/FETCH responses keyed by UID."""

    def __init__(self, *, search_uids, headers=None, bodies=None, fail_login=False):
        self._search_uids = search_uids  # list[bytes] OR dict[term -> list[bytes]]
        self._headers = headers or {}  # uid(str) -> header bytes
        self._bodies = bodies or {}  # uid(str) -> full rfc822 bytes
        self._fail_login = fail_login
        self.calls: list[tuple] = []
        self.select_kwargs: dict = {}
        self.logged_out = False

    def login(self, user, password):
        self.calls.append(("login", user, password))
        if self._fail_login:
            import imaplib

            raise imaplib.IMAP4.error("authentication failed")
        return ("OK", [b"logged in"])

    def select(self, mailbox, readonly=False):
        self.select_kwargs = {"mailbox": mailbox, "readonly": readonly}
        return ("OK", [b"1"])

    def uid(self, command, *args):
        self.calls.append(("uid", command, *args))
        if command == "SEARCH":
            # Gmail path: ("SEARCH", None, "X-GM-RAW", "...") -> flat list.
            # Generic path: ("SEARCH", None, [SINCE x], "SUBJECT", term) -> per term.
            if isinstance(self._search_uids, dict):
                term = args[-1]
                uids = self._search_uids.get(term, [])
            else:
                uids = self._search_uids
            return ("OK", [b" ".join(uids)] if uids else [b""])
        if command == "FETCH":
            uid = args[0]
            uid_str = uid.decode() if isinstance(uid, bytes) else uid
            spec = args[1]
            if "HEADER" in spec:
                blob = self._headers[uid_str]
            else:
                blob = self._bodies[uid_str]
            return ("OK", [(b"meta", blob), b")"])
        raise AssertionError(f"unexpected uid command {command}")

    def logout(self):
        self.logged_out = True
        return ("BYE", [b"bye"])


def _client(fake: FakeIMAP, host: str = "imap.gmail.com") -> ImapClient:
    client = ImapClient.from_credentials(host, "me@gmail.com", "app-pass")
    client._connect = lambda: (
        fake.login("me@gmail.com", "app-pass"),
        fake.select("INBOX", readonly=True),
        fake,
    )[-1]  # noqa: E501
    return client


def test_search_candidates_gmail_uses_xgmraw_and_peek_headers():
    fake = FakeIMAP(
        search_uids=[b"11", b"12"],
        headers={
            "11": _header_blob("Netflix <info@netflix.com>", "Your receipt", "D1"),
            "12": _header_blob("AWS <no-reply@aws.amazon.com>", "Invoice", "D2"),
        },
    )
    client = _client(fake)

    candidates = client.search_candidates()

    assert [c.message_id for c in candidates] == ["11", "12"]
    assert candidates[0].sender == "Netflix <info@netflix.com>"
    assert candidates[0].subject == "Your receipt"
    assert candidates[1].date == "D2"
    # Read-only: opened with EXAMINE and headers fetched with BODY.PEEK.
    assert fake.select_kwargs["readonly"] is True
    search = next(c for c in fake.calls if c[1] == "SEARCH")
    assert "X-GM-RAW" in search
    fetch = next(c for c in fake.calls if c[1] == "FETCH")
    assert "BODY.PEEK" in fetch[3]
    assert "\\Seen" not in str(fake.calls)
    assert fake.logged_out is True


def test_search_candidates_gmail_applies_after_date():
    fake = FakeIMAP(search_uids=[])
    client = _client(fake)

    client.search_candidates(after=datetime(2026, 6, 6))

    search = next(c for c in fake.calls if c[1] == "SEARCH")
    # X-GM-RAW carries the gmail-style after: filter in the raw query arg.
    assert any("after:2026/06/06" in str(a) for a in search)


def test_search_candidates_generic_host_applies_since_date():
    fake = FakeIMAP(search_uids={})
    client = _client(fake, host="imap.fastmail.com")

    client.search_candidates(after=datetime(2026, 6, 6))

    # Generic host uses an IMAP SINCE criterion (dd-Mon-yyyy), not X-GM-RAW.
    searches = [c for c in fake.calls if c[1] == "SEARCH"]
    assert searches
    for search in searches:
        assert "SINCE" in search
        assert "06-Jun-2026" in search
        assert "X-GM-RAW" not in search


def test_search_candidates_generic_host_unions_subject_terms():
    fake = FakeIMAP(
        search_uids={"receipt": [b"5"], "invoice": [b"5", b"6"], "payment": [b"7"]},
        headers={
            "5": _header_blob("a@x.com", "receipt", "d"),
            "6": _header_blob("b@x.com", "invoice", "d"),
            "7": _header_blob("c@x.com", "payment", "d"),
        },
    )
    client = _client(fake, host="imap.fastmail.com")

    candidates = client.search_candidates()

    # Deduped union, first-seen order preserved.
    assert [c.message_id for c in candidates] == ["5", "6", "7"]
    # Generic host must NOT use the Gmail-only X-GM-RAW extension.
    assert not any("X-GM-RAW" in c for c in fake.calls if c[1] == "SEARCH")


def test_get_email_prefers_plaintext():
    body = (
        b"From: Spotify <no-reply@spotify.com>\r\n"
        b"Subject: Receipt\r\nDate: D1\r\n"
        b'Content-Type: multipart/alternative; boundary="b"\r\n\r\n'
        b"--b\r\nContent-Type: text/plain\r\n\r\nPaid $9.99 on June 1\r\n"
        b"--b\r\nContent-Type: text/html\r\n\r\n<p>ignored</p>\r\n--b--\r\n"
    )
    fake = FakeIMAP(search_uids=[], bodies={"1": body})
    client = _client(fake)

    email = client.get_email("1")

    assert email.sender == "Spotify <no-reply@spotify.com>"
    assert email.body == "Paid $9.99 on June 1"
    # Read with BODY.PEEK — never marks the message read.
    fetch = next(c for c in fake.calls if c[1] == "FETCH")
    assert "BODY.PEEK" in fetch[3]


def test_get_email_strips_html_when_no_plaintext():
    html = "<html><body><h1>Stan</h1><p>Charged <b>$10</b></p></body></html>"
    body = (
        b"From: Stan <billing@stan.com.au>\r\nSubject: Renewal\r\nDate: D2\r\n"
        b"Content-Type: text/html\r\n\r\n" + html.encode()
    )
    fake = FakeIMAP(search_uids=[], bodies={"2": body})
    client = _client(fake)

    email = client.get_email("2")

    assert "Stan" in email.body
    assert "Charged" in email.body
    assert "<" not in email.body


def test_get_email_caps_body_length():
    long_text = "x" * (MAX_BODY_CHARS + 5000)
    body = (
        b"From: a@b.com\r\nSubject: s\r\nDate: d\r\n"
        b"Content-Type: text/plain\r\n\r\n" + long_text.encode()
    )
    fake = FakeIMAP(search_uids=[], bodies={"3": body})
    client = _client(fake)

    email = client.get_email("3")

    assert len(email.body) == MAX_BODY_CHARS


def test_get_email_decodes_mime_encoded_headers():
    body = (
        b"From: =?UTF-8?B?TsOpdGZsaXg=?= <info@netflix.com>\r\n"
        b"Subject: =?UTF-8?Q?Re=C3=A7u?=\r\nDate: D1\r\n"
        b"Content-Type: text/plain\r\n\r\nbody\r\n"
    )
    fake = FakeIMAP(search_uids=[], bodies={"9": body})
    client = _client(fake)

    email = client.get_email("9")

    assert email.sender == "Nétflix <info@netflix.com>"
    assert email.subject == "Reçu"


def test_check_login_raises_on_bad_credentials(monkeypatch):
    import imaplib

    import app.integrations.email_imap as imap_mod

    fake = FakeIMAP(search_uids=[], fail_login=True)
    monkeypatch.setattr(imap_mod.imaplib, "IMAP4_SSL", lambda host: fake)

    client = ImapClient.from_credentials("imap.gmail.com", "me@gmail.com", "bad")
    with pytest.raises(imaplib.IMAP4.error):
        client.check_login()


def test_check_login_succeeds_with_real_connect_path(monkeypatch):
    import app.integrations.email_imap as imap_mod

    fake = FakeIMAP(search_uids=[])
    monkeypatch.setattr(imap_mod.imaplib, "IMAP4_SSL", lambda host: fake)

    client = ImapClient.from_credentials("imap.gmail.com", "me@gmail.com", "app-pass")
    client.check_login()  # no raise

    # Real _connect path: logged in, opened read-only, then logged out.
    assert ("login", "me@gmail.com", "app-pass") in fake.calls
    assert fake.select_kwargs["readonly"] is True
    assert fake.logged_out is True
