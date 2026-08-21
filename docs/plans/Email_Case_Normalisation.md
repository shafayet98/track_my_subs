# Plan: Email Case Normalisation (issue #34)

## Goal
Fix case-sensitive email handling on register and login so `User@Example.com` and
`user@example.com` are treated as the same address.

## Scope
- **In scope:** normalise email to lowercase at the Pydantic schema boundary
  (`backend/app/schemas/auth.py`); add an Alembic migration to lowercase any
  existing rows; add tests.
- **Out of scope:** DB unique index hardening (`citext`/functional index) — noted
  as a follow-up.

## Approach
1. **Schema fix:** Add `field_validator("email", mode="before")` to both
   `RegisterRequest` and `LoginRequest` that calls `v.lower()`. Using
   `mode="before"` means the lowercase value flows into the `EmailStr` validator,
   so the stored + queried value is always lowercase. No changes to the API layer.

2. **Migration:** Add `backend/alembic/versions/0003_lowercase_existing_emails.py`
   with `UPDATE users SET email = lower(email)`. This safely handles any existing
   mixed-case rows. Pre-existing collisions are extremely unlikely; the migration
   will surface a unique-constraint violation if they exist (resolve manually).

## Key files
- `backend/app/schemas/auth.py` — add the validators
- `backend/alembic/versions/0003_lowercase_existing_emails.py` — new migration
- `backend/tests/test_auth.py` — add 4 new test cases

## Steps
1. Edit `backend/app/schemas/auth.py`: import `field_validator`, add
   `normalise_email` validators to `RegisterRequest` and `LoginRequest`.
2. Add migration `0003_lowercase_existing_emails.py` (`down_revision = "0002_renewal_trial_alerts"`).
3. Add 4 tests to `backend/tests/test_auth.py`:
   - register mixed-case → login lowercase → 200
   - register lowercase → login uppercase → 200
   - register mixed-case → register lowercase duplicate → 409
   - register mixed-case → GET /auth/me → email is lowercase
4. Run `uv run pytest`.
5. Update `.claude/progress.md`.
6. Commit, push, open PR.

## Acceptance criteria
- `POST /auth/register` with `User@Example.com` stores `user@example.com`.
- `POST /auth/login` with any case variant returns 200.
- Duplicate registration in a different case returns 409.
- `GET /auth/me` returns the normalised lowercase email.
- Migration lowercases any existing rows.
- Full test suite passes.

## Follow-ups (deferred)
- Functional unique index `CREATE UNIQUE INDEX ON users (lower(email))` as
  belt-and-suspenders against out-of-band inserts.
