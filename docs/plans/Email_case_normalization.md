# Plan: Email case normalization (issue #34)

## Goal

Fix case-sensitive email handling in auth endpoints so that:
- Emails are stored in lowercase regardless of how the user types them.
- Login succeeds whether the user types `User@Example.com` or `user@example.com`.
- Registering an email that already exists in a different case is rejected with 409.

## Root cause

`RegisterRequest` and `LoginRequest` in `backend/app/schemas/auth.py` pass `email`
through as-typed. The DB lookup (`User.email == body.email`) is a literal string
comparison, so case variants bypass both the duplicate-check and the login lookup.

## Scope

- **In scope:** normalize email in `RegisterRequest` and `LoginRequest` schemas.
- **Out of scope:** backfilling existing stored emails; any other model field.

## Approach

Add a Pydantic v2 `field_validator("email", mode="after")` to both
`RegisterRequest` and `LoginRequest` that returns `value.lower()`. Pydantic's
`EmailStr` already validates format; the validator runs after that and lowercases
the result. Because the normalized value is set on `body.email` before any
DB interaction, no changes are needed in `auth.py`.

No migration is required — the schema change only affects new writes.

## Steps

1. In `backend/app/schemas/auth.py`:
   - Import `field_validator` from `pydantic`.
   - Add `@field_validator("email", mode="after") @classmethod def normalize_email(cls, v): return v.lower()` to `RegisterRequest`.
   - Add the same validator to `LoginRequest`.

2. In `backend/tests/test_auth.py`, add two tests:
   - `test_register_mixed_case_login_lowercase`: register `MixedCase@Example.com`, then login with `mixedcase@example.com` → 200.
   - `test_register_duplicate_different_case_conflicts`: register `User@Example.com`, then register `user@example.com` → 409.

3. Run `pytest backend/tests/test_auth.py` (then the full suite).

## Acceptance criteria

- `test_register_mixed_case_login_lowercase` passes.
- `test_register_duplicate_different_case_conflicts` passes.
- All existing auth tests still pass.
- Full test suite passes.
