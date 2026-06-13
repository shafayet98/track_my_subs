"""Dashboard aggregation over seeded payments.

We seed payments at dates relative to a fixed "today" the service computes from,
so the month buckets are deterministic. The endpoints use date.today(), so tests
that assert exact months drive the service directly; the endpoint tests assert
shape + tenant scoping.
"""

from datetime import date

from app.models import Payment, Subscription
from app.services import dashboard as dashboard_service


async def _seed_subscription(session, user_id, **kwargs) -> Subscription:
    sub = Subscription(
        user_id=user_id,
        merchant_name=kwargs.pop("merchant_name", "Netflix"),
        billing_cycle=kwargs.pop("billing_cycle", "monthly"),
        amount=kwargs.pop("amount", 15.0),
        currency=kwargs.pop("currency", "USD"),
        status=kwargs.pop("status", "active"),
        **kwargs,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub


def _add_payment(session, sub, **kwargs):
    session.add(
        Payment(
            user_id=sub.user_id,
            subscription_id=sub.id,
            amount=kwargs.pop("amount", 15.0),
            currency=kwargs.pop("currency", "USD"),
            status=kwargs.pop("status", "paid"),
            occurred_on=kwargs.pop("occurred_on"),
            source_message_id=kwargs.pop("source_message_id", None),
        )
    )


async def test_summary_buckets_this_and_last_month(client, session, make_user):
    a = await make_user("a@x.com")
    today = date(2026, 6, 13)
    sub = await _seed_subscription(session, a["user_id"])

    # This month: two paid charges. Last month: one. Older (in-window) one.
    _add_payment(session, sub, amount=15.0, occurred_on=date(2026, 6, 1))
    _add_payment(session, sub, amount=5.0, occurred_on=date(2026, 6, 10))
    _add_payment(session, sub, amount=20.0, occurred_on=date(2026, 5, 3))
    _add_payment(session, sub, amount=9.0, occurred_on=date(2026, 1, 15))
    # An unpaid charge must not count toward spend.
    _add_payment(session, sub, amount=99.0, status="overdue", occurred_on=date(2026, 6, 2))
    await session.commit()

    summary = await dashboard_service.get_summary(session, a["user_id"], today=today)

    assert len(summary.monthly_spend) == 12
    assert summary.monthly_spend[-1].month == "2026-06"
    assert summary.monthly_spend[0].month == "2025-07"
    assert summary.this_month == 20.0  # 15 + 5, the overdue excluded
    assert summary.last_month == 20.0  # the May charge
    assert summary.active_subscriptions == 1

    by_month = {m.month: m.total for m in summary.monthly_spend}
    assert by_month["2026-06"] == 20.0
    assert by_month["2026-05"] == 20.0
    assert by_month["2026-01"] == 9.0
    assert by_month["2025-12"] == 0.0


async def test_summary_empty(client, make_user):
    a = await make_user("a@x.com")
    r = await client.get("/api/dashboard/summary", headers=a["headers"])
    assert r.status_code == 200
    body = r.json()
    assert len(body["monthly_spend"]) == 12
    assert all(m["total"] == 0.0 for m in body["monthly_spend"])
    assert body["this_month"] == 0.0
    assert body["last_month"] == 0.0
    assert body["active_subscriptions"] == 0


async def test_subscription_card_aggregates(session, make_user):
    a = await make_user("a@x.com")
    today = date(2026, 6, 13)
    sub = await _seed_subscription(
        session, a["user_id"], amount=15.0, next_payment_date=date(2026, 7, 1)
    )
    _add_payment(session, sub, amount=15.0, occurred_on=date(2026, 4, 1))
    _add_payment(session, sub, amount=15.0, occurred_on=date(2026, 5, 1))  # last month
    _add_payment(session, sub, amount=15.0, occurred_on=date(2026, 6, 1))
    _add_payment(session, sub, amount=15.0, status="overdue", occurred_on=date(2026, 6, 1))
    _add_payment(session, sub, amount=0.0, status="missing", occurred_on=date(2026, 3, 1))
    await session.commit()

    cards = await dashboard_service.get_subscription_cards(session, a["user_id"], today=today)
    assert len(cards) == 1
    card = cards[0]
    assert card.total_spent == 45.0  # three paid
    assert card.last_month_spent == 15.0  # the May one
    assert card.overdue_total == 15.0
    assert card.missing_count == 2  # one missing + one overdue
    assert card.next_payment_date == date(2026, 7, 1)
    assert card.next_payment_amount == 15.0


async def test_subscription_detail_endpoint(client, session, make_user):
    a = await make_user("a@x.com")
    sub = await _seed_subscription(session, a["user_id"], confidence=0.9)
    _add_payment(session, sub, amount=15.0, occurred_on=date(2026, 5, 1))
    _add_payment(session, sub, amount=15.0, occurred_on=date(2026, 6, 1))
    await session.commit()

    r = await client.get(f"/api/subscriptions/{sub.id}", headers=a["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["merchant_name"] == "Netflix"
    assert body["confidence"] == 0.9
    assert body["total_spent"] == 30.0
    assert len(body["payments"]) == 2
    # ordered newest first
    assert body["payments"][0]["occurred_on"] == "2026-06-01"
    assert "source_message_id" in body["payments"][0]


async def test_subscription_detail_cross_tenant_404(client, session, make_user):
    a = await make_user("a@x.com")
    b = await make_user("b@x.com")
    sub = await _seed_subscription(session, a["user_id"])

    r = await client.get(f"/api/subscriptions/{sub.id}", headers=b["headers"])
    assert r.status_code == 404


async def test_subscription_list_endpoint_shape(client, session, make_user):
    a = await make_user("a@x.com")
    await _seed_subscription(session, a["user_id"], merchant_name="Spotify")

    r = await client.get("/api/subscriptions", headers=a["headers"])
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["merchant_name"] == "Spotify"
    assert body[0]["total_spent"] == 0.0
    assert body[0]["missing_count"] == 0
