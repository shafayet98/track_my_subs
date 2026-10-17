# Email case normalization

## Goal

Fix GitHub issue #34: email addresses are treated case-sensitively on register and
login, allowing duplicate accounts and breaking login when case differs from
registration.

## Scope

- **In scope:** normalize email to lowercase at the Pydantic schema layer for
  `RegisterRequest` and `LoginRequest`.
- **Out of scope:** DB-level `citext` column or functional index (not needed for
  the current single entry point; deferred to a future hardening pass if needed).
- **Existing data note:** the dev DB is clean. A production deployment against a
  DB that already has mixed-case rows would need a one-time `UPDATE users SET
  email = LOWER(email)` before this change goes live.

## Approach

Add a `@field_validator("email", mode="after")` classmethod to both
`RegisterRequest` and `LoginRequest` in `backend/app/schemas/auth.py` that
returns `v.lower()`. Pydantic v2 runs this after `EmailStr` validation (which
returns a plain `str`), so the downstream router always receives a normalized
value. No changes are needed in `api/auth.py` or the `User` model.

## Steps

1. Add `field_validator` to the imports in `backend/app/schemas/auth.py`.
2. Add a `normalize_email` validator on `RegisterRequest.email`.
3. Add the same validator on `LoginRequest.email`.
4. Add tests to `backend/tests/test_auth.py`:
   - Register mixed-case → login all-lowercase succeeds (200).
   - Register mixed-case → register again with different case returns 409.
   - `/me` returns the lowercased email after mixed-case registration.

## Acceptance criteria

- All existing auth tests pass unchanged.
- `POST /auth/register` with `User@Example.com` stores `user@example.com`.
- `POST /auth/login` with `user@example.com` succeeds after registering
  `User@Example.com`.
- `POST /auth/register` with `user@example.com` after `User@Example.com` returns
  409.
