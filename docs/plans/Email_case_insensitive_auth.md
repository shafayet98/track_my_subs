# Email case-insensitive authentication

## Goal

Fix issue #34: email authentication is case-sensitive, allowing duplicate accounts
differing only by case and causing login failures when case doesn't match registration.

## Scope

**In scope:**
- Normalize email to lowercase at the schema/validation boundary (register + login).
- Reject duplicate registrations where the email differs only by case (409).
- Tests: mixed-case register → lowercase login succeeds; duplicate-with-different-case → 409.

**Out of scope:**
- No DB migration needed — fix is at the input boundary; existing data is unchanged.
- No changes to the `User` model or DB schema.
- No changes to any endpoint logic in `auth.py` (the fix lands entirely in the schema).

## Approach

Add a `field_validator` with `mode='after'` on the `email` field in both
`RegisterRequest` and `LoginRequest` in `backend/app/schemas/auth.py`.

Using `mode='after'` means pydantic's `EmailStr` validates format first, then
our validator lowercases the result. This ensures the stored value and both
lookups always use the normalized (lowercased) form — no endpoint logic changes
required.

## Files touched

- `backend/app/schemas/auth.py` — add `field_validator` to `RegisterRequest` and `LoginRequest`
- `backend/tests/test_auth.py` — add case-insensitivity tests

## Steps

1. Edit `backend/app/schemas/auth.py`:
   - Import `field_validator` from pydantic.
   - Add `@field_validator('email', mode='after') @classmethod def normalize_email(cls, v): return v.lower()`
     to both `RegisterRequest` and `LoginRequest`.

2. Add tests in `backend/tests/test_auth.py`:
   - `test_login_case_insensitive`: register `User@Example.com`, login with
     `user@example.com` → 200 with token.
   - `test_register_duplicate_different_case`: register `User@Example.com`, then
     register `user@example.com` → 409 conflict.

3. Run the full test suite (`pytest backend/`).

## Acceptance criteria

- `test_login_case_insensitive` passes.
- `test_register_duplicate_different_case` passes.
- All existing auth tests still pass.
- Full suite is green.
