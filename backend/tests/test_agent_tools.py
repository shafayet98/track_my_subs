"""Agent tool executor tests — tenant scoping, upsert, dedup, get_email.

The Gmail boundary is a tiny fake; no network. Executors run against the real
(in-memory SQLite) DB session.
"""

import json
import uuid

from sqlalchemy import select

from app.agent.tools import ScanContext, execute_tool
from app.integrations.gmail import EmailContent
from app.models import Payment, Subscription


class _FakeGmail:
    def __init__(self, emails: dict[str, EmailContent]):
        self._emails = emails

    def get_email(self, message_id: str) -> EmailContent:
        return self._emails[message_id]


def _ctx(session, user_id, *, gmail=None, candidates=None) -> ScanContext:
    return ScanContext(
        db=session,
        user_id=user_id,
        scan_run_id=uuid.uuid4(),
        gmail=gmail or _FakeGmail({}),
        candidates=candidates or [],
    )


async def test_upsert_subscription_creates_then_updates(session, make_user):
    user = await make_user("agent@example.com")
    ctx = _ctx(session, user["user_id"])

    out, err = await execute_tool(
        ctx,
        "upsert_subscription",
        {"merchant_name": "Netflix", "amount": 9.99, "currency": "USD", "billing_cycle": "monthly"},
    )
    assert not err
    created = json.loads(out)
    assert created["created"] is True
    sid = created["subscription_id"]
    assert ctx.subscriptions_found == 1

    out2, _ = await execute_tool(
        ctx, "upsert_subscription", {"merchant_name": "Netflix", "amount": 12.99}
    )
    updated = json.loads(out2)
    assert updated["subscription_id"] == sid
    assert updated["created"] is False
    assert ctx.subscriptions_found == 1  # no duplicate

    sub = await session.get(Subscription, uuid.UUID(sid))
    assert sub.amount == 12.99


async def test_record_payment_scopes_to_user_and_dedups(session, make_user):
    user = await make_user("pay@example.com")
    ctx = _ctx(session, user["user_id"])
    sid = json.loads(
        (await execute_tool(ctx, "upsert_subscription", {"merchant_name": "Spotify"}))[0]
    )["subscription_id"]

    out, err = await execute_tool(
        ctx,
        "record_payment",
        {
            "subscription_id": sid,
            "amount": 9.99,
            "currency": "USD",
            "occurred_on": "2026-05-01",
            "source_message_id": "m1",
        },
    )
    assert not err

    # Same source_message_id → idempotent, no second row.
    out2, _ = await execute_tool(
        ctx,
        "record_payment",
        {
            "subscription_id": sid,
            "amount": 9.99,
            "occurred_on": "2026-05-01",
            "source_message_id": "m1",
        },
    )
    assert json.loads(out2)["duplicate"] is True

    rows = (await session.scalars(select(Payment).where(Payment.user_id == user["user_id"]))).all()
    assert len(rows) == 1
    assert rows[0].source_message_id == "m1"


async def test_record_payment_rejects_foreign_subscription(session, make_user):
    a = await make_user("a@example.com")
    b = await make_user("b@example.com")

    ctx_a = _ctx(session, a["user_id"])
    sid = json.loads(
        (await execute_tool(ctx_a, "upsert_subscription", {"merchant_name": "AWS"}))[0]
    )["subscription_id"]

    ctx_b = _ctx(session, b["user_id"])
    out, err = await execute_tool(
        ctx_b,
        "record_payment",
        {"subscription_id": sid, "amount": 5.0, "occurred_on": "2026-01-01"},
    )
    assert err is True
    assert "unknown subscription_id" in json.loads(out)["error"]

    rows = (await session.scalars(select(Payment))).all()
    assert rows == []  # nothing written across the tenant boundary


async def test_record_payment_rejects_bad_date(session, make_user):
    user = await make_user("bad@example.com")
    ctx = _ctx(session, user["user_id"])
    sid = json.loads(
        (await execute_tool(ctx, "upsert_subscription", {"merchant_name": "Stan"}))[0]
    )["subscription_id"]

    out, err = await execute_tool(
        ctx, "record_payment", {"subscription_id": sid, "amount": 10.0, "occurred_on": "May 1"}
    )
    assert err is True
    assert "invalid date" in json.loads(out)["error"]


async def test_get_email_returns_body_and_counts(session, make_user):
    user = await make_user("read@example.com")
    gmail = _FakeGmail(
        {
            "m1": EmailContent(
                "m1", "Netflix <i@netflix.com>", "Receipt", "D1", "Paid $9.99 on May 1"
            )
        }
    )
    ctx = _ctx(session, user["user_id"], gmail=gmail)

    out, err = await execute_tool(ctx, "get_email", {"message_id": "m1"})
    assert not err
    assert "Paid $9.99" in json.loads(out)["body"]
    assert ctx.emails_scanned == 1


async def test_finish_scan_sets_state(session, make_user):
    user = await make_user("fin@example.com")
    ctx = _ctx(session, user["user_id"])
    out, err = await execute_tool(ctx, "finish_scan", {"summary": "Found 2 subscriptions."})
    assert not err
    assert ctx.finished is True
    assert ctx.summary == "Found 2 subscriptions."
