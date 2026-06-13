# Plan — CI pipeline (GitHub Actions)

Branch: `chore/ci`

## Goal

Add a GitHub Actions workflow that runs on every PR to `main` (and pushes to
`main`) so lint, formatting, tests, and migrations are verified automatically.
This enforces the PR-per-phase workflow and raises the quality floor before the
codebase grows (Gmail, agent, dashboard).

## Scope

In scope:
- A single workflow `.github/workflows/ci.yml` with one **backend** job:
  install (uv) → `ruff check` → `ruff format --check` → `pytest` → migrations
  apply + drift check.
- Keep it **hermetic**: no secrets, no network, SQLite only — this validates our
  rule of mocking the Gmail/Anthropic boundary (`.claude/rules/security.md`).

Out of scope (deliberate, per discussion):
- **Postgres service container** — we test on SQLite for speed (option A). Add a
  Postgres job at Phase 5 (dashboard aggregation) when we introduce
  Postgres-specific SQL (`date_trunc`, etc.).
- **Frontend job** — added in Phase 6 when the React app exists.
- **CD / deploy** — separate concern, comes with Phase 7 (AWS CDK).

## Approach / decisions

- **uv** via `astral-sh/setup-uv@v5` with caching (keyed on `backend/uv.lock`).
- Steps run with `working-directory: backend`.
- **Formatting is enforced** (`ruff format --check`) so style is automated, not
  argued. Normalized the existing files with `ruff format` as part of this work.
- **Migration drift check** (`alembic upgrade head` + `alembic check`) catches
  the "changed a model, forgot the migration" bug. To make `alembic check`
  drift-free, the initial migration now uses the same custom `GUID` type as the
  models (previously `sa.String(36)`, which `compare_type` flagged as a change).
- Triggers: `pull_request` + `push` to `main`. `concurrency` cancels superseded
  runs. Least-privilege `permissions: contents: read`.

## Steps

1. Fix migration to use the `GUID` type so `alembic check` is clean. ✅
2. `ruff format` the repo so `--check` passes in CI. ✅
3. Write `.github/workflows/ci.yml` (backend job above).
4. Verify locally: `ruff check`, `ruff format --check`, `pytest`, `alembic
   upgrade head` + `alembic check` all green. ✅ (drift check confirmed clean)
5. Update `progress.md`; open PR `chore/ci` → `main` (the PR run self-validates).

## Acceptance criteria

- The workflow runs on the PR and passes: lint, format, tests, migrations.
- No secrets referenced anywhere in the workflow.
- After merge, enable branch protection requiring this check (manual GitHub
  setting — note in the PR).
