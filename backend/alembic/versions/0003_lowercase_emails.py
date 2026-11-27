"""lowercase all stored email addresses

Revision ID: 0003_lowercase_emails
Revises: 0002_renewal_trial_alerts
Create Date: 2026-11-27

Normalises existing rows so they match what the new field_validator produces.
If two rows would collide after lowercasing (a data anomaly that should not
exist on a healthy install), the UNIQUE constraint surfaces it.
"""

from alembic import op

revision: str = "0003_lowercase_emails"
down_revision: str | None = "0002_renewal_trial_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE users SET email = LOWER(email)")


def downgrade() -> None:
    pass  # Case normalisation is irreversible without the original values
