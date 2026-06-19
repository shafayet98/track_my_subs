---
description: Investigate an issue and report root cause + fix options (read-only — no fix).
argument-hint: <the issue / bug / symptom to investigate>
---

# /investigate

Investigate the issue described in `$ARGUMENTS` (ask for details if empty). The
goal is a clear **root cause**, not a fix — this command is **read-only**: do not
change application code unless the user explicitly asks afterward.

Do the following:

1. **Frame the problem.** Restate the symptom precisely: what's observed, where
   (frontend / API / agent / infra), and when it started if known. Note the
   expected vs actual behavior.

2. **Gather evidence** before theorizing:
   - **Code** — read the relevant paths (use search/Explore for breadth).
   - **History** — `git log`/`git blame` around the suspect code; recent changes
     in `.claude/progress.md`.
   - **Runtime** — if it's a deployed/runtime issue, pull logs (e.g. ECS via
     CloudWatch with `aws logs tail ... --profile audrie98`), health checks, and
     stack/service state. Reproduce locally only if safe and useful.
   - Respect `.claude/rules/security.md`: don't print secrets or email content.

3. **Form and test a hypothesis.** State the most likely cause, then confirm it
   against the evidence (a specific line, log entry, config value, or commit).
   Rule out plausible alternatives rather than stopping at the first guess.

4. **Report findings:**
   - **Root cause** — the precise why, citing `file:line` / log / commit.
   - **Impact / blast radius** — who/what is affected.
   - **Fix options** — one or more, with trade-offs and a recommendation.
   - **Confidence** — and what would raise it if you're not certain.

5. **Stop.** Don't implement the fix. If the user wants it done, follow up with
   `/plan` (if non-trivial) then `/coding`, or a direct fix for a one-liner.
