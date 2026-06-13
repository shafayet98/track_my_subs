# Rule: Git workflow

Repo: https://github.com/shafayet98/track_my_subs

## Branching

- Never commit directly to `main`. Branch per change:
  `feat/<short-name>`, `fix/<short-name>`, `chore/<short-name>`.
- Keep PRs focused — one logical change per PR.

## Before every PR — update progress.md (required)

Before opening a pull request, **add an entry to `.claude/progress.md`** at the
top, using the entry format documented in that file (What / Why / Touches /
Follow-ups). This is part of the change and belongs in the same PR. A PR without
a progress entry is incomplete.

If the PR completes a roadmap item in `progress.md`, check it off.

## Commits & PRs

- Only commit or push when the owner asks.
- Commit messages: imperative mood, short subject, body explaining *why*.
- End commit messages with the Co-Authored-By trailer for Claude when applicable.
- Use the `gh` CLI for PR creation. PR description should summarize the change
  and link the progress entry.

## Don't commit

- `.env`, secrets, OAuth tokens, API keys.
- Build artifacts, `node_modules/`, `__pycache__/`, virtualenvs.
- Keep `.gitignore` current for both `backend/` and `frontend/`.
