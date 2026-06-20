"""Detection-logic tests for proactive notifications (pure, no DB/network)."""

import uuid
from datetime import date
from types import SimpleNamespace

from app.services.alerts import (
    MISSED_PAYMENT,
    RENEWAL,
    TRIAL_CONVERSION,
    PrefsView,
    due_notifications,
)

TODAY = date(2026, 6, 21)


def _sub(**kw) -> SimpleNamespace:
    return SimpleNamespace(
        id=kw.get("id", uuid.uuid4()),
        merchant_name=kw.get("merchant_name", "Netflix"),
        status=kw.get("status", "active"),
        amount=kw.get("amount", 15.99),
        currency=kw.get("currency", "USD"),
        next_payment_date=kw.get("next_payment_date"),
        trial_end_date=kw.get("trial_end_date"),
    )


def _payment(sub, **kw) -> SimpleNamespace:
    return SimpleNamespace(
        subscription_id=sub.id,
        status=kw.get("status", "missing"),
        amount=kw.get("amount", 9.99),
        currency=kw.get("currency", "USD"),
        occurred_on=kw.get("occurred_on", date(2026, 6, 3)),
    )


def test_renewal_within_lead_window_fires():
    sub = _sub(next_payment_date=date(2026, 6, 23))  # 2 days out, lead=3
    events = due_notifications([sub], [], None, set(), TODAY)
    assert len(events) == 1
    e = events[0]
    assert e.event_type == RENEWAL
    assert e.event_date == date(2026, 6, 23)
    assert e.merchant_name == "Netflix"
    assert e.amount == 15.99


def test_renewal_outside_window_does_not_fire():
    sub = _sub(next_payment_date=date(2026, 6, 25))  # 4 days out, lead=3
    assert due_notifications([sub], [], None, set(), TODAY) == []


def test_renewal_in_the_past_does_not_fire():
    sub = _sub(next_payment_date=date(2026, 6, 20))  # yesterday
    assert due_notifications([sub], [], None, set(), TODAY) == []


def test_window_boundaries_inclusive():
    today_sub = _sub(id=uuid.uuid4(), next_payment_date=TODAY)
    edge_sub = _sub(id=uuid.uuid4(), next_payment_date=date(2026, 6, 24))  # today + 3
    events = due_notifications([today_sub, edge_sub], [], None, set(), TODAY)
    assert {e.subscription_id for e in events} == {today_sub.id, edge_sub.id}


def test_trial_conversion_fires_with_amount():
    sub = _sub(trial_end_date=date(2026, 6, 22), amount=96.0, next_payment_date=None)
    events = due_notifications([sub], [], None, set(), TODAY)
    assert len(events) == 1
    assert events[0].event_type == TRIAL_CONVERSION
    assert events[0].amount == 96.0


def test_missed_payment_fires_regardless_of_window():
    sub = _sub(next_payment_date=None)
    pay = _payment(sub, status="overdue", occurred_on=date(2026, 6, 3))
    events = due_notifications([sub], [pay], None, set(), TODAY)
    assert len(events) == 1
    assert events[0].event_type == MISSED_PAYMENT
    assert events[0].event_date == date(2026, 6, 3)


def test_paid_payment_is_not_an_alert():
    sub = _sub(next_payment_date=None)
    pay = _payment(sub, status="paid")
    assert due_notifications([sub], [pay], None, set(), TODAY) == []


def test_dedup_skips_already_sent():
    sub = _sub(next_payment_date=date(2026, 6, 23))
    already = {(sub.id, RENEWAL, date(2026, 6, 23))}
    assert due_notifications([sub], [], None, already, TODAY) == []


def test_prefs_disable_each_type():
    sub = _sub(next_payment_date=date(2026, 6, 23), trial_end_date=date(2026, 6, 22))
    pay = _payment(sub, status="missing")

    no_renewals = PrefsView(renewals_enabled=False)
    types = {e.event_type for e in due_notifications([sub], [pay], no_renewals, set(), TODAY)}
    assert RENEWAL not in types and TRIAL_CONVERSION in types and MISSED_PAYMENT in types

    no_trials = PrefsView(trial_conversions_enabled=False)
    types = {e.event_type for e in due_notifications([sub], [pay], no_trials, set(), TODAY)}
    assert TRIAL_CONVERSION not in types

    no_missed = PrefsView(missed_payments_enabled=False)
    types = {e.event_type for e in due_notifications([sub], [pay], no_missed, set(), TODAY)}
    assert MISSED_PAYMENT not in types


def test_custom_lead_time():
    sub = _sub(next_payment_date=date(2026, 6, 28))  # 7 days out
    assert due_notifications([sub], [], PrefsView(lead_time_days=3), set(), TODAY) == []
    events = due_notifications([sub], [], PrefsView(lead_time_days=7), set(), TODAY)
    assert len(events) == 1


def test_duplicate_payment_rows_yield_one_event():
    sub = _sub(next_payment_date=None)
    pay1 = _payment(sub, status="missing", occurred_on=date(2026, 6, 3))
    pay2 = _payment(sub, status="missing", occurred_on=date(2026, 6, 3))
    events = due_notifications([sub], [pay1, pay2], None, set(), TODAY)
    assert len(events) == 1


def test_cancelled_subscription_is_skipped():
    sub = _sub(status="cancelled", next_payment_date=date(2026, 6, 22))
    pay = _payment(sub, status="overdue")
    assert due_notifications([sub], [pay], None, set(), TODAY) == []
