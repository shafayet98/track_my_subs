# Backend image for ECS Fargate. Build for linux/amd64 (matches the Fargate
# default x86_64 runtime):
#   docker build --platform linux/amd64 -t track-my-subs-api backend/
FROM python:3.12-slim

# uv for dependency install (matches local dev).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install deps first (cached unless pyproject changes), then the app.
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

COPY . .
RUN uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
