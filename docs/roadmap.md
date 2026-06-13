# Roadmap — track_my_subs

The forward-looking build plan. Each phase is a PR (or a small set of PRs) with
explicit deliverables and acceptance criteria. This is the plan we follow; the
backward-looking record of what shipped lives in `.claude/progress.md`.

Conventions: every PR updates `progress.md` first (`.claude/rules/git-workflow.md`),
respects `.claude/rules/*`, and uses Claude Opus 4.8 per `.claude/rules/llm-usage.md`.

Legend: ✅ done · 🔜 next · ⬜ planned

---

## Phase 0 — Scaffolding & docs ✅

**Deliverables:** `CLAUDE.md`, `docs/architecture.md`, `docs/roadmap.md`, the
`.claude/` tree (rules, skills, commands, progress log, permissions), `.gitignore`,
`.env.example`. Git initialized, GitHub remote wired.

**Done when:** docs describe the system and conventions; repo is ready to receive
code. → First push (`chore/scaffolding`).

## Phase 1 — Backend skeleton ✅

**Deliverables:** FastAPI app + `/api/health`; core config/db/security (JWT,
bcrypt, Fernet token encryption); SQLAlchemy models (users, email_accounts,
subscriptions, payments, scan_runs); Alembic + initial migration; working
register/login/me; tenant-scoped stub routers for accounts/scans/dashboard.

**Done when:** `uv sync` installs cleanly, `alembic upgrade head` creates the
schema, the app boots, and register→login→`/auth/me` round-trips.

## Phase 2 — Verify & harden auth 🔜

**Deliverables:** confirm migration + app boot locally (local Postgres or SQLite);
a `pytest` suite covering register/login/JWT and tenant isolation; ruff clean;
fix anything the verification surfaces.

**Done when:** `uv run pytest` is green and `uv run ruff check` passes.

## Phase 3 — Gmail integration ✅

**Skill:** `gmail-sync`. **Deliverables:** Google OAuth connect + callback;
encrypted refresh-token storage; `integrations/gmail.py` with the heuristic
candidate search and `get_email` (HTML→plaintext, length-capped); accounts API
wired to real flow.

**Done when:** a user can connect a Gmail account; candidate search + single-email
fetch work against fixtures in tests (no live network in CI).

## Phase 4 — The agent ✅

**Skill:** `agent-tooling`. **Deliverables:** `agent/tools.py` (schemas +
tenant-scoped executors), `agent/prompts.py` (stable system prompt),
`agent/loop.py` (manual agentic loop with `MAX_ITERATIONS`),
`integrations/anthropic_client.py`; `POST /api/scans` runs the scan as a
background job; `GET /api/scans/{id}` reports status.

**Done when:** a scan over fixture emails populates `subscriptions` + `payments`
correctly scoped to the user; the loop terminates on `end_turn`, on the iteration
cap, and on a refusal; all LLM/Gmail boundaries mocked in tests.

## Phase 5 — Dashboard aggregation ✅

**Deliverables:** `services/dashboard.py` (monthly spend, this-vs-last-month,
per-subscription totals/next-payment/overdue); `GET /api/dashboard/summary` and
the subscription-detail endpoint return real data.

**Done when:** endpoints return correct aggregates over seeded payments, verified
by tests.

## Phase 6 — Frontend ⬜

**Deliverables:** React + Vite + TS app; typed API client; pages —
ConnectAccount (OAuth kickoff + "Scan now" + poll), Dashboard (Recharts spend
chart + subscription card grid), SubscriptionDetail (totals, next payment,
overdue).

**Done when:** end-to-end locally — connect Gmail → scan → see charts and cards.

## Phase 7 — AWS deployment (CDK, Python) ⬜

**Deliverables:** `infra/` CDK app — S3 + CloudFront (SPA), Fargate (API) + a
separate scan worker, RDS Postgres, Secrets Manager for all secrets.

**Done when:** the stack deploys and the app runs in AWS.

---

## Cross-cutting / later

- Scheduled re-scans (currently manual "Scan now" only).
- Multi-provider email (Outlook/IMAP) behind the same integration interface.
- Currency normalization across merchants.
- Notifications for upcoming/overdue payments.
