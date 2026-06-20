"""Pure detection logic for proactive notifications.

`due_notifications` takes plain data (a user's subscriptions, payments,
preferences, and the already-sent log) and returns the alert events that are due
now. No DB, no I/O, no clock — `today` is passed in. This keeps the core fully
unit-testable without a scheduler or SES; the Stage-B worker wires it to the DB
and email delivery (see docs/plans/Renewal_And_Trial_Alerts.md).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from app.models.notification_preference import DEFAULT_LEAD_TIME_DAYS

RENEWAL = "renewal"
TRIAL_CONVERSION = "trial_conversion"
MISSED_PAYMENT = "missed_payment"

_MISSED_STATUSES = ("missing", "overdue")


@dataclass(frozen=True)
class PrefsView:
    """The preference fields detection needs. Defaults match a missing DB row."""

    renewals_enabled: bool = True
    trial_conversions_enabled: bool = True
    missed_payments_enabled: bool = True
    lead_time_days: int = DEFAULT_LEAD_TIME_DAYS


@dataclass(frozen=True)
class DueEvent:
    """One alert to send. Parsed facts only — never any email content."""

    subscription_id: object
    event_type: str
    event_date: date
    merchant_name: str
    amount: float | None
    currency: str | None


def due_notifications(
    subscriptions: Iterable[object],
    payments: Iterable[object],
    prefs: PrefsView | None,
    already_sent: set[tuple[object, str, date]],
    today: date,
) -> list[DueEvent]:
    """Return the alert events due today, deduped against `already_sent`.

    An event fires when its date falls in the lead window
    `[today, today + lead_time_days]` (renewals, trial conversions) or as soon as
    a missing/overdue payment exists (missed payments). Disabled alert types and
    already-sent `(subscription_id, event_type, event_date)` triples are skipped.
    """
    prefs = prefs or PrefsView()
    window_end = today + timedelta(days=prefs.lead_time_days)
    subs = list(subscriptions)
    by_id = {sub.id: sub for sub in subs}
    events: list[DueEvent] = []
    seen: set[tuple[object, str, date]] = set()

    def emit(sub: object, event_type: str, event_date: date, amount, currency) -> None:
        key = (sub.id, event_type, event_date)
        if key in already_sent or key in seen:
            return
        seen.add(key)
        events.append(
            DueEvent(
                subscription_id=sub.id,
                event_type=event_type,
                event_date=event_date,
                merchant_name=sub.merchant_name,
                amount=amount,
                currency=currency,
            )
        )

    for sub in subs:
        if sub.status == "cancelled":
            continue
        if (
            prefs.renewals_enabled
            and sub.next_payment_date is not None
            and today <= sub.next_payment_date <= window_end
        ):
            emit(sub, RENEWAL, sub.next_payment_date, sub.amount, sub.currency)
        if (
            prefs.trial_conversions_enabled
            and sub.trial_end_date is not None
            and today <= sub.trial_end_date <= window_end
        ):
            emit(sub, TRIAL_CONVERSION, sub.trial_end_date, sub.amount, sub.currency)

    if prefs.missed_payments_enabled:
        for payment in payments:
            if payment.status not in _MISSED_STATUSES:
                continue
            sub = by_id.get(payment.subscription_id)
            if sub is None or sub.status == "cancelled":
                continue
            emit(sub, MISSED_PAYMENT, payment.occurred_on, payment.amount, payment.currency)

    return events
