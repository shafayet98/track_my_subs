"""Response schemas for the dashboard + subscription endpoints."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class MonthlySpend(BaseModel):
    """One bucket of the spend chart: a calendar month and its paid total."""

    month: str  # "YYYY-MM"
    total: float


class DashboardSummary(BaseModel):
    monthly_spend: list[MonthlySpend]  # last 12 months, oldest first
    this_month: float
    last_month: float
    active_subscriptions: int


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: float
    currency: str | None = None
    status: str
    occurred_on: date
    source_message_id: str | None = None


class SubscriptionCard(BaseModel):
    """A subscription plus the aggregates a dashboard card shows."""

    id: uuid.UUID
    merchant_name: str
    category: str | None = None
    billing_cycle: str
    amount: float | None = None
    currency: str | None = None
    status: str
    next_payment_date: date | None = None
    next_payment_amount: float | None = None
    total_spent: float
    last_month_spent: float
    overdue_total: float
    missing_count: int


class SubscriptionDetail(SubscriptionCard):
    """The card aggregates plus the full payment history for the drill-down."""

    confidence: float | None = None
    payments: list[PaymentOut]
