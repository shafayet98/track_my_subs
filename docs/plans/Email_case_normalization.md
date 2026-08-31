# Email Case Normalization

## Goal

Fix issue #34: email addresses are treated case-sensitively on register/login.
Registering with `User@Example.com` and logging in with `user@example.com`
fails with 401, and registering a duplicate email with different case creates
a second account instead of returning 409.

## Scope

- Normalize email to lowercase at the Pydantic schema boundary.
- No DB migration needed (unique constraint already exists).
- No changes to `api/auth.py` or the model layer.

## Out of scope

- Backfilling any existing mixed-case rows (dev-stage; no prod data).
- Changes to the Gmail / OAuth email handling.

## Approach

Add a `_EmailNormalMixin(BaseModel)` in `backend/app/schemas/auth.py` with a
`field_validator("email", mode="before")` that lowercases the full email string
(with an `isinstance(v, str)` guard to let Pydantic produce clean validation
errors for non-string inputs). Both `RegisterRequest` and `LoginRequest`
inherit from it.

Pydantic's `EmailStr` already lowercases the domain part (RFC 5321), but not
the local part. The `mode="before"` validator runs first and normalizes the
entire string.

## Steps

1. Update `backend/app/schemas/auth.py` — add `_EmailNormalMixin` and wire it
   into `RegisterRequest` and `LoginRequest`.
2. Update `backend/tests/test_auth.py` — add two tests:
   - `test_register_mixed_case_login_lowercase`: register with `User@Example.com`,
     login with `user@example.com`, expect 200 + token.
   - `test_register_duplicate_different_case_conflicts`: register `User@Example.com`,
     then register `user@example.com`, expect 409.
3. Run full test suite: `cd backend && uv run pytest tests/`.

## Acceptance criteria

- Login with lowercased email after registering with mixed-case email returns
  200 with a token.
- Registering an email that already exists in a different case returns 409.
- All pre-existing tests continue to pass.
- No DB migration is required.
