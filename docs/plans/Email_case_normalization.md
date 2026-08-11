# Email Case Normalization

**Issue:** #34
**Branch:** `claude/email-case-normalization`
**Date:** 2026-08-11

## Goal

Fix case-sensitive email handling that allowed two accounts to share the
same email differing only by case, and that blocked logins when the case
used at login differed from registration.

## Scope

- **In scope:** normalize emails to lowercase at the input boundary;
  backfill existing stored emails via a data migration.
- **Out of scope:** collation changes, schema/index changes, frontend
  changes.

## Approach

Add a Pydantic `field_validator('email', mode='before')` to both
`RegisterRequest` and `LoginRequest` in `backend/app/schemas/auth.py`
that calls `.lower()`. `mode='before'` fires before `EmailStr` coercion,
so the normalized value is what gets stored and compared. The existing
case-sensitive DB unique index on `users.email` then effectively enforces
case-insensitive uniqueness with no schema change.

Add Alembic migration `0003_lowercase_emails` (data-only — no column or
constraint changes):

1. **Dedup:** For any rows whose lowercased email collides with another
   (possible because bug #34 allowed it), keep the oldest user
   (`ORDER BY created_at ASC`) and delete the rest via
   `ROW_NUMBER() OVER (PARTITION BY LOWER(email) ...)`. `ROW_NUMBER()` is
   available in SQLite ≥ 3.25 (Python 3.12 bundles 3.39+) and all
   supported PostgreSQL versions.
2. **Normalize:** `UPDATE users SET email = LOWER(email)` on the
   now-collision-free rows.

## Steps

1. Add `field_validator` to `RegisterRequest` and `LoginRequest` in
   `backend/app/schemas/auth.py`.
2. Write migration `backend/alembic/versions/0003_lowercase_emails.py`.
3. Add three tests to `backend/tests/test_auth.py`:
   - mixed-case register → lowercase login → 200
   - lowercase register → uppercase login → 200 (symmetry)
   - duplicate-different-case register → 409
4. Run `uv run pytest` to confirm all tests pass.

## Acceptance Criteria

- `POST /auth/register` with `User@Example.com` stores `user@example.com`.
- `POST /auth/login` with `user@example.com` succeeds after registering
  `User@Example.com`.
- `POST /auth/register` with `user@example.com` after `User@Example.com`
  returns 409.
- All existing tests continue to pass.
