---
name: agent-tooling
description: How the subscription-detection agent is built in this repo — the agentic loop, tool schemas/executors, prompts, and how a scan runs. Read this before changing anything under backend/app/agent/.
---

# Agent tooling (this repo's agent architecture)

The agent is Claude Opus 4.8 driving a set of tools through a manual agentic
loop. It reads candidate emails and records subscriptions + payments. Full
context is in `docs/architecture.md` §2; this skill is the working playbook.

## Files

- `backend/app/agent/loop.py` — the agentic loop (the orchestrator).
- `backend/app/agent/tools.py` — tool JSON schemas + Python executors.
- `backend/app/agent/prompts.py` — the stable system prompt.
- `backend/app/integrations/anthropic_client.py` — SDK client wrapper.
- `backend/app/integrations/gmail.py` — Gmail candidate search + fetch.

## The loop, precisely

1. Build `messages`: system prompt + a user turn describing the scan task and a
   compact summary of candidate emails (ids, senders, subjects only).
2. Call `messages.create(model="claude-opus-4-8", max_tokens=16000,
   thinking={"type": "adaptive"}, tools=TOOL_SCHEMAS, messages=messages)`.
3. Inspect `response.stop_reason`:
   - `end_turn` → done.
   - `refusal` → log and stop the scan gracefully.
   - otherwise → there are `tool_use` blocks.
4. Append the full `response.content` (keep `tool_use` blocks intact).
5. Execute each `tool_use` block via its executor; collect one `tool_result`
   per `tool_use` id (set `is_error: true` on failures with a message).
6. Append a user turn with the `tool_result` blocks; loop.
7. Enforce `MAX_ITERATIONS` to bound cost.

## Adding or changing a tool

Use the `/new-tool` command (`.claude/commands/new-tool.md`). Rules:

- Every write tool executor is bound to `user_id` and `scan_run_id` from the
  scan context — it must never write rows for another tenant.
- Read-only tools (`list_candidate_emails`, `get_email`) are parallel-safe;
  write tools are executed serially.
- Validate inputs in the executor. Return concise, structured results — the
  model reads them.
- Keep the schema list deterministic and stable (prompt caching depends on it).

## Cost discipline

- The Gmail heuristic pre-filter (`integrations/gmail.py`) narrows candidates
  before the LLM sees anything. Don't bypass it by dumping the whole inbox into
  the prompt.
- `get_email` returns plaintext body trimmed to a sane length; never the raw
  MIME.
- Reuse the same system prompt + tool order across scans so the cached prefix
  is reused.

## Testing

Mock the Anthropic client and Gmail client. Assert that:
- the loop terminates on `end_turn` and on `MAX_ITERATIONS`,
- a `tool_use` for `record_payment` results in a `payments` row scoped to the
  right user,
- a refusal stops the scan without raising.
