"""Normalise stored emails to lowercase (data-only, no schema change).

Revision ID: 0003_lowercase_emails
Revises: 0002_renewal_trial_alerts
Create Date: 2026-08-11

Two-phase upgrade:
1. Dedup: where two rows share the same lowercased email (allowed by the
   old case-sensitive register check), keep the oldest (by created_at)
   and delete the rest using ROW_NUMBER().
2. Normalise: LOWER() every remaining stored email so future
   case-insensitive lookups work without a collation change.

Downgrade is a no-op — lowercasing is lossy and original casing cannot
be recovered.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_lowercase_emails"
down_revision: str | None = "0002_renewal_trial_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Step 1: remove duplicate-cased rows that would collide after LOWER().
    # ROW_NUMBER() is available in SQLite >= 3.25 (Python 3.12 bundles 3.39+)
    # and in all supported PostgreSQL versions.
    op.execute(
        sa.text(
            """
            DELETE FROM users
            WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY LOWER(email)
                               ORDER BY created_at ASC
                           ) AS rn
                    FROM users
                ) sub
                WHERE rn = 1
            )
            """
        )
    )
    # Step 2: normalise every remaining email to lowercase.
    op.execute(sa.text("UPDATE users SET email = LOWER(email)"))


def downgrade() -> None:
    pass
