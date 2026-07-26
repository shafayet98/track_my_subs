"""Auth endpoint tests: register, login, /me, and guards."""


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_register_returns_token_and_me_works(client, make_user):
    user = await make_user("a@b.com", name="A")
    r = await client.get("/api/auth/me", headers=user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "a@b.com"
    assert body["name"] == "A"


async def test_register_duplicate_email_conflicts(client, make_user):
    await make_user("dup@b.com")
    r = await client.post(
        "/api/auth/register", json={"email": "dup@b.com", "password": "password123"}
    )
    assert r.status_code == 409


async def test_register_rejects_short_password(client):
    r = await client.post("/api/auth/register", json={"email": "x@b.com", "password": "short"})
    assert r.status_code == 422  # pydantic min_length


async def test_login_ok_and_wrong_password(client, make_user):
    await make_user("c@b.com", password="password123")
    ok = await client.post("/api/auth/login", json={"email": "c@b.com", "password": "password123"})
    assert ok.status_code == 200
    assert "access_token" in ok.json()

    bad = await client.post(
        "/api/auth/login", json={"email": "c@b.com", "password": "wrong-password"}
    )
    assert bad.status_code == 401


async def test_login_unknown_user(client):
    r = await client.post(
        "/api/auth/login", json={"email": "ghost@b.com", "password": "whatever123"}
    )
    assert r.status_code == 401


async def test_me_requires_valid_token(client):
    assert (await client.get("/api/auth/me")).status_code == 401
    bad = await client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert bad.status_code == 401


async def test_login_case_insensitive(client, make_user):
    """Register with mixed-case email; login with lowercase should succeed."""
    await make_user("User@Example.com", password="password123")
    r = await client.post(
        "/api/auth/login", json={"email": "user@example.com", "password": "password123"}
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


async def test_register_duplicate_different_case(client, make_user):
    """Registering same email with different case should return 409."""
    await make_user("User@Example.com")
    r = await client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert r.status_code == 409


async def test_login_mixed_case_for_lowercase_account(client, make_user):
    """Login with mixed-case email should succeed when account was registered lowercase."""
    await make_user("user@example.com", password="password123")
    r = await client.post(
        "/api/auth/login", json={"email": "User@Example.com", "password": "password123"}
    )
    assert r.status_code == 200
    assert "access_token" in r.json()
