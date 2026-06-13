"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-13
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# GUID columns are stored as CHAR(36) (see app.models.types.GUID).
GUID = sa.String(36)


def _timestamps() -> list[sa.Column]:
    now = sa.func.now()
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "email_accounts",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="gmail"),
        sa.Column("email_address", sa.String(320), nullable=False),
        sa.Column("oauth_refresh_token_encrypted", sa.String(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_email_accounts_user_id", "email_accounts", ["user_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("merchant_name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("billing_cycle", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("next_payment_date", sa.Date(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    op.create_table(
        "payments",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "subscription_id",
            GUID,
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="paid"),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("source_message_id", sa.String(128), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_subscription_id", "payments", ["subscription_id"])
    op.create_index("ix_payments_occurred_on", "payments", ["occurred_on"])
    op.create_index("ix_payments_source_message_id", "payments", ["source_message_id"])

    op.create_table(
        "scan_runs",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("emails_scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subscriptions_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.String(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_scan_runs_user_id", "scan_runs", ["user_id"])


def downgrade() -> None:
    op.drop_table("scan_runs")
    op.drop_table("payments")
    op.drop_table("subscriptions")
    op.drop_table("email_accounts")
    op.drop_table("users")
