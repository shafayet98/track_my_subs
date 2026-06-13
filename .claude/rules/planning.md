# Rule: Plan before coding

Before starting any new piece of work (a roadmap phase or a standalone task),
write a short plan **first**, then implement.

## How

1. Create the feature branch named after the task
   (e.g. `feat/verify-harden-auth`).
2. Add a plan file under **`docs/plans/`** named after the task in
   `Title_Case_With_Underscores.md` form — e.g. `Verify_harden_auth.md`.
3. The plan should cover, briefly:
   - **Goal** — what we're building and why.
   - **Scope / out of scope** — what this task does and explicitly doesn't.
   - **Approach** — key files, design decisions, anything non-obvious.
   - **Steps** — the ordered work.
   - **Acceptance criteria** — how we know it's done (the roadmap "done when").
4. Only after the plan exists, start coding.

## Notes

- Keep plans short and practical — they're a thinking aid, not a spec.
- One plan file per task; it stays in the repo as a record of intent.
- This complements `git-workflow.md` (update `progress.md` before the PR) and
  `docs/roadmap.md` (the high-level phase list). Plan files are the per-task
  detail under a roadmap phase.
