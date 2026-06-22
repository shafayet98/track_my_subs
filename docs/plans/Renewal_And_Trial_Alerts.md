# Renewal & free-trial alerts (proactive notifications)

Closes #18.

## Goal

Proactively email users before money moves: upcoming renewals and — the headline
— free trials about to convert to paid ("your Notion trial converts to $96/yr on
Sat — cancel if you don't want it"). Turns the dashboard from a passive ledger
into something that actively saves people money. Most raw signal already exists
(next-payment dates, trial emails); we just don't act on it yet.

## Scope

Land in two stages (one PR each — keep PRs focused):

**Stage A — capture + detect (this plan's first PR):**

- Capture trial-conversion dates: agent records when an email says a trial
  converts to paid.
- Pure detection logic: given a user's subscriptions/payments + prefs + already-
  sent log, decide which events are due within the lead window (upcoming
  renewals, trials converting soon, missed/overdue payments) — deduped.
- Data model for prefs + a sent-notifications log (so detection can dedup and
  respect opt-out), with sensible defaults.
- Tests covering detection (which events fire), dedup, and lead-window math.
  Anthropic/Gmail mocked at the boundary.

**Stage B — deliver (second PR, separate):**

- Scheduled worker (daily) that runs detection per user and sends email.
- SES delivery (CDK: SES identity + IAM send perms; `integrations/ses_client.py`;
  plain templated emails — parsed facts only).
- Preferences API + a frontend settings screen (on/off per type, lead-time days).

### Out of scope

- Price-increase alerts (separate follow-up; reuses this delivery channel).
- Push / SMS / in-app channels — email only to start.
- Changing the scan schedule itself or history-synthesis (separate issues #14 /
  history work — better dates only *improve* these alerts).

## Approach

Key files and decisions:

**Data model (Stage A migration — additive, backward-compatible):**

- `models/subscription.py` — add `trial_end_date: date | None` (the date a trial
  converts to paid). The convert-to amount/currency reuse the existing
  `amount`/`currency` columns. No new status value needed.
- `models/notification.py` (new) — `Notification`: `user_id`, `subscription_id`,
  `event_type` ("renewal" | "trial_conversion" | "missed_payment"), `event_date`,
  `sent_at`. The dedup key is `(subscription_id, event_type, event_date)` —
  one alert per concrete event, ever.
- `models/notification_preference.py` (new) — `NotificationPreference` per user:
  `renewals_enabled` / `trial_conversions_enabled` / `missed_payments_enabled`
  (bool, default true) and `lead_time_days` (int, default 3). One row per user;
  detection treats a missing row as defaults.
- Register both in `models/__init__.py` (Alembic autogenerate sees them).
- New Alembic revision under `alembic/versions/` (additive columns/tables only —
  CD runs migrations after the rollout, so they must be backward-compatible).

**Agent (Stage A):**

- `agent/tools.py` — add a `trial_end_date` property (YYYY-MM-DD) to the existing
  `upsert_subscription` schema and persist it in `_exec_upsert_subscription`
  (same `_parse_date` path as `next_payment_date`). Keep the **tool list order**
  stable; adding one optional property to an existing tool is the deliberate,
  minimal change.
- `agent/prompts.py` — document `subscription.trial_end_date`: set it only when an
  email indicates a free trial that converts to paid on a specific date.

**Detection logic (Stage A — the testable core):**

- `services/alerts.py` (new) — a pure function, e.g.
  `due_notifications(subscriptions, payments, prefs, already_sent, today) ->
  list[DueEvent]`. No DB, no I/O — takes plain data, returns the events to send.
  - Renewal: `next_payment_date` within `[today, today + lead_time_days]` and
    renewals enabled.
  - Trial conversion: `trial_end_date` within the lead window and enabled.
  - Missed/overdue: a `missing`/`overdue` payment (the agent already flags these)
    not yet notified.
  - Skip any event whose `(subscription_id, event_type, event_date)` is in
    `already_sent` (dedup) or whose type is disabled in prefs.
- Keeping this pure is the whole point: Stage A tests it exhaustively without a
  scheduler or SES.

**Delivery (Stage B):**

- `integrations/ses_client.py` (new) — thin SES send wrapper; creds server-side
  only, never logged.
- `worker/` entrypoint (e.g. `python -m app.worker.alerts`) — loads each user's
  subs/payments/prefs/sent-log, calls `due_notifications`, sends via SES, writes a
  `Notification` row per sent event (the dedup record). Tenant-scoped on
  `user_id`.
- `infra/stacks/` — SES identity + IAM `ses:SendEmail` on the task role; an
  EventBridge **scheduled** rule (daily) → ECS `RunTask` of the worker (mirrors
  the existing `BackendStack` task wiring). New env: sender address.
- `api/` + `frontend/` — `notification_preferences` GET/PUT router (thin →
  service) and a settings screen using the existing typed API client.

**Privacy/security (`.claude/rules/security.md`):**

- Notifications contain **parsed facts only** (merchant, amount, date) — never any
  email content. The dedup log stores ids/dates/types, not content.
- Every query (detection, worker, prefs API) filters on the authenticated /
  job-scoped `user_id`. SES creds and sender config live server-side only.

## Steps

**Stage A (first PR):**

1. Models: add `trial_end_date` to `Subscription`; add `Notification` and
   `NotificationPreference`; register in `models/__init__.py`.
2. Alembic revision (additive) for the new column + tables.
3. Agent: add `trial_end_date` to `upsert_subscription` schema + executor; update
   the system prompt.
4. `services/alerts.py`: the pure `due_notifications` function.
5. Tests: detection (each event type fires correctly), dedup against the sent
   log, lead-window boundaries, prefs opt-out; agent executor persists
   `trial_end_date`. Anthropic/Gmail mocked.
6. `ruff check` + `ruff format --check` + `pytest` green. `progress.md` entry.

**Stage B (second PR) — DONE:** SES client + CDK (SES identity, IAM, EventBridge
schedule → worker ECS task) + worker entrypoint that sends and records
`Notification` rows + prefs API + frontend settings screen + tests
(SES mocked; `cdk synth` green).

Delivered:
1. `integrations/ses_client.py` — thin SES `send_email` wrapper (creds from the
   task role; never logged).
2. `services/notifications.py` — prefs get/upsert, email rendering (parsed facts
   only), `run_user_alerts` (detect → send → record), `run_all_alerts` (batch).
3. `worker/alerts.py` — `python -m app.worker.alerts` entrypoint.
4. `api/notifications.py` + `schemas/notifications.py` — `/notifications/
   preferences` GET/PUT; wired in `main.py`.
5. Frontend — `SettingsPage` (toggles + lead time), api client/types, route,
   nav link.
6. `infra/stacks/backend_stack.py` — SES domain identity (DKIM via hosted zone),
   `ses:SendEmail` task-role grant, EventBridge daily rule → worker ECS RunTask.
7. Config: `AWS_REGION`, `SES_SENDER`, `APP_BASE_URL` (+ `.env.example`); `boto3`
   dependency.
8. Tests `test_notifications_worker.py` / `test_notifications_api.py` (SES
   mocked). `ruff` + `pytest` (68) + `cdk synth` + `npm run build` green.

> Note: real sends need SES production access (out of sandbox) and the
> `alerts@shafcode.xyz` sender live; until then `SES_SENDER` is empty and the
> worker logs+skips.

## Acceptance criteria

- The agent records trial-conversion dates where the email indicates a trial
  (Stage A).
- A scheduled job detects upcoming renewals and trial conversions within the
  user's lead window and sends at most one email per event (deduped) (Stage B,
  on the Stage A core).
- Users can opt out / set lead time; respected by the job.
- Tests cover detection (which events fire, dedup, lead-window math) and
  preference handling; Gmail/Anthropic/SES mocked (no live calls in CI).
- No raw email content leaves the system in any notification.
