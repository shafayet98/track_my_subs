# Email case normalization

## Goal

Fix case-sensitive email handling so `User@Example.com` and `user@example.com`
are treated as the same account. Closes issue #34.

## Scope

- **In:** Pydantic field validator on `RegisterRequest` and `LoginRequest` to
  lowercase emails; Alembic migration to normalize existing stored emails.
- **Out:** No router changes, no model changes, no frontend changes.

## Approach

Add `@field_validator("email", mode="before")` to both request schemas in
`backend/app/schemas/auth.py`. Running `v.lower()` before `EmailStr` validation
ensures every email that enters the system is already lowercase — the existing
router comparisons (`User.email == body.email`) work correctly with no changes.

Also add migration `0003_lowercase_emails` to run `UPDATE users SET email =
LOWER(email)` so any pre-existing mixed-case rows match the new normalized form.

## Steps

1. Add `field_validator` to `RegisterRequest` and `LoginRequest` in
   `backend/app/schemas/auth.py`.
2. Add `backend/alembic/versions/0003_lowercase_emails.py`.
3. Add two tests to `backend/tests/test_auth.py`:
   - Register mixed-case → login lowercase succeeds (200 + token).
   - Register mixed-case → register same email lowercase → 409.
4. Run `uv run pytest` — all tests must pass.
5. Update `.claude/progress.md`.
6. Commit and push; open PR against `main`.

## Acceptance criteria

- Registering `User@Example.com` then logging in with `user@example.com` returns
  200 + a valid token.
- Registering `user@example.com` after `User@Example.com` returns 409.
- Full test suite passes.
- Plan saved under `docs/plans/`.
- `.claude/progress.md` updated.
- PR open against `main`.
