"""IMAP connect endpoint tests. The IMAP login is patched (no network)."""

import pytest
from sqlalchemy import select

from app.core.security import decrypt_token
from app.models import EmailAccount


def _patch_login(monkeypatch, *, fail: bool = False):
    import app.api.accounts as accounts_mod

    def fake_check_login(self):
        if fail:
            import imaplib

            raise imaplib.IMAP4.error("auth failed")

    monkeypatch.setattr(accounts_mod.ImapClient, "check_login", fake_check_login)


async def test_imap_connect_requires_auth(client):
    r = await client.post(
        "/api/accounts/imap/connect",
        json={"email_address": "me@gmail.com", "app_password": "abcd efgh ijkl mnop"},
    )
    assert r.status_code == 401


async def test_imap_connect_stores_encrypted_password(client, make_user, session, monkeypatch):
    _patch_login(monkeypatch)
    user = await make_user("imap@example.com")

    r = await client.post(
        "/api/accounts/imap/connect",
        headers=user["headers"],
        json={"email_address": "inbox@gmail.com", "app_password": "secret-app-pw"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["provider"] == "imap"
    assert r.json()["email_address"] == "inbox@gmail.com"

    account = await session.scalar(
        select(EmailAccount).where(EmailAccount.user_id == user["user_id"])
    )
    assert account is not None
    assert account.provider == "imap"
    assert account.imap_host == "imap.gmail.com"  # default host
    # Stored password is encrypted, not plaintext, and decrypts back.
    assert account.app_password_encrypted != "secret-app-pw"
    assert decrypt_token(account.app_password_encrypted) == "secret-app-pw"


async def test_imap_connect_custom_host(client, make_user, session, monkeypatch):
    _patch_login(monkeypatch)
    user = await make_user("fastmail@example.com")

    r = await client.post(
        "/api/accounts/imap/connect",
        headers=user["headers"],
        json={
            "email_address": "me@fastmail.com",
            "app_password": "pw",
            "imap_host": "imap.fastmail.com",
        },
    )
    assert r.status_code == 200

    account = await session.scalar(
        select(EmailAccount).where(EmailAccount.user_id == user["user_id"])
    )
    assert account.imap_host == "imap.fastmail.com"


async def test_imap_connect_bad_credentials_returns_400(client, make_user, session, monkeypatch):
    _patch_login(monkeypatch, fail=True)
    user = await make_user("bad@example.com")

    r = await client.post(
        "/api/accounts/imap/connect",
        headers=user["headers"],
        json={"email_address": "inbox@gmail.com", "app_password": "wrong"},
    )
    assert r.status_code == 400

    # Nothing stored on failure.
    account = await session.scalar(
        select(EmailAccount).where(EmailAccount.user_id == user["user_id"])
    )
    assert account is None


async def test_imap_connect_reconnect_upserts(client, make_user, session, monkeypatch):
    _patch_login(monkeypatch)
    user = await make_user("re-imap@example.com")

    for pw in ("pw-1", "pw-2"):
        r = await client.post(
            "/api/accounts/imap/connect",
            headers=user["headers"],
            json={"email_address": "same@gmail.com", "app_password": pw},
        )
        assert r.status_code == 200

    accounts = (
        await session.scalars(select(EmailAccount).where(EmailAccount.user_id == user["user_id"]))
    ).all()
    assert len(accounts) == 1
    assert decrypt_token(accounts[0].app_password_encrypted) == "pw-2"


@pytest.mark.parametrize("missing", ["email_address", "app_password"])
async def test_imap_connect_requires_fields(client, make_user, monkeypatch, missing):
    _patch_login(monkeypatch)
    user = await make_user(f"missing-{missing}@example.com")

    body = {"email_address": "me@gmail.com", "app_password": "pw"}
    del body[missing]
    r = await client.post("/api/accounts/imap/connect", headers=user["headers"], json=body)
    assert r.status_code == 422
