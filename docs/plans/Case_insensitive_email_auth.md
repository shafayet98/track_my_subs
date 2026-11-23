# Case-insensitive email on register/login

## Goal

Fix issue #34: authentication is case-sensitive on email, allowing two accounts
for `User@Example.com` and `user@example.com`, and causing login failures when
the case differs from registration.

## Scope

- **In scope:** normalize email to lowercase at the Pydantic schema layer for
  `RegisterRequest` and `LoginRequest`.
- **Out of scope:** migrating existing stored emails (no existing production data;
  the issue says no migration needed), changes to any other endpoint.

## Approach

Add a Pydantic `field_validator("email", mode="before")` on both
`RegisterRequest` and `LoginRequest` in `backend/app/schemas/auth.py` that
calls `.lower()`. Using `mode="before"` runs before the `EmailStr` validation so
the stored and compared value is always lowercase.

The existing `unique=True` constraint on `User.email` already rejects duplicates
at the DB level. After normalization, `User@Example.com` and `user@example.com`
both become `user@example.com`, so the existing DB constraint catches the
duplicate — no migration or query changes needed.

The DB query in `auth.py` (`User.email == body.email`) is then correct because
both sides are lowercase.

## Steps

1. Add `field_validator("email", mode="before")` to `RegisterRequest` and
   `LoginRequest` in `backend/app/schemas/auth.py`.
2. Add two tests to `backend/tests/test_auth.py`:
   - Register with `User@Example.com`, log in with `user@example.com` → 200.
   - Register `dup@Example.com`, re-register `DUP@example.com` → 409.
3. Run the full test suite (`pytest`).

## Acceptance criteria

- Existing tests in `test_auth.py` all pass.
- New test: register mixed-case → login lowercase → 200 with token.
- New test: register mixed-case → register different-case → 409.
- Full test suite passes.
