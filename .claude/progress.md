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

## 2026-06-21 — CD: grant ecs:RegisterTaskDefinition to the deploy role (fix/cd-register-taskdef-permission, #26 follow-up)

**What:** Fixed CD, which #26 broke on first run. #26's migrate-before-rollout step
registers a one-off ECS task-def revision (cloned from the live one, image swapped
to the new SHA) so `alembic upgrade head` runs on the new image pre-rollout — but
the `github-actions-deploy` role lacked `ecs:RegisterTaskDefinition`, so the step
failed with `AccessDeniedException` (before `cdk deploy`, so prod was untouched —
it kept running the previous image). Added `ecs:RegisterTaskDefinition` to the
role's ECS policy statement in `cicd_stack.py` (the needed `iam:PassRole`, scoped
to `ecs-tasks.amazonaws.com`, was already granted). Since `TrackMySubs-Cicd` is
intentionally not deployed by CD, this was applied out-of-band
(`cdk deploy TrackMySubs-Cicd`) to unblock the pipeline; this commit makes the
stack source match. Plan: `docs/plans/CD_register_taskdef_permission.md`.
**Why:** the migrate-before-rollout fix (#26) couldn't run without the registration
permission; main's CD was red.
**Touches:** `infra/stacks/cicd_stack.py`,
`docs/plans/CD_register_taskdef_permission.md`.
**Verified:** `ruff check` clean; `cdk synth TrackMySubs-Cicd` includes
`ecs:RegisterTaskDefinition`; stack deployed (DeployRole policy updated); CD
re-run exercises the migration step end-to-end.
**Follow-ups:** the one-off migration task-def revisions accumulate in ECS
(harmless/free) — could deregister old revisions later if it gets noisy.

## 2026-06-21 — CD: migrate before rollout + log swallowed scan failures (fix/cd-migrate-before-rollout-and-scan-logging, #25)

**What:** Fixed a deploy-window race surfaced by a real failed scan. After #18
deployed, CD rolled the ECS service onto the new image **first** and ran
migrations ~2 min later, so new code briefly queried `subscriptions.trial_end_date`
before migration `0002` added it (`UndefinedColumnError`) — a scan in that window
failed. **CD (`cd.yml`):** now migrates **before** rollout. The new image is
already in ECR, so the step derives a one-off task-def revision from the live
service's current task definition (via `describe-task-definition` + `jq`, swapping
only the image to `${GITHUB_SHA}`), runs `alembic upgrade head` on it, gates on
exit 0 — *then* `cdk deploy` rolls the service and waits services-stable. Additive
migrations stay backward-compatible with the still-running old code, so
migrate-first closes the window (expand/contract). **Backend (`agent/loop.py`):**
`run_scan_job` previously swallowed the exception with only a generic summary, so
the failure was invisible in logs; it now `logger.exception("scan %s failed",
scan_run_id)` before setting the failed status (DB/API errors carry message ids at
most — no email bodies/PII, per `.claude/rules/security.md`). Test: `run_scan_job`
logs the traceback keyed by scan id and marks the run failed (Gmail/Anthropic
mocked). Plan: `docs/plans/CD_migrate_before_rollout_and_scan_logging.md`.
Closes #25.
**Why:** a user's scan failed during the #18 deploy; the root cause (migrate-after-
rollout) and the silent failure path both needed fixing so it can't recur and is
diagnosable next time.
**Touches:** `.github/workflows/cd.yml`, `backend/app/agent/loop.py`,
`backend/tests/test_agent_loop.py`,
`docs/plans/CD_migrate_before_rollout_and_scan_logging.md`.
**Verified:** `uv run ruff check` + `ruff format --check` clean; `uv run pytest`
→ 59 passed (1 new); `cd.yml` valid YAML. CD ordering verified by review (next
merge exercises it live).
**Follow-ups:** for non-additive (contract) migrations the expand/contract split
must be done by hand across two deploys — migrate-first only covers additive
changes; an optional manual-approval gate before prod rollout.

## 2026-06-21 — Renewal & free-trial alerts: capture + detection (feat/renewal-trial-alerts, #18)

