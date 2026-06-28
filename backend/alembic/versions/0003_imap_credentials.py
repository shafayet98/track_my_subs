"""IMAP App Password credentials on email_accounts

Revision ID: 0003_imap_credentials
Revises: 0002_renewal_trial_alerts
Create Date: 2026-06-28

Additive only (two nullable columns) so it is backward-compatible: existing
Gmail/OAuth accounts keep working with both columns NULL.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_imap_credentials"
down_revision: str | None = "0002_renewal_trial_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("email_accounts", sa.Column("imap_host", sa.String(255), nullable=True))
    op.add_column("email_accounts", sa.Column("app_password_encrypted", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("email_accounts", "app_password_encrypted")
    op.drop_column("email_accounts", "imap_host")
