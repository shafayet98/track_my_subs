"""Lowercase all existing user emails

Revision ID: 0003_lowercase_emails
Revises: 0002_renewal_trial_alerts
Create Date: 2026-11-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_lowercase_emails"
down_revision: str = "0002_renewal_trial_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    # Abort if any case-duplicate pairs exist — the unique constraint would
    # fail and a human must resolve them first.
    result = conn.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT LOWER(email) FROM users GROUP BY LOWER(email) HAVING COUNT(*) > 1"
        ") AS dupes"
    )
    count = result.scalar()
    if count:
        raise SystemExit(
            f"Migration 0003 aborted: {count} case-duplicate email(s) found in users table. "
            "Resolve the duplicates manually (keep the desired account per canonical address, "
            "delete the others) before running this migration."
        )
    conn.execute("UPDATE users SET email = LOWER(email)")


def downgrade() -> None:
    # Original casing is not retained — downgrade is a no-op.
    pass
