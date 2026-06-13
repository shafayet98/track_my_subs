"""Gmail OAuth endpoint tests. The code-exchange network call is patched."""

from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from app.core.security import create_oauth_state, decrypt_token
from app.integrations.gmail import OAuthResult
from app.models import EmailAccount


async def test_connect_requires_auth(client):
    r = await client.get("/api/accounts/gmail/connect")
    assert r.status_code == 401  # no bearer token


async def test_connect_returns_consent_url(client, make_user):
    user = await make_user("connect@example.com")
    r = await client.get("/api/accounts/gmail/connect", headers=user["headers"])
    assert r.status_code == 200

    url = r.json()["authorization_url"]
    qs = parse_qs(urlparse(url).query)
    assert qs["scope"] == ["https://www.googleapis.com/auth/gmail.readonly"]
    assert qs["access_type"] == ["offline"]
    assert qs["state"]  # signed state present


async def test_callback_stores_encrypted_token_and_account(client, make_user, session, monkeypatch):
    import app.integrations.gmail as gmail_mod

    user = await make_user("cb@example.com")
    state = create_oauth_state(str(user["user_id"]))

    monkeypatch.setattr(
        gmail_mod,
        "exchange_code",
        lambda code: OAuthResult(email_address="inbox@gmail.com", refresh_token="refresh-xyz"),
    )

    r = await client.get(
        "/api/accounts/gmail/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "gmail=connected" in r.headers["location"]

    account = await session.scalar(
        select(EmailAccount).where(EmailAccount.user_id == user["user_id"])
    )
    assert account is not None
    assert account.email_address == "inbox@gmail.com"
    # Stored token is encrypted, not plaintext, and decrypts back.
    assert account.oauth_refresh_token_encrypted != "refresh-xyz"
    assert decrypt_token(account.oauth_refresh_token_encrypted) == "refresh-xyz"


async def test_callback_rejects_bad_state(client, monkeypatch):
    import app.integrations.gmail as gmail_mod

    monkeypatch.setattr(
        gmail_mod,
        "exchange_code",
        lambda code: OAuthResult(email_address="x@gmail.com", refresh_token="r"),
    )
    r = await client.get(
        "/api/accounts/gmail/callback",
        params={"code": "auth-code", "state": "not-a-valid-jwt"},
        follow_redirects=False,
    )
    assert r.status_code == 400


async def test_callback_reconnect_updates_token(client, make_user, session, monkeypatch):
    """Reconnecting the same mailbox upserts (no duplicate account row)."""
    import app.integrations.gmail as gmail_mod

    user = await make_user("re@example.com")
    state = create_oauth_state(str(user["user_id"]))

    tokens = iter(["token-1", "token-2"])
    monkeypatch.setattr(
        gmail_mod,
        "exchange_code",
        lambda code: OAuthResult(email_address="same@gmail.com", refresh_token=next(tokens)),
    )

    for _ in range(2):
        r = await client.get(
            "/api/accounts/gmail/callback",
            params={"code": "c", "state": state},
            follow_redirects=False,
        )
        assert r.status_code == 303

    accounts = (
        await session.scalars(select(EmailAccount).where(EmailAccount.user_id == user["user_id"]))
    ).all()
    assert len(accounts) == 1
    assert decrypt_token(accounts[0].oauth_refresh_token_encrypted) == "token-2"


@pytest.mark.parametrize("missing", ["code", "state"])
async def test_callback_requires_params(client, missing):
    params = {"code": "c", "state": "s"}
    del params[missing]
    r = await client.get("/api/accounts/gmail/callback", params=params)
    assert r.status_code == 422
