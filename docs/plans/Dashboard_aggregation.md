# Plan: Dashboard aggregation (Phase 5)

## Goal

Turn the `subscriptions` + `payments` the agent writes (Phase 4) into the
aggregates the frontend (Phase 6) renders: a monthly-spend chart, this-vs-last
month totals, and per-subscription cards (total spent, last month, next payment,
overdue/missing). This makes `GET /api/dashboard/summary` and the subscription
endpoints return real data instead of the `501` stub.

## Scope

- `services/dashboard.py` — the aggregation logic (new service layer).
- `schemas/dashboard.py` — response schemas (summary, cards, detail, payments).
- Wire `GET /api/dashboard/summary` (real data, drop the `501`).
- Enrich `GET /api/subscriptions` to return card aggregates, and
  `GET /api/subscriptions/{id}` to return the per-subscription drill-down
  (totals, next payment, overdue/missing, payment history).
- Tests over seeded payments.

### Out of scope

- Currency normalization across merchants (cross-cutting / later) — we sum raw
  `amount` and surface a representative `currency`.
- Frontend (Phase 6), scheduled re-scans, notifications.

## Approach

- **Portability over `date_trunc`.** The architecture sketches Postgres
  `date_trunc('month', ...)`, but tests and CI run on SQLite. To keep one
  codepath, fetch the user's payments (already small, one tenant) and bucket by
  calendar month in Python. No Postgres-specific SQL.
- Aggregation is tenant-scoped: every query filters on `user_id`. The cards/
  detail endpoints fetch all of a user's payments once and group by
  `subscription_id` in memory (no N+1).
- Month math via small helpers (`_add_months`, `_month_key`, `_month_window`);
  "this/last month" and the 12-month chart window are derived from `today`
  (injectable so tests are deterministic).
- Spend totals count only `status == "paid"` payments; `overdue_total` sums
  `overdue`; `missing_count` counts `missing` + `overdue` (an overdue payment is
  also a missing-expected one). `next_payment_*` comes from the subscription's
  `next_payment_date` / `amount`.

## Steps

1. `schemas/dashboard.py`: `MonthlySpend`, `DashboardSummary`, `PaymentOut`,
   `SubscriptionCard`, `SubscriptionDetail`.
2. `services/dashboard.py`: month helpers; `get_summary`, `get_subscription_cards`,
   `get_subscription_detail` (tenant-scoped, Python bucketing).
3. `api/dashboard.py`: replace the `501` summary with the real one; point the
   list + detail endpoints at the service; return the richer schemas.
4. Tests: `test_dashboard.py` — monthly buckets + this/last month, card
   aggregates, detail drill-down, 404 cross-tenant, empty state.

## Acceptance criteria

- `GET /api/dashboard/summary` returns a 12-month series + this/last-month totals
  over seeded payments.
- `GET /api/subscriptions` returns cards with correct total/last-month/overdue.
- `GET /api/subscriptions/{id}` returns the drill-down; 404 cross-tenant.
- `uv run pytest` green, `uv run ruff check` + `ruff format --check` clean,
  `alembic check` drift-free (no schema change this phase).
