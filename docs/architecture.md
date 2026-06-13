# Architecture — track_my_subs

This document describes the full system: the agent design, services, data model,
API surface, and the local→AWS path. Read `CLAUDE.md` first for the high-level
picture and conventions.

## 1. System overview

```
┌─────────────┐        ┌──────────────────────────────────────────────┐
│  React SPA  │        │                 FastAPI backend                │
│ (Vite + TS) │ HTTPS  │                                                │
│             ├───────▶│  /api/auth        /api/accounts                 │
│  Dashboard  │  JWT   │  /api/scans       /api/dashboard                │
│  Charts     │◀───────┤                                                 │
└─────────────┘        │   ┌────────────┐   ┌──────────────────────┐    │
                       │   │  Services  │   │   Agent (LLM brain)  │    │
                       │   │ dashboard  │   │  loop + tools +      │    │
                       │   │ aggregation│   │  Claude Opus 4.8     │    │
                       │   └─────┬──────┘   └─────────┬────────────┘    │
                       │         │                    │ tool calls      │
                       │         ▼                    ▼                 │
                       │   ┌──────────┐    ┌────────────────────────┐  │
                       │   │ Postgres │    │  Integrations          │  │
                       │   │ (parsed  │    │  • Gmail API (OAuth2)  │  │
                       │   │  data)   │    │  • Anthropic SDK       │  │
                       │   └──────────┘    └────────────────────────┘  │
                       └──────────────────────────────────────────────┘
```

Key principles:

- **The frontend never touches Gmail or Anthropic directly.** All third-party
  access is server-side, so tokens and the API key never reach the browser.
- **We persist only structured facts** the agent extracts (subscriptions,
  payments). Raw email bodies are fetched, used in-memory during a scan, and
  discarded. This minimizes the privacy/storage footprint.
- **Multi-tenant from day one.** Every row that holds user data is scoped by
  `user_id`, and every query filters on the authenticated user.

## 2. The Agent (LLM brain + tools)

This is the heart of the system. The agent is a deliberate, tool-using loop with
Claude Opus 4.8 as the reasoning engine. We use a **custom agentic loop** (not a
framework) so we control gating, logging, and cost.

### 2.1 Why an agent, not a regex pipeline

Subscription emails are wildly inconsistent across merchants (receipts,
"your payment is due", renewal notices, price-change notices, failed-payment
alerts). A model that can read an email and reason about *what kind of event it
represents* generalizes far better than per-merchant parsers. The agent decides:
"is this a subscription?", "is this a charge, a renewal notice, or a failed
payment?", "what's the amount, currency, and date?".

### 2.2 Hybrid pre-filter (cost control)

We don't feed the whole mailbox to the LLM. The flow is:

1. **Heuristic narrowing (no LLM):** the Gmail integration runs targeted
   searches — queries like `subscription OR receipt OR invoice OR "payment
   received" OR "your plan"`, plus known-merchant senders — to produce a
   candidate set of message IDs.
2. **Agentic classification + extraction (LLM):** the agent pulls candidates,
   reads them, and records structured data via tools.

This keeps token spend proportional to *candidate* emails, not the whole inbox.

### 2.3 The loop

Implemented in `backend/app/agent/loop.py`. Manual agentic loop (see the
Anthropic tool-use pattern):

```
messages = [ system: <agent instructions>, user: <scan task + candidate summary> ]
while True:
    resp = anthropic.messages.create(
        model="claude-opus-4-8",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        tools=TOOL_SCHEMAS,
        messages=messages,
    )
    if resp.stop_reason == "end_turn":
        break
    if resp.stop_reason == "refusal":
        handle_refusal(resp); break
    # execute each tool_use block, append tool_result, continue
```

We check `stop_reason` before reading content, append the full assistant
`content` (preserving `tool_use` blocks), and return one `tool_result` per
`tool_use` id. A `max_iterations` cap prevents runaway loops.

### 2.4 Tools

Each tool is a typed Python function plus a JSON schema. Tools are the agent's
only way to affect the world — the harness executes them, so we can validate,
log, and gate every action.

| Tool                    | Purpose                                                       | Side effects |
| ----------------------- | ------------------------------------------------------------- | ------------ |
| `list_candidate_emails` | Return candidate email IDs + subjects/senders for the scan.   | Read-only    |
| `get_email`             | Fetch one email's headers + plaintext body for inspection.    | Read-only    |
| `upsert_subscription`   | Create/update a subscription (merchant, cycle, amount, etc.). | Write        |
| `record_payment`        | Record a payment event (amount, date, status, source email).  | Write        |
| `flag_missing_payment`  | Flag an expected-but-missing or overdue payment.              | Write        |
| `finish_scan`           | End the scan with a short summary of what was found.          | Write        |

Tool schemas live in `backend/app/agent/tools.py`; their executors are scoped to
the current `user_id` and `scan_run_id` so the agent cannot write across tenants.
Read-only tools (`list_candidate_emails`, `get_email`) are safe to parallelize;
write tools are serialized. See `.claude/commands/new-tool.md` to add one.

### 2.5 Prompts