**What:** Stage A of proactive notifications (issue #18) — the capture and
detection core, no delivery yet. The agent can now record when a free trial
converts to paid: added an optional `trial_end_date` to the `upsert_subscription`
tool schema/executor (same `_parse_date` path as `next_payment_date`, tool order
unchanged for prompt caching) and to the system prompt (set only when an email
indicates a trial converting on a date; the convert-to amount stays in `amount`).
Added `Subscription.trial_end_date` plus two models: `Notification` (a sent-alert
log; unique `(subscription_id, event_type, event_date)` so a concrete event is
alerted at most once) and `NotificationPreference` (per-user on/off for renewals /
trial conversions / missed payments + `lead_time_days`, defaults all-on / 3 days).
Migration `0002` is additive (one nullable column + two tables), backward-
compatible. The detection core is `services/alerts.py::due_notifications(...)` — a
**pure** function (no DB/IO/clock; `today` passed in) that, given a user's subs,
payments, prefs, and the already-sent set, returns the events due now: renewals
and trial conversions within `[today, today+lead_time_days]`, and missed/overdue
payments (already flagged by the agent), deduped (against the sent log and within
a run) and respecting prefs; cancelled subs are skipped.
**Why:** issue #18 — turn the passive dashboard into something that proactively
saves users money (esp. free-trial conversions). Keeping detection pure lets us
land + fully test the logic now, before the Stage-B scheduler/SES wiring.
**Touches:** `backend/app/models/{subscription,notification,notification_preference,__init__}.py`,
`backend/alembic/versions/0002_renewal_trial_alerts.py`,
`backend/app/agent/{tools,prompts}.py`, `backend/app/services/alerts.py`,
`backend/tests/{test_alerts,test_agent_tools}.py`,
`docs/plans/Renewal_And_Trial_Alerts.md`.
**Verified:** `ruff check` + `ruff format --check` clean; full suite 56 tests pass
(14 new); `alembic upgrade head` applies and `alembic check` reports no drift;
live-exercised `due_notifications` against the issue's Notion-trial / Netflix-
renewal / Spotify-missed scenario incl. dedup re-run and prefs opt-out.
**Follow-ups:** Stage B — scheduled worker (EventBridge → ECS) running detection
per user, SES delivery (CDK identity + IAM, `integrations/ses_client.py`, parsed
facts only), `notification_preferences` API + frontend settings screen. Price-
increase alerts reuse this channel later.

## 2026-06-21 — Scan all accounts + remove the 100-email cap (feat/scan-all-accounts-no-cap, #23)

**What:** Made a scan comprehensive in two dimensions. **Part A** — dropped the
100-candidate cap in `GmailClient.search_candidates`: it now pages through the
**entire** lookback window following `nextPageToken` (500 ids/page internally,
just the batch size — not a ceiling), keeping `format=metadata` so no bodies are
pulled during triage. Removed the `max_results` argument. **Part B** —
`run_scan_job` now iterates **every** connected Gmail account (was the first row
only): per account it decrypts that mailbox's token, builds its own
`GmailClient`, runs the agent loop with a `ScanContext` scoped to that mailbox
(a message id is only valid with its own token), then aggregates
`emails_scanned` / `subscriptions_found` and joins per-account summaries
(prefixed with the mailbox address); status is `succeeded` only if every account
completed, and `last_synced_at` is set per account. So AWS bills sitting in a
second inbox now show up. Tests (Gmail mocked, no network): pagination across
pages in `search_candidates`, multi-account aggregation in `run_scan_job`, and
the dropped-cap call site updated. Plan:
`docs/plans/Scan_all_accounts_no_cap.md`. Closes #23.
**Why:** issue #23 — coverage (which mailboxes) and completeness (no cap) were
both limited; only one inbox was scanned and only its first 100 matches.
**Touches:** `backend/app/integrations/gmail.py`, `backend/app/agent/loop.py`,
`backend/tests/test_gmail.py`, `backend/tests/test_agent_loop.py`,
`docs/plans/Scan_all_accounts_no_cap.md`.
**Verified:** `uv run ruff check` + `ruff format --check` clean; `uv run pytest`
→ 44 passed (2 new). No live Gmail/LLM network in tests.
**Follow-ups:** subscription dedup / merchant-name normalization in
`upsert_subscription` (more candidates + multiple inboxes make duplicate rows
like "Anthropic (Claude Pro)" vs "Anthropic Claude Pro" more likely); an
optional high safety bound on candidates if a very busy mailbox proves costly.

## 2026-06-21 — Frontend redesign + 2-month scan window (feat/frontend-redesign, #20)

**What:** Redesigned the SPA to a warm cream/coral, monospace-accented look (per
provided screenshots) and widened the default scan window. Frontend: rewrote
`index.css` as a design-token system (cream bg, coral accent, Space Mono for
brand/numbers/labels, soft shadowed cards, rounded status pills incl.
`cancelled`/`unknown`), added the Space Mono font link in `index.html`, and an
`initials()` helper. Restyled every screen: 3-section topbar with centered brand +
`Connect` button + user avatar (`Layout`); auth "Welcome back / Create an account"
(`LoginPage`); dashboard coral summary card beside the chart card + Subscriptions
count + better empty state (`DashboardPage`); merchant-avatar subscription cards
(`SubscriptionCard`); avatar header + stat cards + payment table
(`SubscriptionDetailPage`); coral chart bars (`SpendChart`); and a friendlier "no
candidate emails — connect the inbox where your receipts arrive" message on the
scan page (`ConnectAccountPage`). No backend data/schema changes — the API already
returned category/confidence/payments. Backend: `SCAN_LOOKBACK_DAYS` default
14 → 60 (~2 months) so a first scan catches a billing cycle; the existing lookback
test reads `settings.scan_lookback_days` so it adapts. Chose refined CSS over a
Tailwind migration to match the screenshots precisely with a reviewable diff.
Plan: `docs/plans/Frontend_redesign_and_2mo_scan.md`.
**Why:** issue #20 — make the product look finished for real users, and stop sparse
mailboxes returning nothing on a first scan.
**Touches:** `frontend/index.html`, `frontend/src/index.css`,
`frontend/src/components/{Layout,SubscriptionCard,SpendChart}.tsx`,
`frontend/src/pages/{Login,Dashboard,ConnectAccount,SubscriptionDetail}Page.tsx`,
`frontend/src/lib/format.ts`, `backend/app/core/config.py`,
`docs/plans/Frontend_redesign_and_2mo_scan.md`.
**Verified:** `npm run lint` + `npm run build` green; backend `ruff` clean + all 42
tests pass.
**Follow-ups:** optional Tailwind/component-library migration; code-split the
Recharts-heavy bundle; self-host the font.

## 2026-06-20 — Time-based scan window: last 14 days (feat/scan-lookback-window)

**What:** Changed the mailbox scan from a count-based window (the 100 most-recent
candidate emails, no date filter) to a time-based one: the last N days (default
14). Added `scan_lookback_days` to `core/config.py` (env `SCAN_LOOKBACK_DAYS`) so
the window is one tunable value. `agent/loop.py`'s `run_scan_job` now computes
`after = now(UTC) - timedelta(days=settings.scan_lookback_days)` and passes it to
the already-supported `GmailClient.search_candidates(after=...)`. `max_results`
stays at 100 as a safety cap (documented) — a 14-day window is far smaller than an
all-time mailbox, so truncation risk drops; pagination stays deferred (it pairs
with the larger history-synthesis idea). Tests (`test_gmail.py`): the `after:`
filter lands in the Gmail query with the expected date, and no date filter is
applied by default. Gmail mocked at the boundary (no network). Closes #14. Plan:
`docs/plans/Scan_lookback_window.md`.
**Why:** so each scan covers a consistent recent time window regardless of mailbox
size — previously a large mailbox only ever surfaced the latest ~100 matches,
with no predictable time bound.
**Touches:** `backend/app/core/config.py`, `backend/app/agent/loop.py`,
`backend/tests/test_gmail.py`, `docs/plans/Scan_lookback_window.md`.
**Verified:** `uv run ruff check` + `ruff format --check` clean; `uv run pytest`
→ 41 passed (2 new). No live network in tests.
**Follow-ups:** history synthesis (identify a subscription once, derive payment
history from cadence) — would revisit the 100-candidate cap / pagination.

## 2026-06-20 — Top-level README + contributor guide (chore/readme)

**What:** Added a human-facing `README.md` at the repo root (there was none —
`CLAUDE.md` is agent-facing). Covers the product pitch + privacy posture, how the
agent works, tech stack, an architecture diagram, local-dev quickstart + required
secrets, tests/checks, deployment + CD summary, the contributing flow (the
`/plan` `/coding` `/cpr` `/investigate` commands + rules), project layout, and a
CI badge. Also added `contributor_guideline.md` — a practical contributor guide
(what you need to contribute, the branch→PR workflow + slash commands, condensed
coding/LLM/security standards, tests/checks, the progress.md requirement, commit/PR
conventions, and the "merging deploys to prod via CD" warning). The README's
Contributing section links to it. Both link out to `docs/architecture.md`,
`infra/README.md`, `docs/roadmap.md`, and `.claude/rules/`.
**Why:** the repo had no project description for humans / GitHub visitors, and no
single onboarding doc for contributors.
**Touches:** `README.md` (new), `contributor_guideline.md` (new).
**Verified:** docs-only; links point at existing paths. No code/tests affected.
**Follow-ups:** add a LICENSE if the project is opened up; drop in screenshots/GIF
once there's a public demo instance.

## 2026-06-20 — CD pipeline: GitHub OIDC → IAM (feat/cd-pipeline)

**What:** Auto-deploy to AWS on merge to `main`, authenticated via GitHub OIDC
(no long-lived keys). New CDK stack `cicd_stack.py` (`TrackMySubs-Cicd`) creates a
GitHub OIDC provider + a `github-actions-deploy` role whose trust is scoped to
`repo:shafayet98/track_my_subs:ref:refs/heads/main`; the role can assume the CDK
bootstrap roles (for `cdk deploy`) and do the direct steps (ECR push, ECS RunTask
+ PassRole, SPA-bucket S3 sync, CloudFront invalidation, CFN DescribeStacks) —
scoped, not a broad managed policy. `backend_stack.py` now reads the image tag
from `imageTag` context (default `latest`) so CD deploys by commit SHA and ECS
rolls deterministically. New `.github/workflows/cd.yml` (on push to main): OIDC
auth → build/push image tagged `$GITHUB_SHA` → `cdk deploy` the 5 app stacks with
`-c imageTag=$GITHUB_SHA` → run migrations as a one-off ECS task (discovers
cluster/taskdef/network at runtime) + wait services-stable → build SPA → s3 sync +
CloudFront invalidation (bucket/dist from `TrackMySubs-Frontend` outputs).
`concurrency: deploy-prod` prevents overlap. The Cicd stack is intentionally NOT
deployed by CD. Deployed `TrackMySubs-Cicd` once to create the provider + role.
Plan: `docs/plans/CD_pipeline.md`.
**Why:** the follow-up from the manual first deploy — encode the runbook so
merge-to-main ships the app with no manual `aws`/`cdk`/`docker` steps.
**Touches:** `infra/stacks/cicd_stack.py` (new), `infra/stacks/backend_stack.py`,
`infra/app.py`, `.github/workflows/cd.yml`, `infra/README.md`,
`docs/plans/CD_pipeline.md`.
**Verified:** `cdk synth -c imageTag=…` produces all 6 stacks incl. `TrackMySubs-Cicd`;
ruff clean; `cd.yml` valid YAML; `TrackMySubs-Cicd` deployed (OIDC provider +
`github-actions-deploy` role exist). End-to-end pipeline run is verified post-merge
(first push to main with the workflow present).
**Follow-ups:** tighten ECS/CloudFront resource scoping; optional manual-approval
GitHub Environment; migrations currently run post-rollout (keep them additive).

## 2026-06-20 — First AWS deploy: fixes (fix/rds-postgres-version)

**What:** Fixes found while doing the first real `cdk deploy` of the stack into
audrie98 (the app is now live: SPA on CloudFront, API at https://api.shafcode.xyz,
RDS, ECS Fargage, secrets, connect-Gmail → scan all working). Three changes:
1. **RDS engine 16.4 → 16.9** (`data_stack.py`) — 16.4 was retired in
   ap-southeast-2; use `PostgresEngineVersion.of("16.9","16")` to pin an
   actually-offered minor.
2. **ECR split into its own stack** (`ecr_stack.py` new; `backend_stack.py` takes
   `repository` as a prop; `app.py` deploys `TrackMySubs-Ecr` and wires it). The
   repo previously lived in the backend stack, so on first deploy the Fargate
   service couldn't stabilize (no image yet) and the rollback **deleted the repo**.
   Separate lifecycle = deploy repo → push image → deploy service.
3. **OAuth PKCE fix** (`gmail.py`) — `Flow` defaulted to
   `autogenerate_code_verifier=True`, so the auth-URL step sent a PKCE challenge
   but the token-exchange step (a fresh `Flow`) had a different verifier →
   Google returned `invalid_grant`. Set `autogenerate_code_verifier=False`
   (confidential web client with a secret doesn't need PKCE). This was never
   caught earlier because the OAuth round-trip was only ever tested against
   fixtures, never live.
   README updated: new deploy order (ECR before image push), the bootstrap-bucket
   recreation gotcha, the zsh `${REPO}:latest` tag gotcha, and a one-off ECS
   `run-task` recipe for migrations.
**Why:** get the first real deployment working end-to-end; land the fixes on
`main` so the repo matches what's deployed.
**Touches:** `infra/stacks/data_stack.py`, `infra/stacks/ecr_stack.py` (new),
`infra/stacks/backend_stack.py`, `infra/app.py`, `backend/app/integrations/gmail.py`,
`infra/README.md`.
**Verified:** stack deployed; `https://api.shafcode.xyz/api/health` 200; Gmail
connect (callback 303) + scan populate real subscriptions on the dashboard;
`cdk synth` + ruff clean.
**Follow-ups:** CD pipeline (GitHub OIDC role → build/push/deploy on merge);
history synthesis (identify a subscription once, then derive payment history from
cadence instead of reading every email — raise/paginate the 100-candidate cap);
rotate the Anthropic key (it transited chat during setup).

## 2026-06-17 — API custom domain + HTTPS (feat/api-https-domain)

**What:** Put the backend API behind `https://api.shafcode.xyz` so Google OAuth
(needs an https redirect on an owned domain) works once deployed. DNS for
shafcode.xyz now lives in a Route 53 hosted zone in the audrie98 account
(`Z0858754AS09Y4TNXSF5`; the registrar's nameservers were repointed to it — the
old delegation was to an empty, unused zone in another account). An ACM cert for
`api.shafcode.xyz` (ap-southeast-2, DNS-validated against the zone) is referenced
by ARN. The backend stack now passes `protocol=HTTPS`, the cert, `domain_name`,
`domain_zone` (referenced via `HostedZone.from_hosted_zone_attributes` — by id, no
lookup, so CI synth stays offline) and `redirect_http=True` to the
`ApplicationLoadBalancedFargateService`, which yields an HTTPS:443 listener, an
HTTP→HTTPS redirect, and an auto-created `api.shafcode.xyz` A-alias to the ALB.
`GOOGLE_OAUTH_REDIRECT_URI` moved from a secret placeholder to a fixed task env var
(`https://api.shafcode.xyz/api/accounts/gmail/callback`) and was dropped from the
app-secrets template. Outputs now show the https API URL + the raw ALB DNS. README
gains a Domain/DNS/TLS section and the deploy steps reflect the fixed redirect URI;
plan: `docs/plans/Api_https_domain.md`.
**Why:** unblock the core Gmail-connect flow in the deployed environment — the API
must be reachable over https on a domain we control.
**Touches:** `infra/stacks/backend_stack.py`, `infra/stacks/data_stack.py`,
`infra/README.md`, `docs/plans/Api_https_domain.md`.
**Verified:** `cdk synth` clean; the backend template contains an HTTPS:443
listener using the cert, an HTTP:80→HTTPS redirect, and an `api.shafcode.xyz`
Route 53 record. `ruff check` + format clean. Not deployed — gated on the cert
reaching `Issued` (waiting on nameserver propagation) and owner go-ahead.
**Follow-ups:** deploy once the cert is Issued; a custom frontend domain
(`app.shafcode.xyz`, needs a us-east-1 cert) is still later.

## 2026-06-14 — AWS deployment, CDK (feat/aws-deployment-cdk)

**What:** Implemented Phase 7 — Infrastructure-as-code as an AWS CDK (Python) app
under `infra/`, targeting the **audrie98** account (`390843337949`),
`ap-southeast-2` (SSO profile `audrie98`). Four stacks wired in `app.py` with the
account/region pinned so synth is deterministic and needs no environment lookups:
**Network** (VPC, 2 AZ, 1 NAT, public + private-with-egress subnets); **Data**
(RDS PostgreSQL 16, private, encrypted, single-AZ burstable Graviton micro; DB
creds in an RDS-managed Secrets Manager secret; plus an app-secrets secret —
`JWT_SECRET` generated, the external keys (Anthropic, Google OAuth, Fernet token
key, redirect URI, frontend origin) created as empty placeholders the owner fills
out-of-band); **Backend** (ECR repo, ECS cluster, a Fargate API service behind an
internet-facing ALB via `ApplicationLoadBalancedFargateService`, health check
`GET /api/health`, image pulled from ECR by tag so synth/deploy need no local
Docker; DB host/port/name injected as env and user/password from the RDS secret,
app secrets injected from Secrets Manager); **Frontend** (private S3 bucket +
CloudFront with OAC and 403/404 → `index.html` SPA fallback). RDS access is opened
to the API task SG via a standalone `CfnSecurityGroupIngress` declared in the
backend stack, keeping the cross-stack dependency one-way (backend → data) and
avoiding a dependency cycle. Added `backend/Dockerfile` (+ `.dockerignore` and a
`docker-entrypoint.sh` that composes `DATABASE_URL` from the injected `DB_*` parts
so the password never sits in a plaintext env var — backend code unchanged).
`infra/README.md` documents bootstrap → deploy → build/push image → fill secrets →
migrate → frontend upload → destroy. Pinned `aws-cdk-lib<2.250` to match the
installed CDK CLI's cloud-assembly schema. CI: added an `infra` job (uv sync →
ruff check + format check → `cdk synth`) alongside the backend/frontend jobs.
Plan: `docs/plans/AWS_deployment.md`.
**Why:** Phase 7 of the roadmap — get the app deployable on AWS (S3+CloudFront SPA,
Fargate API, RDS Postgres, Secrets Manager).
**Touches:** `infra/**` (new), `backend/Dockerfile`, `backend/docker-entrypoint.sh`,
`backend/.dockerignore`, `.github/workflows/ci.yml`, `docs/plans/AWS_deployment.md`.
**Verified:** `cd infra && uv sync && uv run cdk synth` synthesizes all four stacks
cleanly (no Docker build needed); `uv run ruff check` + format clean. The one
context lookup (availability zones, from pinning a real account/region) is cached
in committed `cdk.context.json`, so CI synth needs no AWS credentials. No secret
values committed; the app-secrets secret is structure-only.
**Follow-ups:** Actual `cdk deploy` is a gated step (billable resources) pending
owner go-ahead. Deferred: a dedicated scan-worker Fargate service (needs a backend
worker entrypoint — scans run in-process today), custom domain + ACM/Route53,
CI/CD for image build+push and auto-deploy, autoscaling/WAF/multi-AZ RDS, and
tightening RDS/S3/ECR removal policies before holding real data.

## 2026-06-13 — Frontend (feat/frontend)

**What:** Implemented Phase 6 — the React + Vite + TypeScript SPA. New `frontend/`
project (Vite + React 18 + TS, `react-router-dom`, `recharts`, eslint). One typed
API client (`src/api/client.ts` + `types.ts`) mirroring the backend schemas:
attaches the JWT, throws `ApiError` on non-2xx, clears the token on 401; base URL
from `VITE_API_BASE_URL` (default `http://localhost:8000/api`). Auth via
`AuthContext` (JWT in `localStorage`, `/auth/me` on load) + a `RequireAuth` route
guard. Pages: **LoginPage** (login/register toggle), **DashboardPage**
(`/dashboard/summary` → this/last-month + active count + a 12-month Recharts bar
chart; `/subscriptions` → card grid), **ConnectAccountPage** (lists accounts,
"Connect Gmail" → redirect to the consent URL, "Scan now" → `POST /scans` then
polls `GET /scans/{id}` every 2s until terminal, handles the `?gmail=connected`
return), **SubscriptionDetailPage** (`/subscriptions/{id}` → totals, next payment,
overdue/missing, payment-history table). Dumb presentational components
(`SpendChart`, `SubscriptionCard`, `Layout`) + a `useFetch` hook + display
helpers; minimal hand-rolled CSS (no UI framework). CI: added a `frontend` job
(npm ci → eslint → tsc + vite build); committed `package-lock.json`, gitignored
`*.tsbuildinfo`. Plan: `docs/plans/Frontend.md`.
**Why:** Phase 6 of the roadmap — the UI that ties the whole flow together:
connect Gmail → scan → dashboard charts + cards → subscription detail.
**Touches:** `frontend/**` (new), `.github/workflows/ci.yml`, `.gitignore`,
`docs/plans/Frontend.md`.
**Verified:** `npm ci` + `npm run lint` (eslint clean) + `npm run build` (tsc +
vite) all green locally, matching the new CI job; backend CI unchanged.
**Follow-ups:** Phase 7 — AWS deployment (CDK). The bundle is one chunk (~550 kB,
Recharts-heavy); code-splitting is a later optimization. No frontend test runner
this phase — the typecheck + build is the gate.

## 2026-06-13 — Dashboard aggregation (feat/dashboard-aggregation)

**What:** Implemented Phase 5 — the read-side aggregation that turns the agent's
`subscriptions` + `payments` into dashboard numbers. New `services/dashboard.py`
(`get_summary`, `get_subscription_cards`, `get_subscription_detail`; tenant-scoped
on `user_id`) and `schemas/dashboard.py` (`MonthlySpend`, `DashboardSummary`,
`PaymentOut`, `SubscriptionCard`, `SubscriptionDetail`). Spend buckets are
computed in Python (group by calendar month), not Postgres `date_trunc`, so the
one codepath runs on SQLite (tests/CI) and Postgres; spend counts only
`status='paid'`, `overdue_total` sums `overdue`, `missing_count` counts
`missing`+`overdue`, `next_payment_*` comes from the subscription. Wired the API:
`GET /api/dashboard/summary` now returns a 12-month series + this/last-month
totals + active-subscription count (dropped the `501` stub); `GET /api/subscriptions`
returns card aggregates; `GET /api/subscriptions/{id}` returns the drill-down
(card aggregates + confidence + newest-first payment history). The list/detail
endpoints fetch a user's payments once and group in memory (no N+1). Month math
takes an injectable `today` for deterministic tests. Tests (`test_dashboard.py`):
this/last-month buckets with unpaid excluded, empty state, card aggregates
(total/last-month/overdue/missing/next-payment), detail endpoint shape + ordering,
cross-tenant 404. Plan: `docs/plans/Dashboard_aggregation.md`.
**Why:** Phase 5 of the roadmap — the data the Phase 6 frontend (spend chart +
subscription cards + detail) renders.
**Touches:** `backend/app/services/dashboard.py` + `__init__.py` (new),
`backend/app/schemas/dashboard.py` (new), `backend/app/api/dashboard.py`,
`backend/tests/test_dashboard.py` (new), `docs/plans/Dashboard_aggregation.md`.
**Verified:** `uv run pytest` → 39 passed; `uv run ruff check` + `ruff format
--check` clean; `alembic upgrade head` + `alembic check` drift-free on SQLite (no
schema change this phase).
**Follow-ups:** Phase 6 — the React frontend. Currency normalization across
merchants stays deferred (we sum raw `amount` and surface a representative
`currency`).

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
