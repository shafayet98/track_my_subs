# Backend — track_my_subs

FastAPI + async SQLAlchemy + Postgres. See `../docs/architecture.md` for the
full design and `../CLAUDE.md` for conventions.

## Setup

```bash
cp ../.env.example ../.env        # fill in secrets
# start a local Postgres and create the DB, e.g.:
#   brew services start postgresql@16 && createdb track_my_subs
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Health check: `GET http://localhost:8000/api/health`.
API docs (dev): `http://localhost:8000/docs`.

## Layout

```
app/
  main.py            FastAPI app, CORS, router wiring
  core/              config, db session, security (JWT + hashing + token crypto)
  models/            SQLAlchemy ORM models
  schemas/           Pydantic request/response models
  api/               routers (auth, accounts, scans, dashboard) + deps
  agent/             LLM agent: loop, tools, prompts        (added later)
  integrations/      gmail + anthropic clients              (added later)
  services/          business logic / dashboard aggregation (added later)
alembic/             migrations
```

## Tests

```bash
uv run pytest
```

Tests use SQLite (aiosqlite) and mock the Gmail/Anthropic boundaries — no
network calls.