The system prompt (`backend/app/agent/prompts.py`) defines the agent's job,
the meaning of each subscription/payment field, how to infer billing cycles, and
how to handle ambiguous emails (prefer recording with lower confidence over
dropping). Keep it stable — it's the cacheable prefix for prompt caching.

### 2.6 Scans are background jobs

A scan can take minutes. The API kicks off a scan asynchronously and returns a
`scan_run_id`; the frontend polls `/api/scans/{id}` for status. Locally this runs
as a FastAPI background task; on AWS it becomes a worker (see §6).

## 3. Data model

PostgreSQL. All user-data tables carry `user_id` and are filtered per request.

```
users(id, email UNIQUE, name, created_at)

email_accounts(
  id, user_id → users,
  provider,                      -- "gmail"
  email_address,
  oauth_refresh_token_encrypted, -- encrypted at rest (TOKEN_ENCRYPTION_KEY)
  last_synced_at, created_at)

subscriptions(
  id, user_id → users,
  merchant_name,                 -- "Netflix", "AWS", "Stan"
  category,                      -- "streaming", "cloud", "music", ...
  billing_cycle,                 -- "monthly" | "annual" | "weekly" | "unknown"
  amount, currency,              -- expected recurring amount
  status,                        -- "active" | "cancelled" | "unknown"
  next_payment_date,             -- inferred next charge date
  confidence,                    -- agent's confidence 0..1
  created_at, updated_at)

payments(
  id, subscription_id → subscriptions, user_id → users,
  amount, currency,
  status,                        -- "paid" | "upcoming" | "missing" | "overdue"
  occurred_on,                   -- charge/expected date
  source_message_id,             -- Gmail message id (provenance, not body)
  created_at)

scan_runs(
  id, user_id → users,
  status,                        -- "running" | "succeeded" | "failed"
  started_at, finished_at,
  emails_scanned, subscriptions_found, summary)
```

We store `source_message_id` (the Gmail id) for provenance/dedup, **not** the
email body.

### 3.1 Dashboard queries (in `services/dashboard.py`)

- **Monthly spend chart:** `SUM(amount)` over `payments` where `status='paid'`,
  grouped by `date_trunc('month', occurred_on)`, last 12 months.
- **This month vs last month:** two windowed sums over `payments`.
- **Per-subscription card:**
  - total spent → `SUM(amount)` of paid payments for the subscription
  - last month spend → paid payments in the previous calendar month
  - next payment → `subscriptions.next_payment_date` + expected `amount`
  - missing/overdue → `payments` with `status in ('missing','overdue')`, plus
    the overdue total.

## 4. API surface

All endpoints under `/api`, JWT-authenticated except auth itself.

| Method | Path                          | Description                                  |
| ------ | ----------------------------- | -------------------------------------------- |
| POST   | `/api/auth/register`          | Create account.                              |
| POST   | `/api/auth/login`             | Get JWT.                                      |
| GET    | `/api/accounts`               | List connected email accounts.               |
| GET    | `/api/accounts/gmail/connect` | Start Google OAuth (returns consent URL).    |
| GET    | `/api/accounts/gmail/callback`| OAuth callback; stores encrypted token.      |
| POST   | `/api/scans`                  | Start a scan; returns `scan_run_id`.         |
| GET    | `/api/scans/{id}`             | Scan status + summary.                        |
| GET    | `/api/dashboard/summary`      | Charts data (monthly, this vs last month).   |
| GET    | `/api/subscriptions`          | Subscription cards.                          |
| GET    | `/api/subscriptions/{id}`     | Detail: totals, next payment, overdue, etc.  |

## 5. Frontend

React + Vite + TypeScript. Pages: **ConnectAccount** (OAuth kickoff + scan
trigger), **Dashboard** (spend charts + subscription card grid), and
**SubscriptionDetail** (the per-card drill-down). Recharts renders the charts. A
thin typed API client in `src/api/` wraps fetch with the JWT. No third-party SDKs
in the browser.

## 6. Local → AWS path

**Local:** run a locally-installed Postgres (no Docker — e.g. Homebrew
`postgresql@16`), or SQLite for quick iteration; backend and frontend run via
their dev servers. This is the primary target until the app works end to end.

**AWS (later, via AWS CDK in Python, in `infra/`):**

- Frontend → S3 + CloudFront.
- Backend API → ECS Fargate (or Lambda + API Gateway) behind an ALB.
- Scan workers → a separate Fargate service or SQS-triggered Lambda, since scans
  are long-running.
- Database → RDS PostgreSQL.
- Secrets → AWS Secrets Manager (`ANTHROPIC_API_KEY`, Google OAuth creds, JWT
  secret, token-encryption key).

CDK is chosen over Terraform to keep IaC in Python alongside the backend.

## 7. Security & privacy notes

- Gmail scope is **read-only** (`gmail.readonly`).
- OAuth refresh tokens are encrypted at rest; the API key and tokens live only
  server-side.
- Only parsed facts are stored; raw bodies are never persisted.
- All data access is tenant-scoped by `user_id`.

See `.claude/rules/security.md` for the enforceable rules.
