---
description: Plan a task and save the plan under docs/plans/ (planning only — no code).
argument-hint: <what to build / the task>
---

# /plan

Produce a written plan for the task in `$ARGUMENTS` (ask for the task if it's
empty). This command **plans only — it writes no application code and creates no
branch.** It implements step 2 of `.claude/rules/planning.md`; `/coding` does the
branching + implementation afterward.

Do the following:

1. **Understand the task.** Restate the goal in one or two sentences. If anything
   material is ambiguous (scope, approach, a product decision), ask before
   writing the plan rather than guessing.

2. **Explore the codebase** enough to ground the plan: the files you'll touch,
   relevant rules in `.claude/rules/`, any related skill in `.claude/skills/`, and
   how similar work was done before (`.claude/progress.md`, existing `docs/plans/`).

3. **Write the plan file** under **`docs/plans/`**, named after the task in
   `Title_Case_With_Underscores.md` form (e.g. `Add_Scheduled_Rescans.md`). Keep
   it short and practical — a thinking aid, not a spec. Cover:
   - **Goal** — what we're building and why.
   - **Scope / out of scope** — what this does and explicitly doesn't.
   - **Approach** — key files, design decisions, anything non-obvious.
   - **Steps** — the ordered work.
   - **Acceptance criteria** — how we'll know it's done (the "done when").

4. **Stop and report.** Print the plan path and a short summary. Do **not** start
   coding — that's `/coding`. Leave the plan file uncommitted in the working tree;
   `/coding` will carry it onto the new branch.
