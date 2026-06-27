# Fix a low-effort issue

> Requirement spec. This will eventually run as a scheduled cloud agent, but for
> now it is just the description of what that task must do.

## Goal

Autonomously pick up one small, well-scoped issue and carry it all the way to an
open pull request — investigated, planned (with review), implemented, tested,
independently verified, and logged.

## Requirements

1. **Pick the issue.** From the repo's open issues labeled `effort:low`, choose
   the **newest** one. If there are none, stop — nothing to do.
2. **Branch.** Create a `claude/<short-slug>` branch for the work.
3. **Investigate** the issue first — understand the root cause and what the fix
   needs to touch before planning. (You may use `/investigate`.)
4. **Plan** the fix. (You may use `/plan`.)
5. **Review the plan.** Spawn a sub-agent to review the plan. Do not proceed
   until the sub-agent has verified it.
6. **Save the plan** under `docs/plans/` once the sub-agent has approved it.
7. **Implement** the code according to the approved plan. (You may use
   `/coding`.)
8. **Add a test** that covers the fix.
9. **Run the full test suite.**
10. **Independent verification before declaring done.** Spawn a sub-agent to
    independently confirm that (a) the tests pass and (b) the issue's described
    behaviour is actually met.
11. **If verification fails**, fix the problem and re-run — loop back through
    implement → test → verify until it passes.
12. **Update `.claude/progress.md`** with an entry for the change.
13. **Commit, push, and raise a PR** against the `main` branch. (You may use
    `/cpr`.)

## Done

Done when a pull request is open against `main` that fixes the chosen
`effort:low` issue, includes a covering test, has a passing full suite, has been
independently verified by a sub-agent, has its plan saved under `docs/plans/`,
and has a matching `.claude/progress.md` entry.

## Notes

- During the session you may use the repo's custom commands where helpful:
  `/investigate`, `/plan`, `/coding`, `/cpr`.
- Follow the repo rules these commands already encode: plan before coding
  (`.claude/rules/planning.md`), branch + progress entry per PR
  (`.claude/rules/git-workflow.md`), and the coding standards.
- Scope is a single issue per run. Don't batch multiple issues into one PR.
