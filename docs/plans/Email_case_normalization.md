# Email Case Normalization

## Goal

Fix email case-sensitivity bugs in register and login. Registering with
`User@Example.com` and logging in with `user@example.com` currently fails
(401), and registering `user@example.com` after `User@Example.com` silently
creates a second account instead of returning 409.

## Scope

- **In scope:** normalize email to lowercase at the Pydantic schema boundary.
- **Out of scope:** DB migration for existing rows (development stage; no
  production users with mixed-case emails). If the app is ever deployed with
  existing mixed-case data, a one-time `UPDATE users SET email = LOWER(email)`
  migration must run before deploying this fix.

## Approach

Add `@field_validator("email", mode="before")` + `@classmethod` to both
`RegisterRequest` and `LoginRequest` in `backend/app/schemas/auth.py`. The
`mode="before"` ensures the lowercased string is what Pydantic's `EmailStr`
validates and what reaches the DB query/insert — no router changes needed.

## Steps

1. Edit `backend/app/schemas/auth.py` — add `normalize_email` validator to
   `RegisterRequest` and `LoginRequest`.
2. Add three tests to `backend/tests/test_auth.py`:
   - `test_email_case_insensitive_login`
   - `test_email_case_duplicate_rejected`
   - `test_email_stored_lowercase`

## Acceptance Criteria

- Register `User@Example.com` → login `user@example.com` → 200.
- Register `User@Example.com` → register `user@example.com` → 409.
- `/api/auth/me` returns email in lowercase regardless of registration case.
- Full test suite passes.
