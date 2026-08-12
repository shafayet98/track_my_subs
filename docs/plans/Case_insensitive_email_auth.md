# Case-insensitive email auth

## Goal

Fix issue #34: email addresses are compared case-sensitively on register and
login, allowing duplicate accounts and causing 401s when the user types a
different case than they registered with.

## Scope

**In scope:** Normalize email in `RegisterRequest` and `LoginRequest` Pydantic
schemas; add covering tests.

**Out of scope:** Database migration (no production data to backfill), changes
to `auth.py` endpoint logic, DB-level case-insensitive index.

## Approach

Add a Pydantic v2 `field_validator` with `mode="after"` on the `email` field
in both request schemas. Using `mode="after"` means `EmailStr` validates the
format first; then we lowercase the already-validated string. This makes
`body.email` always lowercase by the time any endpoint code touches it — no
changes to `auth.py` are required.

Key files:
- `backend/app/schemas/auth.py` — add `field_validator` import and
  `normalize_email` validator on `RegisterRequest` and `LoginRequest`.
- `backend/tests/test_auth.py` — add two new tests.

## Steps

1. Edit `backend/app/schemas/auth.py` — add `field_validator` and
   `normalize_email` to both request models.
2. Add tests:
   - `test_register_mixed_case_login_lowercase_succeeds`
   - `test_register_duplicate_different_case_conflicts`
3. Run full test suite.

## Acceptance criteria

- `User@Example.com` registered; `user@example.com` login → 200.
- `dup@Example.com` registered; re-register as `DUP@example.com` → 409.
- All existing tests pass.
- No DB migration required.
