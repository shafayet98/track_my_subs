# Rule: Coding standards

## Backend (Python)

- Python 3.12. Use type hints everywhere; prefer `async def` for I/O paths
  (DB, Gmail, Anthropic).
- FastAPI for the API, Pydantic v2 for request/response schemas, SQLAlchemy 2.0
  async ORM, Alembic for migrations.
- Layering: `api/` (routers, thin) → `services/` (business logic) →
  `models/` (ORM). Routers should not contain SQL or LLM calls directly.
- Config via a single `core/config.py` `Settings` (pydantic-settings) reading
  the environment. No `os.getenv` scattered around.
- Dependency management with `uv` (`pyproject.toml`). Lint/format with `ruff`.
- Tests with `pytest`. Mock Gmail and Anthropic at the integration boundary so
  tests don't make network calls.

## Frontend (TypeScript/React)

- React + Vite + TypeScript, function components + hooks.
- One typed API client in `src/api/`; components call it, never `fetch`
  directly. Keep API response types in sync with the backend Pydantic schemas.
- Recharts for charts. Keep presentational components dumb; fetch in
  page-level components or hooks.

## General

- Small, focused modules. Match the style of surrounding code.
- Don't add abstractions, helpers, or error handling for cases that can't
  happen. Validate at boundaries (user input, external APIs), trust internal
  code.
- Keep the agent's system prompt and tool schemas stable for prompt caching —
  changes there are deliberate, not incidental.
