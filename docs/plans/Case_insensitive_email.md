# Case-insensitive email on register/login (issue #34)

## Goal

Normalize email addresses to lowercase at the input boundary so that
`User@Example.com` and `user@example.com` are treated as the same account.

## Scope

- **In scope:** `backend/app/schemas/auth.py` (add a field validator),
  `backend/tests/test_auth.py` (add two new test cases).
- **Out of scope:** database migration (no existing data needs backfilling for
  tests; a one-time migration for production data is a follow-up), frontend
  changes (inputs are `type="email"` which browsers already lowercase on many
  platforms, and normalization now happens server-side in any case).

## Approach

Add a Pydantic v2 `@field_validator("email", mode="after")` on both
`RegisterRequest` and `LoginRequest` in `schemas/auth.py` that calls
`.lower()` on the validated email string before it is returned.
This is the right layer: it normalizes before the value is used in any
DB query or stored.

No changes to `api/auth.py` are needed — the endpoint already uses
`body.email`, which will now always be lowercase.

## Steps

1. Add `field_validator` import to `schemas/auth.py`.
2. Add `@field_validator("email", mode="after")` + `classmethod` to both
   `RegisterRequest` and `LoginRequest`.
3. Add two tests to `tests/test_auth.py`:
   - Register mixed-case → login lowercase → succeeds.
   - Register mixed-case → register different-case → 409.
4. Run the full test suite (`uv run pytest`).

## Acceptance criteria

- Registering `User@Example.com` and then logging in with `user@example.com`
  returns a valid token.
- Registering `user@example.com` after `User@Example.com` returns 409.
- Full test suite passes.
