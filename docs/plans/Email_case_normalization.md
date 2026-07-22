# Email Case Normalization

## Goal

Fix issue #34: email addresses are treated case-sensitively during register and
login, allowing duplicate accounts and causing login failures when case differs.

## Scope

- **In scope:** Normalize email to lowercase in the Pydantic schemas
  (`RegisterRequest`, `LoginRequest`), add tests for the new behaviour.
- **Out of scope:** Database migration (no stored emails need retroactive
  normalization; this is a dev environment with fresh data). No changes to
  `auth.py` lookups or the `User` model are needed because once the schema
  normalizes, `body.email` is always lowercase and the `==` comparison works.

## Approach

Add a Pydantic v2 `field_validator` (`mode="before"`) on the `email` field of
both `RegisterRequest` and `LoginRequest` in `backend/app/schemas/auth.py`:

```python
@field_validator("email", mode="before")
@classmethod
def normalize_email(cls, v: str) -> str:
    return v.strip().lower()
```

`mode="before"` runs before `EmailStr` validation, so the lowercased value is
what Pydantic stores and what the endpoint sees.

`UserOut` deliberately does NOT lowercase — it reflects what is already stored
in the database (which will be lowercase due to normalization on write).

## Steps

1. Add `field_validator` import and the validator to `RegisterRequest` and
   `LoginRequest` in `backend/app/schemas/auth.py`.
2. Add tests in `backend/tests/test_auth.py`:
   - Register with mixed-case email → login with lowercase succeeds.
   - Registering the same email with different case returns `409`.

## Acceptance criteria

- `POST /auth/register` with `User@Example.com`, then `POST /auth/login` with
  `user@example.com` → `200`.
- `POST /auth/register` with `User@Example.com`, then `POST /auth/register`
  with `user@example.com` → `409`.
- Full test suite passes.
