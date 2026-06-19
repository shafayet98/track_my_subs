---
description: Commit, push, and open a PR against main for the current branch.
argument-hint: <optional PR title / note>
---

# /cpr

Commit the current work, push the branch, and open a pull request against `main`.
Use `$ARGUMENTS` as the PR title/intent if provided; otherwise derive it from the
diff. Follow `.claude/rules/git-workflow.md`.

Do the following:

1. **Safety checks.**
   - Confirm you're **not on `main`** (never commit directly to `main`). If you
     are, stop and tell the user to run `/coding` first (or create a branch).
   - `git status` / `git diff` to review what will be committed. Don't commit
     `.env`, secrets, tokens, build artifacts, or anything `.gitignore` covers.

2. **Progress entry (required).** Ensure `.claude/progress.md` has a top entry for
   this change (What / Why / Touches / Verified / Follow-ups). If missing, add it
   now — see `/update-progress`. A PR without a progress entry is incomplete.

3. **Commit.** Stage the change and commit with an imperative subject and a body
   explaining *why*. End the message with:
   `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

4. **Push** the branch (`git push -u origin <branch>`).

5. **Open the PR** with `gh pr create --base main`, a title and a body that
   summarize the change, link the progress entry, list verification done, and note
   follow-ups. End the body with:
   `🤖 Generated with [Claude Code](https://claude.com/claude-code)`

6. **Report the PR URL.** Do not merge — leave that to the user.
