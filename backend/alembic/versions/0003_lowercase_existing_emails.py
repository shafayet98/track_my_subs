"""Lowercase existing users.email values

Revision ID: 0003_lowercase_existing_emails
Revises: 0002_renewal_trial_alerts
Create Date: 2026-08-21

Normalises any mixed-case email addresses stored before the schema-level
field_validator was added (fix for #34). The UPDATE is a no-op if all
existing rows are already lowercase. If two rows differ only by case the
unique constraint will surface a violation — resolve manually before
running this migration.

Downgrade: no-op. The original mixed-case values are not recoverable
without a backup.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_lowercase_existing_emails"
down_revision: str | None = "0002_renewal_trial_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE users SET email = lower(email)")


def downgrade() -> None:
    pass
