"""renewal & trial alerts: trial_end_date + notification tables

Revision ID: 0002_renewal_trial_alerts
Revises: 0001_initial
Create Date: 2026-06-21

Additive only (a new column + two new tables) so it is backward-compatible: the
service rolls onto the new image, then this runs (see contributor_guideline §7).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.types import GUID as _GUID

revision: str = "0002_renewal_trial_alerts"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUID = _GUID()


def _timestamps() -> list[sa.Column]:
    now = sa.func.now()
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
    ]


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("trial_end_date", sa.Date(), nullable=True))

    op.create_table(
        "notifications",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "subscription_id",
            GUID,
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "subscription_id", "event_type", "event_date", name="uq_notification_event"
        ),
        *_timestamps(),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_subscription_id", "notifications", ["subscription_id"])

    op.create_table(
        "notification_preferences",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("renewals_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "trial_conversions_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "missed_payments_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("lead_time_days", sa.Integer(), nullable=False, server_default="3"),
        *_timestamps(),
    )
    op.create_index(
        "ix_notification_preferences_user_id",
        "notification_preferences",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_table("notifications")
    op.drop_column("subscriptions", "trial_end_date")
