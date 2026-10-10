# Email case normalization

## Goal

Fix issue #34: authentication treats email addresses case-sensitively. Registering
`User@Example.com` and `user@example.com` creates two accounts; login with a
different case than was used at registration fails with 401.

## Scope

**In scope:**
- `backend/app/schemas/auth.py` — add `field_validator` to lowercase `email` on
  both `RegisterRequest` and `LoginRequest`.
- `backend/tests/test_auth.py` — add two tests covering the fixed behavior.

**Out of scope:**
- No DB migration. The fix normalizes all new writes; existing mixed-case rows
  are a known deferred risk called out as acceptable for this task.
- No changes to `backend/app/api/auth.py` — the boundary fix is sufficient.

## Approach

Add a Pydantic v2 `field_validator` with `mode="before"` on the `email` field in
both request schemas. `mode="before"` runs before `EmailStr` validation so the
raw string is lowercased first.

## Steps

1. Save this plan.
2. Add `field_validator` to `RegisterRequest` and `LoginRequest`.
3. Add two tests: cross-case login succeeds, cross-case duplicate registration
   returns 409.
4. Run the full test suite.
5. Independent verification.
6. Update `.claude/progress.md`.
7. Commit, push, and open a PR.

## Acceptance criteria

- Registering `User@Example.com` then logging in as `user@example.com` returns 200.
- Registering `user@example.com` after `User@Example.com` returns 409.
- Full test suite passes.
