# Fix email case-sensitivity on register/login (Issue #34)

## Goal

Normalize email addresses to lowercase at the schema boundary so that
authentication is case-insensitive: `User@Example.com` and `user@example.com`
are treated as the same identity.

## Scope

**In scope:**
- Lowercase normalization of `email` on `RegisterRequest` and `LoginRequest`
- Tests covering: mixed-case register → lowercase login succeeds; duplicate
  registration with different case → 409

**Out of scope:**
- Database migration (the existing unique index on `users.email` is sufficient
  once all writes go through the normalized schema)
- Changes to the auth router (`auth.py`) — normalization at the schema layer
  keeps the router clean
- Existing production users with stored mixed-case emails (new project, no
  production data at risk)

## Approach

Add a Pydantic v2 `@field_validator("email", mode="before")` to both
`RegisterRequest` and `LoginRequest` in `backend/app/schemas/auth.py` that
returns `v.lower()`. `mode="before"` ensures the value is lowercased before
`EmailStr` validation runs, so format checks still apply to the normalized form.

No changes to `auth.py`, no migration, no new models.

## Steps

1. Create branch `claude/fix-email-case-sensitivity`
2. Edit `backend/app/schemas/auth.py`: import `field_validator`, add
   `normalize_email` validator to `RegisterRequest` and `LoginRequest`
3. Add two tests to `backend/tests/test_auth.py`:
   - `test_login_mixed_case_email_matches`
   - `test_register_duplicate_different_case_conflicts`
4. Run `uv run pytest` — all tests must pass
5. Run `uv run ruff check` — must be clean
6. Update `.claude/progress.md`, commit, push, open PR

## Acceptance criteria

- Registering `User@Example.com` then logging in with `user@example.com` → 200
- Registering `user@example.com` then registering `User@Example.com` → 409
- All existing tests still pass
- `ruff check` + `ruff format --check` clean
