# Email case normalization (issue #34)

## Goal
Fix case-sensitive email handling in auth so register and login are
case-insensitive. Prevents duplicate accounts and ensures login succeeds
regardless of the case used at registration.

## Scope
- Normalize emails to lowercase at the Pydantic schema boundary.
- Include a data migration that lowercases any existing email rows.
- Out of scope: DB-level safeguard (citext / functional index) — a follow-up
  hardening task if needed.

## Approach
Add a `field_validator('email', mode='after')` that calls `.lower()` in both
`RegisterRequest` and `LoginRequest` in `backend/app/schemas/auth.py`. Because
the stored value and all lookups will now always be lowercase, the existing
case-sensitive DB unique index continues to work correctly.

Add an Alembic migration `0003_normalize_email_case.py` that runs:
```sql
UPDATE users SET email = lower(email);
```
so existing rows are normalized on deploy (safe for the current dev-only state).

## Steps
1. Edit `backend/app/schemas/auth.py` — add `field_validator` to both request
   schemas.
2. Add `backend/alembic/versions/0003_normalize_email_case.py`.
3. Add tests to `backend/tests/test_auth.py`:
   - Register mixed-case → login lowercase succeeds.
   - Register `User@Example.com` → register `user@example.com` → 409 conflict.
   - Login with mixed-case for a lowercase-registered account succeeds.

## Acceptance criteria
- Register `User@Example.com`, login `user@example.com` → 200 with token.
- Register `User@Example.com`, register `user@example.com` → 409.
- Full test suite passes.
