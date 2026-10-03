# Fix email case-sensitivity on register/login

## Goal

Normalize email addresses to lowercase at the input boundary so that:
- Login succeeds regardless of the case used at registration time.
- Registering an email that already exists under a different case returns `409`.

Fixes Issue #34.

## Scope

- **In scope:** `backend/app/schemas/auth.py` — add Pydantic v2 `field_validator` on `email` in both `RegisterRequest` and `LoginRequest`.
- **Out of scope:** DB migration (no existing data to backfill; project is pre-production), frontend changes, other endpoints.

## Approach

Add a `@field_validator("email", mode="before")` to both request schemas. Running in `mode="before"` means the value is lowercased before Pydantic's `EmailStr` validation fires, so the stored value and both DB lookups always use the normalized form.

The validator must guard against non-string input (Pydantic v2 `mode="before"` runs before coercion, so `None` or an integer can arrive). An unguarded `.lower()` on `None` raises `AttributeError` which Pydantic does **not** catch — this would return 500 instead of 422. Use an `isinstance` guard:

```python
@field_validator("email", mode="before")
@classmethod
def normalize_email(cls, v: object) -> object:
    if isinstance(v, str):
        return v.lower()
    return v  # let EmailStr validation reject non-strings with a 422
```

Key files:
- `backend/app/schemas/auth.py` — the only change needed.
- `backend/tests/test_auth.py` — three new test cases.

No changes to `backend/app/api/auth.py` are required because the router already uses `body.email` which will be normalized by the schema.

## Steps

1. In `backend/app/schemas/auth.py`, import `field_validator` from pydantic and add `normalize_email` validators to `RegisterRequest` and `LoginRequest` using the `isinstance` guard above.
2. In `backend/tests/test_auth.py`, add:
   - `test_login_case_insensitive`: register with `User@Example.com`, log in with `user@example.com` — expect 200. Also hit `GET /auth/me` and assert `email == "user@example.com"` (verifies stored value is lowercased).
   - `test_register_duplicate_email_different_case`: register `User@Example.com`, then register `user@example.com` — expect 409.
   - `test_login_uppercase_email`: register `user@example.com`, log in with `USER@EXAMPLE.COM` — expect 200.
3. Run the full test suite (`cd backend && uv run pytest`).

## Acceptance criteria

- `POST /auth/register` with `User@Example.com` stores `user@example.com` (confirmed via `/auth/me`).
- `POST /auth/login` with `user@example.com` after registering `User@Example.com` returns 200.
- `POST /auth/login` with `USER@EXAMPLE.COM` after registering `user@example.com` returns 200.
- `POST /auth/register` with `user@example.com` after registering `User@Example.com` returns 409.
- Non-string email (e.g. `null`) returns 422 not 500.
- Full test suite passes (no regressions).
