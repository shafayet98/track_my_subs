---
description: Scaffold a new tool for the subscription-detection agent (schema + executor + wiring + test).
---

# /new-tool

Add a new tool to the agent. Follow the existing patterns in
`backend/app/agent/tools.py` and the `agent-tooling` skill.

Given the tool's purpose in `$ARGUMENTS` (or ask if not provided), do all of:

1. **Schema** — add a JSON schema entry to `TOOL_SCHEMAS` in
   `backend/app/agent/tools.py`:
   - clear `name` (snake_case), a description that says *when* to use it,
     and a precise `input_schema` (typed properties, `required`, descriptions).
   - keep the list order stable (append) — prompt caching depends on it.

2. **Executor** — implement the Python function that runs the tool:
   - signature receives the validated input plus the scan context
     (`user_id`, `scan_run_id`, db session).
   - **write tools must scope every row to `user_id`/`scan_run_id`.**
   - validate inputs; return a concise, structured result string/dict the model
     can read. On failure, return an error result (the loop marks
     `is_error: true`).

3. **Dispatch** — register the executor in the tool-name → function map used by
   `loop.py`. Mark read-only tools as parallel-safe; write tools serial.

4. **Test** — add a `pytest` case mocking the Anthropic + Gmail clients that
   asserts the tool's effect (e.g. a row created with correct tenant scoping).

5. **Docs** — if the tool changes the agent's capabilities meaningfully, update
   the tool table in `docs/architecture.md` §2.4.

Confirm the model (`claude-opus-4-8`) and loop conventions in
`.claude/rules/llm-usage.md` are respected.
