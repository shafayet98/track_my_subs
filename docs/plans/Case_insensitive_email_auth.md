# Case-insensitive email auth (fixes #34)

## Goal

Authentication currently treats email addresses case-sensitively:
`backend/app/api/auth.py` compares `User.email == body.email` directly, and
the email is stored exactly as typed. This means logging in with a different
case than used at registration fails with `401`, and registering the same
email in a different case creates a second account instead of being rejected
with `409`.

## Scope

- Normalize email to lowercase at the schema boundary so both registration
  storage and login/duplicate lookups use the normalized form.
- Out of scope: no DB migration (existing rows aren't backfilled), no change
  to the `users.email` unique index (already case-sensitive at the DB level,
  but normalization at the boundary means all *new* writes are lowercase, so
  the unique constraint is effectively case-insensitive going forward).

## Approach

Add a Pydantic `field_validator` on the `email` field in both
`RegisterRequest` and `LoginRequest` (`backend/app/schemas/auth.py`) that
lowercases the value. Since `auth.py` (`register`/`login`) already reads
`body.email` for both the DB query and the stored value, no changes are
needed there — normalization at the schema layer covers both paths.

`UserOut.email` is left as-is (just reflects whatever is stored, which will
be lowercase after this change).

## Steps

1. Add a `field_validator` to `RegisterRequest.email` and `LoginRequest.email`
   in `backend/app/schemas/auth.py` that lowercases the input.
2. Add tests in `backend/tests/test_auth.py`:
   - Register with mixed-case email, login with lowercase succeeds.
   - Register with mixed-case email, then register again with a different
     case of the same email returns `409`.
3. Run the full backend test suite.

## Acceptance criteria

- Registering `User@Example.com` then logging in with `user@example.com`
  succeeds.
- Registering `user@example.com` after `User@Example.com` was already
  registered returns `409`.
- Full test suite passes.
