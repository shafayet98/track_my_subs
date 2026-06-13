# The agent (Phase 4)

## Goal

Give the backend an agentic scan: Claude Opus 4.8 driving a small set of tools
through a manual agentic loop. It reads candidate subscription emails (from the
Phase 3 Gmail integration) and records `subscriptions` + `payments`, scoped to
the authenticated user. `POST /api/scans` kicks the scan off as a background job;
`GET /api/scans/{id}` reports status (already built).

## Scope

In scope:

- `integrations/anthropic_client.py` — `AsyncAnthropic` wrapper (reads
  `ANTHROPIC_API_KEY`; model + thinking per `.claude/rules/llm-usage.md`).
- `agent/prompts.py` — the stable system prompt (cacheable prefix).
- `agent/tools.py` — `TOOL_SCHEMAS` (deterministic order) + tenant-scoped
  executors bound to a `ScanContext` (`user_id`, `scan_run_id`, db, gmail,
  candidates). Tools: `list_candidate_emails`, `get_email`, `upsert_subscription`,
  `record_payment`, `flag_missing_payment`, `finish_scan`.
- `agent/loop.py` — `run_agent_loop` (the manual loop with `MAX_ITERATIONS`) and
  `run_scan_job` (background orchestration: decrypt token → Gmail candidate search
  → loop → update `scan_run` + `last_synced_at`).
- Wire `POST /api/scans` to create a `scan_run` and schedule the job.
- Tests with Anthropic + Gmail mocked (no network): tool effects + tenant
  scoping, loop terminates on `end_turn` / `MAX_ITERATIONS` / `refusal`, endpoint
  creates a run / 400 without a connected account.

Out of scope:

- Dashboard aggregation (Phase 5) and the frontend (Phase 6).
- Scheduled re-scans; a durable worker queue (local = FastAPI background task).
- Live LLM/Gmail calls in tests or CI.

## Approach

- **Model rules** (`.claude/rules/llm-usage.md`): `claude-opus-4-8`,
  `thinking={"type": "adaptive"}`, `max_tokens=16000`, no sampling params, no
  prefills. Check `stop_reason` before reading content; append the full
  `response.content` (preserving `tool_use`/thinking blocks); return one
  `tool_result` per `tool_use` id; parse tool input with `json.loads` when it
  arrives as a string.
- **Prompt caching**: stable system prompt + deterministic tool list as the
  cached prefix; volatile per-scan content (candidate summary, today's date) goes
  in the user turn.
- **Tenant isolation** (`.claude/rules/security.md`): every write executor filters
  on `ctx.user_id`; `record_payment`/`flag_missing_payment` reject a
  `subscription_id` that isn't the user's. Only `source_message_id` is stored
  (dedup), never email bodies.
- **Testability**: `run_agent_loop(ctx, client)` takes the Anthropic client as an
  argument so tests inject a fake that returns scripted responses; `ScanContext`
  takes a Gmail client so tests inject a fake. The sync Gmail SDK runs via
  `run_in_threadpool`.

## Steps

1. Plan (this file) + branch `feat/agent`.
2. `integrations/anthropic_client.py`.
3. `agent/prompts.py`, `agent/tools.py`, `agent/loop.py`.
4. Wire `POST /api/scans` (create run + background task).
5. Tests: `test_agent_tools.py`, `test_agent_loop.py`, `test_scans.py`.
6. `ruff check` / `ruff format`, run the full suite.
7. Update `.claude/progress.md`, open PR.

## Acceptance criteria

- A scan over fixture emails populates `subscriptions` + `payments` scoped to the
  user; the loop terminates on `end_turn`, on `MAX_ITERATIONS`, and on a refusal
  (no raise).
- `POST /api/scans` returns a `scan_run_id` (202) and 400 without a connected
  Gmail account; `GET /api/scans/{id}` reports status.
- `uv run pytest` green and `uv run ruff check` clean; all LLM/Gmail boundaries
  mocked.
