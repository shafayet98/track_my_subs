---
description: Add a progress.md entry for the current change, ready for a PR.
---

# /update-progress

Prepare `.claude/progress.md` for a pull request. This is required before every
PR (see `.claude/rules/git-workflow.md`).

Do the following:

1. Determine what changed on the current branch:
   - run `git diff main...HEAD --stat` (and `git log main..HEAD --oneline`) to
     see the scope.
2. Add a new entry at the **top** of the entries section in
   `.claude/progress.md` using the documented format:

   ```
   ## <today's date> — <PR title> (#<branch or PR>)

   **What:** one-paragraph summary.
   **Why:** which roadmap item / motivation.
   **Touches:** key files/areas.
   **Follow-ups:** anything deferred.
   ```

3. If the change completes a roadmap checklist item at the bottom of
   `progress.md`, check it off (`[x]`).
4. Show the new entry for confirmation. Do not commit or push unless the owner
   asks.

If `$ARGUMENTS` contains a PR title, use it; otherwise infer one from the diff.
