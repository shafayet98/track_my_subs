# Email case-insensitive auth

**Fixes:** issue #34

## Goal

Emails are currently stored and compared as-typed, so `User@Example.com` and
`user@example.com` are treated as different identities. This breaks login after
mixed-case registration and allows duplicate accounts that differ only by case.

## Scope

- **In:** normalise email to lowercase at the Pydantic schema boundary for
  register and login; add an Alembic migration to lowercase any existing stored
  emails.
- **Out:** no changes to the router logic or the unique-constraint definition
  (the existing `UNIQUE` on `users.email` is sufficient once all values are
  lowercase).

## Approach

Add a `field_validator("email", mode="before")` to both `RegisterRequest` and
`LoginRequest` in `backend/app/schemas/auth.py` that returns
`v.lower() if isinstance(v, str) else v`. `EmailStr` already validates format;
we normalise before it validates.

The router code (`backend/app/api/auth.py`) uses `body.email` for both the
uniqueness check and the DB lookup, so it automatically benefits from the
normalised value with no changes needed there.

A new Alembic migration (`0003_lowercase_emails.py`) normalises any existing
rows:
- First checks whether any case-duplicate pairs exist (i.e. two rows with the
  same `LOWER(email)`). If any are found the migration aborts with a clear
  error message so a human can resolve the collision manually before running
  it again.
- If no collisions exist, runs `UPDATE users SET email = LOWER(email)`.
- `downgrade()` is a no-op (`pass`) since original casing is not retained.

## Steps

1. In `backend/app/schemas/auth.py`:
   - Import `field_validator` from `pydantic`.
   - Add `@field_validator("email", mode="before") def normalise_email` to
     both `RegisterRequest` and `LoginRequest` returning
     `v.lower() if isinstance(v, str) else v`.
2. Add `backend/alembic/versions/0003_lowercase_emails.py`:
   - `revision = "0003_lowercase_emails"`, revises `0002_renewal_trial_alerts`.
   - In `upgrade()`: check for case-duplicate rows; raise `SystemExit` with a
     descriptive message if found; otherwise
     `op.execute("UPDATE users SET email = LOWER(email)")`.
   - `downgrade()`: `pass`.
3. In `backend/tests/test_auth.py` add four tests:
   - `test_register_mixed_case_login_lowercase` — register `User@Example.com`,
     login with `user@example.com`, expect 200.
   - `test_register_duplicate_different_case_conflicts` — register
     `User@Example.com`, register again with `user@example.com`, expect 409.
   - `test_login_uppercase_email_ok` — register `lower@example.com`, login with
     `LOWER@EXAMPLE.COM`, expect 200.
   - `test_register_mixed_case_stored_lowercase` — register `User@Example.com`,
     call `/me`, assert `body["email"] == "user@example.com"`.

## Acceptance criteria

- Register with any case → stored email is lowercase (verified by `/me`).
- Login with any casing of a registered email succeeds.
- Second registration with a different casing of an existing email returns 409.
- Migration detects case-duplicate rows and aborts instead of silently violating
  the unique constraint.
- Full test suite passes.
