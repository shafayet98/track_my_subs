# CD: migrate before rollout + log swallowed scan failures (#25)

## Goal

Stop scans (and any request) from failing during a deploy because the new code is
serving against the old DB schema, and make scan failures diagnosable in the logs.

## Background (the incident)

On 2026-06-21, a scan failed with `column subscriptions.trial_end_date does not
exist`. That column was added by #18's migration `0002`. CD rolls the ECS service
onto the new image **first**, then runs migrations ~2 min later — so for ~2 minutes
new code ran against the old schema. The scan ran in that window. The failure was
invisible: `run_scan_job` swallows the exception with a generic summary.

## Scope

1. **CD ordering** (`.github/workflows/cd.yml`) — run `alembic upgrade head` on the
   **new image** *before* `cdk deploy` rolls the service. Additive migrations are
   backward-compatible with the still-running old code, so migrate-first closes the
   window (expand/contract).
2. **Scan-job logging** (`backend/app/agent/loop.py`) — log the exception (traceback
   + scan id) when a scan fails, keeping the generic user-facing summary. No email
   content / PII (per `.claude/rules/security.md`).

## Out of scope

- Reworking how scans run (still an in-process background task).
- Changing the migration contents or the additive-migrations convention.

## Approach

### CD (cd.yml)
The new image is already built/pushed before deploy. To migrate on it before
rollout, the one-off ECS task needs a task def pointing at the new image. Derive it
from the live service's current task definition, swap only the image to
`${GITHUB_SHA}`, register a one-off revision, run `alembic upgrade head` on it, gate
on exit code 0 — then `cdk deploy` (which registers its own revision and rolls the
service), then `wait services-stable`. `jq` is preinstalled on the runner.

### loop.py
Add a module logger; in the `except Exception` block call
`logger.exception("scan %s failed", scan_run_id)` before setting the failed status.
`logger.exception` captures the traceback (DB/API errors — message ids at most, no
bodies).

## Steps
1. Plan (this file). ✅
2. Reorder cd.yml: migrate-on-new-image step before `cdk deploy`; drop the old
   post-deploy migrate step; keep `wait services-stable` after deploy.
3. loop.py: module logger + `logger.exception(...)` in the failure path.
4. Test: `run_scan_job` logs on failure (Gmail/Anthropic mocked, caplog).
5. `ruff` + `pytest`; update `.claude/progress.md`.

## Acceptance criteria
- CD runs DB migrations before the ECS service rollout (no new-code/old-schema
  window).
- A failed scan logs the underlying exception (type/message + scan id), no email
  content/PII.
- Tests cover the scan-job logging path; suite green; Gmail/Anthropic mocked.
