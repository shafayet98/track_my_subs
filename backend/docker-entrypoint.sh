#!/bin/sh
# Compose DATABASE_URL from the individual DB_* parts injected by ECS (host/port/
# name as env, user/password from Secrets Manager) so the password never sits in
# a plaintext env var. If DATABASE_URL is already set (e.g. local dev), use it.
set -e

if [ -z "$DATABASE_URL" ] && [ -n "$DB_HOST" ]; then
  export DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
fi

exec "$@"
