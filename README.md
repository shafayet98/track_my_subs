# track_my_subs

[![CI](https://github.com/shafayet98/track_my_subs/actions/workflows/ci.yml/badge.svg)](https://github.com/shafayet98/track_my_subs/actions/workflows/ci.yml)

**An agentic subscription tracker.** Connect your email, and an AI agent
(Claude Opus as the "brain", with a set of tools) scans your mailbox, figures out
which emails are subscription receipts, and extracts your recurring spend into a
clean dashboard — monthly spend charts and a card per subscription (total spent,
last month, next payment, overdue/missing payments).

> **Privacy first.** Gmail access is **read-only**, and we store **parsed facts
> only** — never raw email bodies. The agent reads a message in memory during a
> scan and discards it; only structured data (amounts, dates, merchant, a message
> id for dedup) is persisted. See [`.claude/rules/security.md`](.claude/rules/security.md).

---

## What it does

- **Connect email** — link a Gmail account via Google OAuth2 (`gmail.readonly`).
- **Agentic scan** — the agent walks candidate emails (Netflix, AWS, Vodafone, …),
  decides which are subscriptions, and records subscriptions + payment events.
- **Dashboard** — "this month vs last month" spend, a 12-month chart, and a card
  per subscription. Each card shows total spent, last month's spend, the next
  payment amount/date, and any missing/overdue payments.

## How the agent works

1. A cheap **heuristic search** narrows the mailbox to billing-signal candidates
   (subscription / receipt / invoice / renewal …) — using Gmail metadata, so no
   bodies are pulled just to triage.
2. A **manual agentic loop** drives Claude with **tool use**: the model reads a
   candidate's body in memory, classifies it, and calls tools to record a
   subscription or a payment. Tool executors are **tenant-scoped** to the
   scanning user, so the agent can't read or write across accounts.
3. The read side aggregates the recorded `subscriptions` + `payments` into the
   dashboard numbers.

Deep dive: [`docs/architecture.md`](docs/architecture.md). Agent internals:
[`.claude/skills/agent-tooling`](.claude/skills/).

## Tech stack

| Layer    | Choice                                                       |
| -------- | ------------------------------------------------------------ |
| Frontend | React + Vite + TypeScript, Recharts                          |
| Backend  | FastAPI (async Python 3.12), SQLAlchemy 2.0 async, Alembic   |
| Database | PostgreSQL                                                   |
| LLM      | Claude Opus 4.8 (`claude-opus-4-8`), Anthropic Python SDK    |
| Email    | Gmail API (Google OAuth2, read-only)                         |
| Auth     | Multi-user, JWT bearer tokens                                |
| Infra    | AWS via AWS CDK (Python) — ECS Fargate, RDS, S3 + CloudFront |
| CI/CD    | GitHub Actions (CI on PRs; CD auto-deploys on merge to main) |

## Architecture at a glance

```
Browser ──► CloudFront ──► S3 (React SPA)
   │
   └──────► ALB (HTTPS, api.shafcode.xyz) ──► FastAPI on ECS Fargate ──► RDS Postgres
                                                     │
                                                     └──► Gmail API + Anthropic API
```

The frontend talks only to the backend — never to Gmail or Anthropic directly.
All third-party traffic and secrets stay server-side.

## Getting started (local development)

**Prerequisites:** Python 3.12 + [`uv`](https://github.com/astral-sh/uv),
Node 20+, and a local Postgres (or SQLite for quick iteration).

```bash
# secrets
cp .env.example .env            # fill in your keys (see below)

# backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload     # http://localhost:8000

# frontend (in another shell)
cd frontend
npm install
npm run dev                               # http://localhost:5173
```

### Required secrets (`.env` — never commit)

| Variable | What it's for |
| --- | --- |
| `ANTHROPIC_API_KEY` | The LLM brain |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | Gmail OAuth app |
| `GOOGLE_OAUTH_REDIRECT_URI` | OAuth callback (`http://localhost:8000/api/accounts/gmail/callback` locally) |
| `DATABASE_URL` | Postgres connection string |
| `JWT_SECRET` | Signs auth tokens |
| `TOKEN_ENCRYPTION_KEY` | Fernet key — encrypts stored OAuth refresh tokens at rest |

`.env.example` holds placeholders only. To connect Gmail you'll need a Google
Cloud OAuth client with the `gmail.readonly` scope; while it's in "Testing" mode,
add yourself as a test user.

## Tests & checks

```bash
cd backend && uv run ruff check . && uv run pytest -q
cd frontend && npm run lint && npm run build
cd infra && uv run cdk synth          # if you touched infra
```

## Deployment

Infrastructure is **AWS CDK (Python)** under [`infra/`](infra/). Once deployed,
**CD is automatic**: merging to `main` triggers
[`.github/workflows/cd.yml`](.github/workflows/cd.yml), which authenticates via
**GitHub OIDC → an IAM role** (no stored keys), builds + pushes the API image,
`cdk deploy`s, runs migrations, and ships the SPA to S3 + CloudFront.

Full deploy runbook: [`infra/README.md`](infra/README.md).

## Contributing

See **[`contributor_guideline.md`](contributor_guideline.md)** for the full guide.
In short: work is branch-per-change with a PR into `main`; CI must pass and
[`.claude/progress.md`](.claude/progress.md) gets an entry before each PR.
The repo ships Claude Code slash commands that encode this flow:

- `/plan <task>` — write a plan under `docs/plans/` (no code).
- `/coding` — fresh `main` → branch → implement → tests → sub-agent review.
- `/cpr` — commit, push, open a PR against `main`.
- `/investigate <issue>` — read-only root-cause analysis.

Engineering rules live in [`.claude/rules/`](.claude/rules/); the build plan and
shipped log are in [`docs/roadmap.md`](docs/roadmap.md) and
[`.claude/progress.md`](.claude/progress.md).

## Project layout

```
track_my_subs/
├── backend/    # FastAPI app, the agent (loop/tools/prompts), integrations, models
├── frontend/   # React + Vite + TS SPA (typed API client, pages, charts)
├── infra/      # AWS CDK (Python) — network, data, ECR, backend, frontend, CI/CD
├── docs/       # architecture.md, roadmap.md, plans/
└── .claude/    # rules, skills, commands, progress log
```

## Status

The core product is built and deployed end-to-end (Phases 0–7): connect Gmail →
agentic scan → dashboard, running on AWS with automated CD. See
[`docs/roadmap.md`](docs/roadmap.md) for what's next.
