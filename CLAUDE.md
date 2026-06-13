# track_my_subs

An agentic subscription tracker. Users connect their email account; an AI agent
(Claude Opus as the "brain", with a set of tools) scans the mailbox, identifies
subscription-related emails, and extracts structured spending data. The web app
surfaces this as a dashboard: monthly spend charts and per-subscription cards
(total spent, last month, next payment, overdue/missing payments).

This file is the entry point for anyone (human or agent) working in this repo.
Read it first, then `docs/architecture.md` for the deep dive and
`docs/roadmap.md` for the phased build plan we follow.

## What we're building (product)

- **Connect email** — user links a Gmail account via Google OAuth2 (read-only).
- **Agentic scan** — the agent walks candidate emails (Netflix, AWS, Stan, etc.),
  decides which are subscriptions, and records subscriptions + payment events.
- **Dashboard** — charts for "spend this month vs last month" and a card per
  subscription. Clicking a card shows: total spent, next payment amount + date,
  last month's spend, and any missing/overdue payments.

## Tech stack

| Layer      | Choice                                                          |
| ---------- | -------------------------------------------------------------- |
| Frontend   | React + Vite + TypeScript, Recharts for charts                 |
| Backend    | FastAPI (async Python 3.12)                                    |
| Database   | PostgreSQL via SQLAlchemy (async) + Alembic migrations         |
| LLM        | Claude Opus 4.8 (`claude-opus-4-8`), Anthropic Python SDK      |
| Agent      | Custom agentic loop with tool use (see `docs/architecture.md`) |
| Email      | Gmail API (Google OAuth2, `gmail.readonly`)                    |
| Auth       | Multi-user, JWT bearer tokens                                  |
| Infra      | Local first (Docker Compose); AWS via AWS CDK (Python) later   |

## Repository layout (target)

```
track_my_subs/
├── CLAUDE.md                 # this file
├── docs/
│   └── architecture.md       # full architecture & data model
├── .claude/
│   ├── settings.local.json   # local permissions
│   ├── progress.md           # running PR-by-PR log (update before every PR)
│   ├── rules/                # always-applicable engineering rules
│   ├── skills/               # task-specific playbooks
│   └── commands/             # slash commands
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── api/              # routers (auth, accounts, dashboard, scans)
│   │   ├── agent/            # the LLM agent: loop, tools, prompts
│   │   ├── integrations/     # gmail client, anthropic client
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # business logic (dashboard aggregation, etc.)
│   │   └── core/             # config, db session, security
│   ├── alembic/              # migrations
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── pages/            # Dashboard, ConnectAccount, SubscriptionDetail
│   │   ├── components/       # cards, charts
│   │   ├── api/              # typed API client
│   │   └── main.tsx
│   └── package.json
└── infra/                    # AWS CDK app (Python) — added later
```

> No Docker for local dev — run Postgres locally (e.g. Homebrew `postgresql@16`)
> or use SQLite for quick iteration.

## Local development (target commands)

```bash
# one-time
cp .env.example .env          # fill in secrets (see below)
# start a local Postgres and create the DB, e.g.:
#   brew services start postgresql@16 && createdb track_my_subs

# backend
cd backend && uv sync && uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# frontend
cd frontend && npm install && npm run dev
```

## Required secrets (`.env`, never commit)

- `ANTHROPIC_API_KEY` — provided by the owner when needed.
- `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` — Gmail OAuth app.
- `DATABASE_URL` — Postgres connection string.
- `JWT_SECRET` — signing key for auth tokens.
- `TOKEN_ENCRYPTION_KEY` — encrypts stored OAuth refresh tokens at rest.

## Conventions (the short version)

- **LLM model:** always `claude-opus-4-8` with `thinking={"type": "adaptive"}`.
  Never hardcode another model or use deprecated `budget_tokens`. See
  `.claude/rules/llm-usage.md`.
- **We store parsed data only**, never raw email bodies. See
  `.claude/rules/security.md`.
- **Before starting new work**, write a short plan under `docs/plans/` (named
  after the task, e.g. `Verify_harden_auth.md`), then code. See
  `.claude/rules/planning.md`.
- **Before opening a PR**, update `.claude/progress.md` with what the PR does.
  See `.claude/rules/git-workflow.md`.
- Backend is async end-to-end (async SQLAlchemy, async Anthropic client where it
  helps). Frontend talks to the backend only — never to Gmail or Anthropic
  directly.

## Where to look

- Agent loop, tools, and prompts → `docs/architecture.md` §Agent + `backend/app/agent/`
- Adding a new agent tool → `.claude/commands/new-tool.md`
- Gmail sync details → `.claude/skills/gmail-sync/`
- Data model + dashboard queries → `docs/architecture.md` §Data model
