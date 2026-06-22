"""Notification preferences + the alert-delivery worker logic.

Two concerns live here: reading/writing a user's `NotificationPreference` (the
prefs API) and the per-user alert run the worker drives — load a user's data,
ask the pure `due_notifications` core what's due, send one summary email via SES,
and record a `Notification` row per event so it's never sent twice.

Everything is tenant-scoped on `user_id`. Emails carry parsed facts only
(merchant, amount, date); the sent log stores ids/dates/types, never any email
content. See `.claude/rules/security.md`.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.ses_client import SesClient
from app.models import (
    Notification,
    NotificationPreference,
    Payment,
    Subscription,
    User,
)
from app.models.notification_preference import DEFAULT_LEAD_TIME_DAYS
from app.services.alerts import (
    MISSED_PAYMENT,
    RENEWAL,
    TRIAL_CONVERSION,
    DueEvent,
    PrefsView,
    due_notifications,
)

logger = logging.getLogger(__name__)

_EVENT_VERB = {
    RENEWAL: "renews",
    TRIAL_CONVERSION: "trial converts to paid",
    MISSED_PAYMENT: "payment looks missed",
}


# --- preferences (used by the API) ---------------------------------------


async def get_preferences(db: AsyncSession, user_id: uuid.UUID) -> NotificationPreference:
    """The user's preference row, or a transient default (not persisted).

    A missing row means defaults everywhere; returning an unsaved instance lets
    the API reflect those defaults without writing on a read.
    """
    pref = await db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    if pref is not None:
        return pref
    # Column defaults only apply on INSERT, so an unsaved instance would carry
    # None; set the defaults explicitly for the read path.
    return NotificationPreference(
        user_id=user_id,
        renewals_enabled=True,
        trial_conversions_enabled=True,
        missed_payments_enabled=True,
        lead_time_days=DEFAULT_LEAD_TIME_DAYS,
    )


async def update_preferences(
    db: AsyncSession, user_id: uuid.UUID, **fields: object
) -> NotificationPreference:
    """Upsert the user's preferences, setting only the provided fields."""
    pref = await db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    if pref is None:
        pref = NotificationPreference(user_id=user_id)
        db.add(pref)
    for key, value in fields.items():
        setattr(pref, key, value)
    await db.commit()
    await db.refresh(pref)
    return pref


def _prefs_view(pref: NotificationPreference) -> PrefsView:
    return PrefsView(
        renewals_enabled=pref.renewals_enabled,
        trial_conversions_enabled=pref.trial_conversions_enabled,
        missed_payments_enabled=pref.missed_payments_enabled,
        lead_time_days=pref.lead_time_days,
    )


# --- email rendering ------------------------------------------------------


def _format_amount(amount: float | None, currency: str | None) -> str:
    if amount is None:
        return ""
    money = f"{currency} {amount:.2f}" if currency else f"{amount:.2f}"
    return f" — {money}"


def _event_line(event: DueEvent) -> str:
    verb = _EVENT_VERB.get(event.event_type, event.event_type)
    when = event.event_date.strftime("%a %d %b %Y")
    return f"{event.merchant_name} {verb} on {when}{_format_amount(event.amount, event.currency)}"


def render_alert_email(events: list[DueEvent]) -> tuple[str, str, str]:
    """Render (subject, text_body, html_body) for a user's due events."""
    lines = [_event_line(e) for e in events]
    count = len(events)
    subject = (
        f"track_my_subs: {lines[0]}"
        if count == 1
        else f"track_my_subs: {count} subscription alerts"
    )

    manage_url = f"{settings.app_base_url}/settings"
    text_body = (
        "Heads up before money moves:\n\n"
        + "\n".join(f"  • {line}" for line in lines)
        + f"\n\nManage your subscriptions or alert settings: {manage_url}\n"
    )
    items = "".join(f"<li>{line}</li>" for line in lines)
    html_body = (
        "<p>Heads up before money moves:</p>"
        f"<ul>{items}</ul>"
        f'<p><a href="{manage_url}">Manage your subscriptions or alert settings</a></p>'
    )
    return subject, text_body, html_body


# --- worker run -----------------------------------------------------------


async def _already_sent(db: AsyncSession, user_id: uuid.UUID) -> set[tuple[uuid.UUID, str, date]]:
    rows = await db.execute(
        select(
            Notification.subscription_id,
            Notification.event_type,
            Notification.event_date,
        ).where(Notification.user_id == user_id)
    )
    return {(sub_id, event_type, event_date) for sub_id, event_type, event_date in rows}


async def run_user_alerts(
    db: AsyncSession,
    user: User,
    ses: SesClient | None,
    today: date,
) -> list[DueEvent]:
    """Detect, send, and record due alerts for one user. Returns the events sent.

    Records `Notification` rows only after a successful send, so a delivery
    failure leaves the event eligible to retry on the next run.
    """
    subscriptions = (
        await db.scalars(select(Subscription).where(Subscription.user_id == user.id))
    ).all()
    payments = (await db.scalars(select(Payment).where(Payment.user_id == user.id))).all()
    prefs = _prefs_view(await get_preferences(db, user.id))
    already_sent = await _already_sent(db, user.id)

    due = due_notifications(subscriptions, payments, prefs, already_sent, today)
    if not due:
        return []

    if ses is None:
        logger.info("SES sender not configured; skipping %d alert(s) for user", len(due))
        return []

    subject, text_body, html_body = render_alert_email(due)
    await asyncio.to_thread(
        ses.send_email,
        to=user.email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )

    now = datetime.now(UTC)
    for event in due:
        db.add(
            Notification(
                user_id=user.id,
                subscription_id=event.subscription_id,
                event_type=event.event_type,
                event_date=event.event_date,
                sent_at=now,
            )
        )
    await db.commit()
    logger.info("Sent %d alert(s) for user", len(due))
    return due


async def run_all_alerts(db: AsyncSession, today: date | None = None) -> int:
    """Run the alert pass for every user. Returns the total events sent.

    The worker entrypoint calls this. A per-user failure is logged and skipped
    so one bad user can't stop the rest of the batch.
    """
    today = today or datetime.now(UTC).date()
    ses = SesClient.from_settings() if settings.ses_sender else None
    users = (await db.scalars(select(User))).all()

    total = 0
    for user in users:
        try:
            sent = await run_user_alerts(db, user, ses, today)
            total += len(sent)
        except Exception:
            logger.exception("Alert run failed for a user; continuing")
            await db.rollback()
    return total
