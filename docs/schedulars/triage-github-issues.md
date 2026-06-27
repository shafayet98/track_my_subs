# Scheduled task: Triage all open GitHub issues (apply labels)

**Purpose:** Walk every open issue in the repo, analyze each one, and **apply
labels** for **risk**, **effort**, and **priority** (each high / medium / low)
directly to the issue, so the ratings are visible at a glance in the GitHub
issues list. Re-running keeps each issue's labels current.

**Repo:** https://github.com/shafayet98/track_my_subs
**Cadence:** intended to run on a schedule (e.g. daily). Each run re-evaluates
the current open issues and updates their labels.

---

## Steps

1. **Fetch all open issues** with the `gh` CLI (include body, labels, comments,
   author, and age):

   ```bash
   gh issue list --repo shafayet98/track_my_subs --state open --limit 200 \
     --json number,title,body,labels,author,createdAt,updatedAt,comments
   ```

   If there are zero open issues, there is nothing to do — stop.

2. **Ensure the triage label set exists.** Create any that are missing (idempotent
   — ignore "already exists" errors). Use these exact names and colors:

   ```bash
   gh label create "risk:high"      --repo shafayet98/track_my_subs --color B60205 --description "Triage: risk high"   --force
   gh label create "risk:medium"    --repo shafayet98/track_my_subs --color D93F0B --description "Triage: risk medium" --force
   gh label create "risk:low"       --repo shafayet98/track_my_subs --color FBCA04 --description "Triage: risk low"    --force
   gh label create "effort:high"    --repo shafayet98/track_my_subs --color 0E8A16 --description "Triage: effort high"   --force
   gh label create "effort:medium"  --repo shafayet98/track_my_subs --color 1D76DB --description "Triage: effort medium" --force
   gh label create "effort:low"     --repo shafayet98/track_my_subs --color C5DEF5 --description "Triage: effort low"    --force
   gh label create "priority:high"   --repo shafayet98/track_my_subs --color 5319E7 --description "Triage: priority high"   --force
   gh label create "priority:medium" --repo shafayet98/track_my_subs --color 8250DF --description "Triage: priority medium" --force
   gh label create "priority:low"    --repo shafayet98/track_my_subs --color C2A0FC --description "Triage: priority low"    --force
   ```

3. **Read the context you need to judge each issue.** For every issue, skim the
   title + body and, where it helps, look at the referenced code in this repo
   (files named in the issue) and `docs/architecture.md` / `docs/roadmap.md` so
   ratings reflect reality, not just the issue text. Do **not** modify any code.

4. **Rate each issue** on the three axes using the rubric below. Pick the single
   best-fit level for each; when torn between two, round toward the more cautious
   (higher risk / higher effort).

5. **Apply the labels to each issue.** First remove any existing triage labels so
   re-runs stay clean, then add the three new ones. For an issue with no current
   triage labels the `--remove-label` calls are no-ops — that's fine.

   ```bash
   # remove stale triage labels (ignore errors if not present)
   gh issue edit <N> --repo shafayet98/track_my_subs \
     --remove-label "risk:high"   --remove-label "risk:medium"   --remove-label "risk:low" \
     --remove-label "effort:high" --remove-label "effort:medium" --remove-label "effort:low" \
     --remove-label "priority:high" --remove-label "priority:medium" --remove-label "priority:low"

   # add the chosen ratings
   gh issue edit <N> --repo shafayet98/track_my_subs \
     --add-label "risk:<level>" --add-label "effort:<level>" --add-label "priority:<level>"
   ```

6. **Report what you did** in your final message: a short table of
   `# | title | risk | effort | priority` for every issue you labeled. This is
   chat output only — do **not** write any report file or open a PR.

7. **Scope guardrails.** Only ever touch the nine `risk:` / `effort:` /
   `priority:` labels. Do **not** modify application code, edit issue titles or
   bodies, close/reopen issues, add comments, or change any other (non-triage)
   labels.

---

## Rating rubric

Rate every issue on all three axes. Levels are **high / medium / low**.

### Risk — what could go wrong if we ship a change for this issue

- **High** — touches auth, OAuth scopes, token storage/encryption, tenant
  isolation, money/payment math, the agent's tool executors, DB migrations that
  alter existing data, or anything in `.claude/rules/security.md`. A mistake here
  leaks data, crosses tenants, or corrupts records.
- **Medium** — changes shared backend services, agent prompts/schemas (prompt-
  caching sensitive), public API shapes, or migrations that only add nullable
  columns. Contained blast radius but worth care.
- **Low** — docs, copy, frontend-only cosmetic/UX, isolated additive code with
  tests, infra changes behind a flag. Easy to reverse, no data at stake.

### Effort — how much work to resolve it well (code + tests + review)

- **High** — multi-file or cross-layer (frontend + backend + infra), new agent
  tool, schema/migration + backfill, or anything needing a design decision first.
  Roughly > ~1 day.
- **Medium** — a focused feature or fix spanning a couple of files with tests.
  Roughly a few hours.
- **Low** — one-liner, copy/doc tweak, config bump, small contained fix.
  Roughly < ~1 hour.

### Priority — how soon it should be done

- **High** — broken in production, security/privacy exposure, blocks other work,
  or blocks a roadmap milestone the owner is actively pushing.
- **Medium** — meaningful improvement or non-blocking bug; should happen soon but
  nothing is on fire.
- **Low** — nice-to-have, polish, speculative, or deferred until later phases.

> Priority is a judgment that weighs risk, effort, user impact, and roadmap fit —
> it is **not** a formula. A high-risk, high-effort issue can still be low
> priority if nobody needs it yet; a low-effort issue can be high priority if it
> unblocks everything else.

## Conventions

- If an issue is missing information needed to rate it, rate what you can with the
  cautious default and note the uncertainty in your final-message table.
- Never include secrets, tokens, or email content anywhere.
