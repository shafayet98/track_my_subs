"""Test fixtures: ephemeral SQLite DB, ASGI client, and user helpers.

No network calls. Each test gets a fresh in-memory database.
"""

import os
import uuid

from cryptography.fernet import Fernet

# Set required settings BEFORE importing the app (settings are read at import).
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401  (register models on Base.metadata)
from app.core.db import Base, get_db  # noqa: E402
from app.core.security import decode_access_token  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def session(session_factory):
    """Direct DB access for seeding rows in tests."""
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
def make_user(client):
    """Register a user via the API; returns token, auth headers, and user_id."""

    async def _make(email: str, password: str = "password123", name: str | None = None) -> dict:
        r = await client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "name": name},
        )
        assert r.status_code == 201, r.text
        token = r.json()["access_token"]
        return {
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
            "user_id": uuid.UUID(decode_access_token(token)),
        }

    return _make
