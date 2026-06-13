# Progress log

A running, PR-by-PR record of what has been built. **Before opening any PR,
add an entry here describing what that PR does** (see
`.claude/rules/git-workflow.md`). Newest entries at the top.

The format for each entry:

```
## <date> — <PR title> (#<PR number or branch>)

**What:** one-paragraph summary of the change.
**Why:** the motivation / which part of the roadmap it advances.
**Touches:** key files/areas.
**Follow-ups:** anything deferred.
```

---

## 2026-06-13 — The agent (feat/agent)

**What:** Implemented Phase 4 — the agentic scan. New `agent/` package:
`prompts.py` (stable, cacheable system prompt), `tools.py` (`TOOL_SCHEMAS` in
deterministic order + a `ScanContext` and tenant-scoped executors for
`list_candidate_emails`, `get_email`, `upsert_subscription`, `record_payment`,
`flag_missing_payment`, `finish_scan`), and `loop.py` (`run_agent_loop` — the
manual loop checking `stop_reason`, preserving full assistant `content`, one
`tool_result` per `tool_use`, `MAX_ITERATIONS=25`; plus `run_scan_job`, the
background orchestration: decrypt token → Gmail candidate search → loop → update
`scan_run` + `last_synced_at`). Added `integrations/anthropic_client.py`
(`AsyncAnthropic` wrapper). Wired `POST /api/scans` to create a `scan_run` and
schedule the job (202; 400 without a connected Gmail account). LLM call uses
`claude-opus-4-8` + `thinking={"type":"adaptive"}` + `max_tokens=16000`, no
sampling params (per `.claude/rules/llm-usage.md`). Write executors filter on
`user_id` and reject cross-tenant `subscription_id`; payments dedup on
`source_message_id`; no email bodies persisted. Tests (Anthropic + Gmail faked,
no network): `test_agent_tools.py` (upsert/update, payment dedup, tenant
rejection, bad-date, get_email counting, finish_scan), `test_agent_loop.py`
(completes on finish/end_turn, refusal without raising, `MAX_ITERATIONS` cap,
payment written + scoped), `test_scans.py` (202 + run created + job scheduled,
400 without account, tenant-scoped GET). Plan: `docs/plans/The_agent.md`.
**Why:** Phase 4 of the roadmap — the LLM brain that turns candidate emails into
`subscriptions` + `payments`, the data Phase 5's dashboard aggregates.
**Touches:** `backend/app/agent/**` (new), `backend/app/integrations/anthropic_client.py`
(new), `backend/app/api/scans.py`, `backend/tests/test_agent_tools.py` +
`test_agent_loop.py` + `test_scans.py` (new), `docs/plans/The_agent.md`.
**Verified:** `uv run pytest` → 33 passed; `uv run ruff check` + `ruff format
--check` clean; `alembic upgrade head` + `alembic check` drift-free (no schema
change). No live LLM/Gmail network in tests.
**Follow-ups:** Phase 5 — `services/dashboard.py` aggregation + real
`/api/dashboard/summary` and subscription-detail endpoints. The scan runs as a
FastAPI background task locally; AWS (Phase 7) moves it to a worker.

## 2026-06-13 — Gmail integration (feat/gmail-integration)

**What:** Implemented Phase 3. New `integrations/gmail.py`: OAuth helpers
(`build_authorization_url` — pure consent-URL building with `access_type=offline`
+ `prompt=consent`; `exchange_code` — code→refresh-token + mailbox address via
`getProfile`) and a read-only `GmailClient` with `search_candidates` (heuristic
`CANDIDATE_QUERY`, Gmail `format=metadata` so no bodies are pulled to triage) and
`get_email` (full fetch → prefer `text/plain`, else HTML stripped via
BeautifulSoup, length-capped at `MAX_BODY_CHARS`). Wired the accounts API:
`GET /accounts/gmail/connect` returns the consent URL; `GET /accounts/gmail/callback`
verifies a signed `state`, exchanges the code off the event loop
(`run_in_threadpool`), and upserts the account with the **encrypted** refresh
token. Added `create_oauth_state`/`verify_oauth_state` to `core/security.py`
(short-lived purpose-scoped JWT, since the callback is unauthenticated). Tests:
`test_gmail.py` (candidate shape, plaintext/HTML extraction, length cap, empty
inbox) and `test_accounts_oauth.py` (consent URL scope/params, callback
encryption + upsert/reconnect, bad-state 400, auth + missing-param guards), Gmail
boundary faked — no network. Plan: `docs/plans/Gmail_integration.md`.
**Why:** Phase 3 of the roadmap — gives the backend read-only Gmail access
(connect + candidate search + single-email fetch), the two read-only operations
the Phase 4 agent consumes as tools.
**Touches:** `backend/app/integrations/gmail.py` (new), `backend/app/api/accounts.py`,
`backend/app/core/security.py`, `backend/tests/test_gmail.py` +
`test_accounts_oauth.py` (new), `backend/tests/conftest.py`,
`docs/plans/Gmail_integration.md`.
**Verified:** `uv run pytest` → 20 passed; `uv run ruff check` + `ruff format
--check` clean. No live Gmail network in tests (faked service / patched
`exchange_code`).
**Follow-ups:** Phase 4 — the agent loop + tools wrapping `search_candidates` /
`get_email`, scoped per `user_id`/`scan_run_id`. The `last_synced_at` column is
set during scans (Phase 4), not connect.

