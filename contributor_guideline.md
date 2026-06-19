# Contributor Guideline

Welcome — thanks for working on **track_my_subs**. This guide is the practical
how-to for contributing. It complements the deeper docs: the engineering rules in
[`.claude/rules/`](.claude/rules/) are authoritative; this page ties them into a
workflow.

> **This app reads people's email.** Privacy is a hard constraint, not a
> nice-to-have. Read [`.claude/rules/security.md`](.claude/rules/security.md)
> before touching anything that handles Gmail, secrets, or user data.

---

## 1. What you need to contribute

- **GitHub access** — ask the owner to add you as a repo collaborator. That's
  enough to open PRs.
- **Local tooling** — Python 3.12 + [`uv`](https://github.com/astral-sh/uv),
  Node 20+, and a local Postgres (or SQLite for quick iteration).
- **Your own keys** for local runs — an `ANTHROPIC_API_KEY`, and (only if you're
  testing Gmail) a Google OAuth client or being added as a **test user** on the
  project's OAuth consent screen. Generate your own `JWT_SECRET` /
  `TOKEN_ENCRYPTION_KEY` for dev.
- **You do NOT need AWS access** to contribute. Deployment is automated — merging
  to `main` deploys via the CD pipeline. You'd only need an AWS login (via IAM
  Identity Center) to run `aws`/`cdk` by hand.

See the [README](README.md#getting-started-local-development) for setup commands.

## 2. The workflow

Work is **branch-per-change → PR into `main`**. Never commit directly to `main`.
The repo provides Claude Code slash commands that encode the flow:

| Step | Command | What it does |
| --- | --- | --- |
| Plan | `/plan <task>` | Write a short plan under `docs/plans/` (no code, no branch). |
| Build | `/coding` | Fresh `main` → new branch → implement → tests → fresh sub-agent review. |
| Ship | `/cpr` | Commit, push, open a PR against `main`. |
| Debug | `/investigate <issue>` | Read-only root-cause analysis with fix options. |

You don't have to use the commands, but follow the same shape by hand:

1. **Branch off the latest `main`:** `git checkout main && git pull --ff-only`,
   then `git checkout -b <type>/<short-name>`.
   Branch types: `feat/`, `fix/`, `chore/` (see
   [`git-workflow.md`](.claude/rules/git-workflow.md)).
2. **Plan first for non-trivial work** — a short file under `docs/plans/`
   (Goal / Scope / Approach / Steps / Acceptance). See
   [`planning.md`](.claude/rules/planning.md).
3. **Implement**, matching the surrounding style.
4. **Add tests** and make the checks green (section 4).
5. **Add a `progress.md` entry** (section 5) — required before the PR.
6. **Open a PR** into `main`. Keep PRs focused — one logical change each.

## 3. Coding standards (the short version)

Full detail: [`coding-standards.md`](.claude/rules/coding-standards.md).

- **Backend (Python 3.12):** type hints everywhere; `async def` for I/O (DB,
  Gmail, Anthropic). Layering is `api/` (thin routers) → `services/` (business
  logic) → `models/` (ORM) — routers don't contain SQL or LLM calls. Config flows
  through `core/config.py` (no scattered `os.getenv`). Lint/format with `ruff`.
- **Frontend (TS/React):** function components + hooks; one typed API client in
  `src/api/` (components never `fetch` directly); keep response types in sync with
  the backend schemas; Recharts for charts.
- **General:** small focused modules; validate at boundaries, trust internal code;
  don't add abstractions for cases that can't happen.

### Working with the LLM / agent

If you touch anything that calls Claude, follow
[`llm-usage.md`](.claude/rules/llm-usage.md):

- Model is always `claude-opus-4-8` with `thinking={"type": "adaptive"}`.
- **No** `temperature`/`top_p`/`top_k`, **no** `budget_tokens`, **no** assistant
  prefills (all return 400 on Opus 4.8).
- Parse tool inputs with `json.loads`; keep the system prompt and tool list stable
  (prompt caching). When unsure about the API, consult the `claude-api` skill.

### Privacy & security (non-negotiable)

From [`security.md`](.claude/rules/security.md):

- Gmail scope is **read-only** (`gmail.readonly`) — never request write/send/delete.
- **Store parsed facts only** — never persist raw email bodies or full headers.
- Every user-data query filters on the authenticated `user_id`; agent tools are
  bound to the current `user_id` / `scan_run_id` (no cross-tenant access).
- Secrets live server-side only; encrypt OAuth refresh tokens at rest; never log
  PII or email content; never commit `.env` or keys.

## 4. Tests & checks

Everything below must pass (CI enforces it on PRs):

```bash
# backend
cd backend
uv run ruff check . && uv run ruff format --check .
uv run pytest -q

# frontend (if changed)
cd frontend
npm run lint && npm run build

# infra (if changed)
cd infra
uv run ruff check . && uv run cdk synth
```

Mock Gmail and Anthropic **at the integration boundary** in tests — CI makes no
network calls. Cover new behavior and tenant isolation where relevant.

## 5. Before every PR: update `progress.md`

Add an entry at the **top** of [`.claude/progress.md`](.claude/progress.md) using
the documented format (What / Why / Touches / Verified / Follow-ups). A PR without
a progress entry is incomplete. (`/cpr` and `/update-progress` help with this.)

## 6. Commits & PRs

- **Commit messages:** imperative subject, body explaining *why*. When the work
  was done with Claude, end with the
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.
- **PRs:** target `main`, summarize the change, link the progress entry, and list
  what you verified. CI (backend / frontend / infra) must be green.
- **Don't commit:** `.env`, secrets, OAuth tokens, API keys, build artifacts.

## 7. ⚠️ Merging deploys to production

CD runs on **every merge to `main`** ([`.github/workflows/cd.yml`](.github/workflows/cd.yml)):
it builds the image, `cdk deploy`s, runs migrations, and ships the SPA. So:

- Make sure CI is green and the change is genuinely ready before merging.
- **Database migrations must be backward-compatible** (additive) — they run after
  the service rolls onto the new image.
- If a deploy goes red, check the **Actions** tab (and `/investigate` is your
  friend).

## 8. Where to look

- Product + architecture → [`README.md`](README.md), [`docs/architecture.md`](docs/architecture.md)
- The build plan / what shipped → [`docs/roadmap.md`](docs/roadmap.md), [`.claude/progress.md`](.claude/progress.md)
- Agent internals / adding a tool → [`.claude/skills/`](.claude/skills/), [`.claude/commands/new-tool.md`](.claude/commands/new-tool.md)
- Deploy runbook → [`infra/README.md`](infra/README.md)

Happy shipping. 🚀
