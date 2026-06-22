"""Worker delivery tests: detection → send → dedup. SES mocked (no network)."""

from datetime import date

from sqlalchemy import select

from app.models import Notification, Subscription, User
from app.services.notifications import run_user_alerts, update_preferences

TODAY = date(2026, 6, 22)


class FakeSes:
    """Records sends instead of calling SES."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_email(self, *, to: str, subject: str, text_body: str, html_body: str) -> str:
        self.sent.append({"to": to, "subject": subject, "text": text_body, "html": html_body})
        return "fake-message-id"


async def _seed(session, make_user, **sub_kwargs) -> User:
    u = await make_user(sub_kwargs.pop("email", "user@example.com"))
    user = await session.get(User, u["user_id"])
    session.add(
        Subscription(
            user_id=user.id,
            merchant_name=sub_kwargs.pop("merchant_name", "Netflix"),
            billing_cycle="monthly",
            amount=sub_kwargs.pop("amount", 15.99),
            currency=sub_kwargs.pop("currency", "USD"),
            status=sub_kwargs.pop("status", "active"),
            **sub_kwargs,
        )
    )
    await session.commit()
    return user


async def test_renewal_sends_one_email_and_records_dedup(session, make_user):
    user = await _seed(session, make_user, next_payment_date=date(2026, 6, 24))
    ses = FakeSes()

    sent = await run_user_alerts(session, user, ses, TODAY)

    assert len(sent) == 1
    assert len(ses.sent) == 1
    assert ses.sent[0]["to"] == user.email
    assert "Netflix" in ses.sent[0]["text"]

    notes = (
        await session.scalars(select(Notification).where(Notification.user_id == user.id))
    ).all()
    assert len(notes) == 1
    assert notes[0].event_type == "renewal"
    assert notes[0].event_date == date(2026, 6, 24)


async def test_second_run_does_not_resend(session, make_user):
    user = await _seed(session, make_user, next_payment_date=date(2026, 6, 24))
    ses = FakeSes()

    await run_user_alerts(session, user, ses, TODAY)
    again = await run_user_alerts(session, user, ses, TODAY)

    assert again == []
    assert len(ses.sent) == 1


async def test_trial_conversion_fires(session, make_user):
    user = await _seed(session, make_user, merchant_name="Notion", trial_end_date=date(2026, 6, 23))
    ses = FakeSes()

    sent = await run_user_alerts(session, user, ses, TODAY)

    assert len(sent) == 1
    assert sent[0].event_type == "trial_conversion"
    assert "Notion" in ses.sent[0]["text"]


async def test_opt_out_suppresses_send(session, make_user):
    user = await _seed(session, make_user, next_payment_date=date(2026, 6, 24))
    await update_preferences(session, user.id, renewals_enabled=False)
    ses = FakeSes()

    sent = await run_user_alerts(session, user, ses, TODAY)

    assert sent == []
    assert ses.sent == []


async def test_no_sender_configured_skips_without_recording(session, make_user):
    user = await _seed(session, make_user, next_payment_date=date(2026, 6, 24))

    sent = await run_user_alerts(session, user, None, TODAY)

    assert sent == []
    notes = (
        await session.scalars(select(Notification).where(Notification.user_id == user.id))
    ).all()
    assert notes == []
