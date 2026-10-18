"""Normalize existing user emails to lowercase

Revision ID: 0003_normalize_email_case
Revises: 0002_renewal_trial_alerts
Create Date: 2026-10-18

Data-only migration: lowercases any existing email values so they match the
new Pydantic-level normalization introduced in the same release.
"""

from alembic import op

revision = "0003_normalize_email_case"
down_revision = "0002_renewal_trial_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE users SET email = lower(email)")


def downgrade() -> None:
    # Lowercasing is not reversible.
    pass