## 2026-06-13 — CI pipeline (chore/ci)

**What:** Added `.github/workflows/ci.yml` — a hermetic backend job (uv install →
`ruff check` → `ruff format --check` → `pytest` → `alembic upgrade head` +
`alembic check`) on PRs and pushes to `main`. No secrets, SQLite only. Enabling
the format check required normalizing existing files with `ruff format`; enabling
the drift check required the initial migration to use the models' custom `GUID`
type instead of `sa.String(36)` (so `alembic check` is drift-free). Plan:
`docs/plans/CI_pipeline.md`.
**Why:** Enforce the PR-per-phase workflow and raise the quality floor before the
codebase grows (Gmail, agent, dashboard). Chose option A — SQLite now, add a
Postgres CI job at Phase 5 when Postgres-specific SQL arrives.
**Touches:** `.github/workflows/ci.yml`, `docs/plans/CI_pipeline.md`,
`backend/alembic/versions/0001_initial.py`, formatting across `backend/**`.
**Verified:** all four CI steps pass locally (ruff check/format, 8 tests, migrations
+ drift).
**Follow-ups:** After merge, enable branch protection requiring the CI check on
`main`. Phase 3 — Gmail integration.

## 2026-06-13 — Verify & harden auth: test suite (feat/verify-harden-auth)

**What:** Added a committed `pytest` suite for the backend — fixtures
(`tests/conftest.py`: ephemeral in-memory SQLite, ASGI `httpx.AsyncClient`,
`get_db` override, `make_user` helper), `test_auth.py` (register/login/`me`,
wrong-password 401, unknown-user 401, duplicate-email 409, short-password 422,
auth guards), and `test_tenant_isolation.py` (user B cannot read user A's
subscriptions/scans/accounts; A sees only its own). Introduced the plan-first
rule (`.claude/rules/planning.md`) and the first plan doc
(`docs/plans/Verify_harden_auth.md`).
**Why:** Phase 2 of the roadmap — lock in the auth + tenant-isolation guarantees
every later phase depends on, with a repeatable suite instead of ad-hoc checks.
**Touches:** `backend/tests/**`, `docs/plans/Verify_harden_auth.md`,
`.claude/rules/planning.md`, `CLAUDE.md`.
**Verified:** `uv run pytest` → 8 passed; `uv run ruff check` clean.
**Follow-ups:** Phase 3 — Gmail integration (needs Google OAuth credentials).

## 2026-06-13 — Backend skeleton (chore/scaffolding)

**What:** FastAPI app with `/api/health`; core config/db/security (JWT, bcrypt,
Fernet OAuth-token encryption); SQLAlchemy models (users, email_accounts,
subscriptions, payments, scan_runs) with portable UUID PKs; Alembic + initial
migration `0001_initial`; working auth (register/login/me); tenant-scoped stub
routers for accounts/scans/dashboard (read endpoints work, OAuth/scan/aggregation
return 501). Added `docs/roadmap.md` as the phased plan. Removed Docker; local
dev uses local Postgres or SQLite.
**Why:** Phase 1 of the roadmap — the foundation every later phase builds on.
**Touches:** `backend/**`, `docs/roadmap.md`, `CLAUDE.md`, `docs/architecture.md`.
**Verified:** `uv sync`, `alembic upgrade head` on SQLite, app boots, and
register→login→`/auth/me` (+ wrong-password 401, duplicate-email 409, auth-guard
401) all pass; `ruff check` clean. Two fixes during verification: added
`pydantic[email]` (EmailStr needs `email-validator`) and replaced unmaintained
`passlib` with the `bcrypt` library directly (passlib 1.7.4 breaks on bcrypt 4.x).
**Follow-ups:** Phase 2 — add a committed `pytest` suite (the verification above
was ad-hoc) before moving to the Gmail integration.

## 2026-06-13 — Project scaffolding & docs (initial)

**What:** Established the project's documentation and agent-config foundation:
`CLAUDE.md`, `docs/architecture.md`, and the `.claude/` tree (rules, skills,
commands, this progress log, local permissions).
**Why:** Lock in the architecture and conventions (agent + tools + Claude Opus
brain, FastAPI backend, React frontend, Gmail OAuth, multi-user, parsed-data-only
storage) before writing application code.
**Touches:** `CLAUDE.md`, `docs/architecture.md`, `.claude/**`.
**Follow-ups:** Scaffold the backend (FastAPI app, models, Alembic), the agent
loop + tools, the Gmail integration, the React app, and `docker-compose.yml`.

---

## Roadmap

The forward-looking plan lives in **`docs/roadmap.md`** (phases, deliverables,
acceptance criteria). This log records what actually shipped, newest first.
