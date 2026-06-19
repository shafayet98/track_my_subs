---
description: Implement a planned task on a fresh branch, with tests and a sub-agent review.
argument-hint: <task / plan name> (optional if obvious from context)
---

# /coding

Implement the task described by its plan in `docs/plans/`. If `$ARGUMENTS` names a
task/plan, use that plan; otherwise use the most relevant plan (ask if unclear).
This command does **not** commit, push, or open a PR — that's `/cpr`.

Do the following, in order:

1. **Start from a fresh main.**
   - If not on `main`, run `git checkout main`.
   - `git pull --ff-only` to update to the latest.
   - (Any uncommitted plan file from `/plan` is untracked and will carry over.)

2. **Read the plan** for this task in `docs/plans/`. Treat its Scope and
   Acceptance criteria as the contract.

3. **Create a branch** named for the task per `.claude/rules/git-workflow.md`:
   `feat/<short-name>`, `fix/<short-name>`, or `chore/<short-name>`.

4. **Implement** per the plan and `.claude/rules/coding-standards.md` (async
   backend, layering api→services→models, typed, match surrounding style). Follow
   `.claude/rules/llm-usage.md` and `.claude/rules/security.md` where relevant.

5. **Write tests** (`pytest`, mocking Gmail/Anthropic at the boundary) covering the
   new behavior and tenant isolation where applicable.

6. **Run the checks until green:** `uv run ruff check .`, `uv run ruff format .`,
   `uv run pytest -q` in `backend/` (and `npm run lint && npm run build` in
   `frontend/` if the frontend changed; `uv run cdk synth` if `infra/` changed).

7. **Spawn a fresh sub-agent to review** (Agent tool, clean context). Give it the
   plan and the working-tree diff (`git diff`) and ask it to check: correctness
   and edge cases, test coverage, adherence to `.claude/rules/*`, and whether the
   Acceptance criteria are met. Relay its findings, then **address the blocking
   ones** and re-run the checks.

8. **Stop and report:** branch name, what changed, test/lint results, and the
   review outcome. Leave everything staged-or-unstaged but **uncommitted** — run
   `/cpr` when ready to ship.
