"""Dashboard aggregation.

Turns a user's `subscriptions` + `payments` into the numbers the frontend
renders: the monthly-spend chart, this-vs-last-month totals, and per-subscription
cards/detail. Every query is tenant-scoped on `user_id`.

We bucket payments by calendar month in Python rather than with Postgres'
`date_trunc`, so the same codepath runs on SQLite (tests/CI) and Postgres. A
single user's payment set is small, so this is cheap.
"""

import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Payment, Subscription
from app.schemas.dashboard import (
    DashboardSummary,
    MonthlySpend,
    PaymentOut,
    SubscriptionCard,
    SubscriptionDetail,
)

CHART_MONTHS = 12


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    """Shift a (year, month) pair by `delta` months."""
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def _month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _month_window(today: date, months: int) -> list[tuple[int, int]]:
    """The last `months` calendar months ending at `today`'s month, oldest first."""
    return [_add_months(today.year, today.month, -i) for i in range(months - 1, -1, -1)]


async def get_summary(
    db: AsyncSession, user_id: uuid.UUID, today: date | None = None
) -> DashboardSummary:
    today = today or date.today()

    paid = await db.scalars(
        select(Payment).where(Payment.user_id == user_id, Payment.status == "paid")
    )
    by_month: dict[tuple[int, int], float] = defaultdict(float)
    for p in paid:
        by_month[(p.occurred_on.year, p.occurred_on.month)] += p.amount

    monthly_spend = [
        MonthlySpend(month=_month_key(y, m), total=round(by_month.get((y, m), 0.0), 2))
        for (y, m) in _month_window(today, CHART_MONTHS)
    ]
    this_month = round(by_month.get((today.year, today.month), 0.0), 2)
    last_month = round(by_month.get(_add_months(today.year, today.month, -1), 0.0), 2)

    active_subscriptions = await db.scalar(
        select(func.count())
        .select_from(Subscription)
        .where(Subscription.user_id == user_id, Subscription.status == "active")
    )

    return DashboardSummary(
        monthly_spend=monthly_spend,
        this_month=this_month,
        last_month=last_month,
        active_subscriptions=active_subscriptions or 0,
    )


def _card_aggregates(payments: list[Payment], today: date) -> dict:
    """Per-subscription spend aggregates from its payment rows."""
    last_y, last_m = _add_months(today.year, today.month, -1)
    total_spent = 0.0
    last_month_spent = 0.0
    overdue_total = 0.0
    missing_count = 0
    for p in payments:
        if p.status == "paid":
            total_spent += p.amount
            if (p.occurred_on.year, p.occurred_on.month) == (last_y, last_m):
                last_month_spent += p.amount
        if p.status == "overdue":
            overdue_total += p.amount
        if p.status in ("missing", "overdue"):
            missing_count += 1
    return {
        "total_spent": round(total_spent, 2),
        "last_month_spent": round(last_month_spent, 2),
        "overdue_total": round(overdue_total, 2),
        "missing_count": missing_count,
    }


def _to_card(sub: Subscription, payments: list[Payment], today: date) -> SubscriptionCard:
    return SubscriptionCard(
        id=sub.id,
        merchant_name=sub.merchant_name,
        category=sub.category,
        billing_cycle=sub.billing_cycle,
        amount=sub.amount,
        currency=sub.currency,
        status=sub.status,
        next_payment_date=sub.next_payment_date,
        next_payment_amount=sub.amount,
        **_card_aggregates(payments, today),
    )


async def get_subscription_cards(
    db: AsyncSession, user_id: uuid.UUID, today: date | None = None
) -> list[SubscriptionCard]:
    today = today or date.today()
    subs = list(await db.scalars(select(Subscription).where(Subscription.user_id == user_id)))
    payments = await db.scalars(select(Payment).where(Payment.user_id == user_id))
    by_sub: dict[uuid.UUID, list[Payment]] = defaultdict(list)
    for p in payments:
        by_sub[p.subscription_id].append(p)
    return [_to_card(sub, by_sub.get(sub.id, []), today) for sub in subs]


async def get_subscription_detail(
    db: AsyncSession, sub: Subscription, today: date | None = None
) -> SubscriptionDetail:
    today = today or date.today()
    payments = list(
        await db.scalars(
            select(Payment)
            .where(Payment.subscription_id == sub.id)
            .order_by(Payment.occurred_on.desc())
        )
    )
    card = _to_card(sub, payments, today)
    return SubscriptionDetail(
        **card.model_dump(),
        confidence=sub.confidence,
        payments=[PaymentOut.model_validate(p) for p in payments],
    )
