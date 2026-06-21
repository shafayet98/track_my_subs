"""Agent loop tests with a fake Anthropic client — no network.

Asserts the loop terminates on finish/end_turn, on a refusal, and on the
iteration cap, and that a tool call writes a correctly-scoped row.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.agent.loop import run_agent_loop, run_scan_job
from app.agent.tools import ScanContext
from app.core.config import settings
from app.models import EmailAccount, Payment, ScanRun, Subscription


@dataclass
class FakeToolUse:
    name: str
    input: dict
    id: str = "tu_1"
    type: str = "tool_use"


@dataclass
class FakeResponse:
    stop_reason: str
    content: list = field(default_factory=list)


class _FakeMessages:
    def __init__(self, responses, default):
        self._responses = list(responses)
        self._default = default
        self._i = 0
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        if self._i < len(self._responses):
            resp = self._responses[self._i]
            self._i += 1
            return resp
        return self._default or FakeResponse("end_turn")


class FakeAnthropic:
    def __init__(self, responses, default=None):
        self.messages = _FakeMessages(responses, default)


class _FakeGmail:
    def get_email(self, message_id):  # pragma: no cover - not exercised here
        raise AssertionError("get_email should not be called in this test")


def _ctx(session, user_id, candidates=None) -> ScanContext:
    return ScanContext(
        db=session,
        user_id=user_id,
        scan_run_id=uuid.uuid4(),
        gmail=_FakeGmail(),
        candidates=candidates or [],
    )


async def test_loop_records_payment_and_completes(session, make_user):
    user = await make_user("loop@example.com")
    sub = Subscription(user_id=user["user_id"], merchant_name="Spotify")
    session.add(sub)
    await session.commit()
    await session.refresh(sub)

    responses = [
        FakeResponse(
            "tool_use",
            [
                FakeToolUse(
                    "record_payment",
                    {
                        "subscription_id": str(sub.id),
                        "amount": 9.99,
                        "currency": "USD",
                        "occurred_on": "2026-05-01",
                        "source_message_id": "m1",
                    },
                    id="t1",
                )
            ],
        ),
        FakeResponse("tool_use", [FakeToolUse("finish_scan", {"summary": "done"}, id="t2")]),
    ]
    ctx = _ctx(session, user["user_id"])

    result = await run_agent_loop(ctx, FakeAnthropic(responses))

    assert result == "completed"
    assert ctx.summary == "done"
    payments = (
        await session.scalars(select(Payment).where(Payment.user_id == user["user_id"]))
    ).all()
    assert len(payments) == 1
    assert payments[0].amount == 9.99


async def test_loop_returns_on_end_turn(session, make_user):
    user = await make_user("end@example.com")
    ctx = _ctx(session, user["user_id"])
    result = await run_agent_loop(ctx, FakeAnthropic([FakeResponse("end_turn", [])]))
    assert result == "completed"


async def test_loop_handles_refusal_without_raising(session, make_user):
    user = await make_user("refuse@example.com")
    ctx = _ctx(session, user["user_id"])
    result = await run_agent_loop(ctx, FakeAnthropic([FakeResponse("refusal", [])]))
    assert result == "refused"
    assert ctx.summary  # a graceful summary was set


async def test_loop_stops_at_max_iterations(session, make_user):
    user = await make_user("cap@example.com")
    ctx = _ctx(session, user["user_id"])
    # Always asks for a read-only tool → never ends → hits the cap.
    forever = FakeResponse("tool_use", [FakeToolUse("list_candidate_emails", {}, id="t")])
    client = FakeAnthropic([], default=forever)

    result = await run_agent_loop(ctx, client, max_iterations=3)

    assert result == "max_iterations"
    assert client.messages.calls == 3


async def test_scan_job_searches_within_lookback_window(session, make_user, monkeypatch):
    """run_scan_job must pass search_candidates an `after` ~ now - scan_lookback_days."""
    user = await make_user("window@example.com")
    account = EmailAccount(
        user_id=user["user_id"],
        provider="gmail",
        email_address="window@example.com",
        oauth_refresh_token_encrypted="enc",
    )
    scan = ScanRun(user_id=user["user_id"], status="running")
    session.add_all([account, scan])
    await session.commit()
    await session.refresh(scan)

    captured: dict = {}

    class _FakeGmail:
        @classmethod
        def from_refresh_token(cls, _token):
            return cls()

        def search_candidates(self, *, after=None):
            captured["after"] = after
            return []

    async def _fake_loop(ctx, client, **kwargs):
        return "completed"

    class _SessionCtx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr("app.agent.loop.SessionLocal", lambda: _SessionCtx())
    monkeypatch.setattr("app.agent.loop.decrypt_token", lambda _enc: "tok")
    monkeypatch.setattr("app.agent.loop.GmailClient", _FakeGmail)
    monkeypatch.setattr("app.agent.loop.get_anthropic_client", lambda: object())
    monkeypatch.setattr("app.agent.loop.run_agent_loop", _fake_loop)

    await run_scan_job(scan.id, user["user_id"])

    expected = datetime.now(UTC) - timedelta(days=settings.scan_lookback_days)
    assert captured["after"] is not None
    assert abs((captured["after"] - expected).total_seconds()) < 60


async def test_scan_job_scans_all_accounts(session, make_user, monkeypatch):
    """run_scan_job iterates every connected account and aggregates the counts."""
    user = await make_user("multi@example.com")
    acct1 = EmailAccount(
        user_id=user["user_id"],
        provider="gmail",
        email_address="a@example.com",
        oauth_refresh_token_encrypted="enc1",
    )
    acct2 = EmailAccount(
        user_id=user["user_id"],
        provider="gmail",
        email_address="b@example.com",
        oauth_refresh_token_encrypted="enc2",
    )
    scan = ScanRun(user_id=user["user_id"], status="running")
    session.add_all([acct1, acct2, scan])
    await session.commit()
    await session.refresh(scan)

    seen_tokens: list[str] = []

    class _FakeGmail:
        def __init__(self, token):
            self.token = token

        @classmethod
        def from_refresh_token(cls, token):
            seen_tokens.append(token)
            return cls(token)

        def search_candidates(self, *, after=None):
            return []

    async def _fake_loop(ctx, client, **kwargs):
        # Each account contributes to the aggregate.
        ctx.emails_scanned = 2
        ctx.subscriptions_found = 1
        ctx.summary = "found stuff"
        return "completed"

    class _SessionCtx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr("app.agent.loop.SessionLocal", lambda: _SessionCtx())
    monkeypatch.setattr("app.agent.loop.decrypt_token", lambda enc: enc)
    monkeypatch.setattr("app.agent.loop.GmailClient", _FakeGmail)
    monkeypatch.setattr("app.agent.loop.get_anthropic_client", lambda: object())
    monkeypatch.setattr("app.agent.loop.run_agent_loop", _fake_loop)

    await run_scan_job(scan.id, user["user_id"])

    # Both mailboxes were opened with their own decrypted token.
    assert sorted(seen_tokens) == ["enc1", "enc2"]
    await session.refresh(scan)
    assert scan.emails_scanned == 4
    assert scan.subscriptions_found == 2
    assert scan.status == "succeeded"
    # Summary aggregates both, prefixed with the mailbox address.
    assert "a@example.com:" in scan.summary
    assert "b@example.com:" in scan.summary
