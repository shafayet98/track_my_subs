# Plan — Verify & harden auth (Phase 2)

Branch: `feat/verify-harden-auth`

## Goal

Replace the ad-hoc verification done during Phase 1 with a committed, repeatable
test suite that locks in the auth and **tenant-isolation** guarantees every later
phase (Gmail, agent, dashboard) depends on. If the tests surface bugs, fix them.

## Scope

In scope:
- A `pytest` test harness for the backend (async, SQLite, no network).
- Tests for auth: register, login (+ wrong password), JWT `/me`, auth guards.
- Tests for tenant isolation: a user cannot read another user's accounts,
  subscriptions, or scan runs.
- Fixtures: isolated test DB per test, async HTTP client, helpers to create
  users and seed rows.

Out of scope:
- Gmail OAuth, the agent, dashboard aggregation (later phases).
- CI configuration (can come later); for now the suite runs locally.

## Approach

- **HTTP client:** `httpx.AsyncClient` over `ASGITransport(app=app)` so tests run
  in one event loop alongside the async DB (cleaner than the sync `TestClient`
  for async sessions). `pytest-asyncio` in `auto` mode.
- **Test DB:** in-memory SQLite (`sqlite+aiosqlite`) with `StaticPool` +
  `check_same_thread=False` so one shared connection serves the app and the test.
  Create the schema with `Base.metadata.create_all` per test (fast; Alembic is
  already verified separately). Function-scoped engine → full isolation per test.
- **Dependency override:** `app.dependency_overrides[get_db]` yields sessions
  from a sessionmaker bound to the test engine. A `session` fixture exposes the
  same factory so tests can seed rows (e.g. a subscription owned by user A)
  directly.
- **Settings:** set `TOKEN_ENCRYPTION_KEY` / `JWT_SECRET` for the test process in
  `conftest.py` before importing the app, so security helpers work.

### Files

```
backend/tests/__init__.py
backend/tests/conftest.py        # engine, session factory, get_db override, client, user helpers
backend/tests/test_auth.py       # register / login / me / guards / duplicate email
backend/tests/test_tenant_isolation.py  # cross-tenant read attempts
```

## Steps

1. Add `backend/tests/` with `conftest.py` (fixtures above).
2. `test_auth.py`: health; register→201+token; duplicate email→409; login→200;
   wrong password→401; `/me` with token→200; `/me` no token / bad token→401.
3. `test_tenant_isolation.py`: create users A and B; seed a subscription + a
   scan_run + an email_account for A directly via the session; assert B's
   `GET /subscriptions` excludes A's, `GET /subscriptions/{A_id}`→404,
   `GET /scans/{A_id}`→404, and `GET /accounts` returns only B's.
4. Run `uv run pytest` and `uv run ruff check`; fix anything that surfaces.
5. Update `.claude/progress.md`; open PR `feat/verify-harden-auth` → `main`.

## Acceptance criteria

- `uv run pytest` is green (auth + tenant-isolation suites).
- `uv run ruff check` is clean.
- No network calls in tests; DB is ephemeral SQLite.
