# Email Case Normalization

## Goal

Fix issue #34: email addresses are compared case-sensitively on register and login,
allowing duplicate accounts and broken login with different-case input.

## Scope

- **In scope:** `backend/app/schemas/auth.py` — normalize email at the input boundary.
- **Out of scope:** DB migration for pre-existing mixed-case accounts; other email fields
  (e.g. `email_address` from Google OAuth in `accounts.py` are OAuth-sourced, not user
  input).

## Approach

Add a Pydantic v2 `field_validator('email', mode='before')` to both `RegisterRequest`
and `LoginRequest` in `backend/app/schemas/auth.py` that lowercases the value before
`EmailStr` validates format. No router changes are needed — once the schema normalizes,
the existing comparisons and storage in `auth.py` automatically use the lowercase form.

## Steps

1. In `backend/app/schemas/auth.py`, import `field_validator` and add a
   `normalize_email` class method validator (mode='before') to `RegisterRequest`
   and `LoginRequest`.
2. In `backend/tests/test_auth.py`, add tests:
   - Register mixed-case → login with lowercase succeeds (200).
   - Register duplicate with different case → 409.
3. Run full test suite to confirm no regressions.

## Acceptance criteria

- Login with a different-case variant of the registered email succeeds.
- Registering an email that already exists in a different case returns 409.
- All existing auth tests continue to pass.
