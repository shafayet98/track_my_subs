"""Tenant isolation: a user must never read another user's data."""

from app.models import EmailAccount, ScanRun, Subscription


async def test_user_cannot_read_other_users_data(client, session, make_user):
    a = await make_user("a@x.com")
    b = await make_user("b@x.com")

    # Seed data owned by user A directly in the DB.
    sub = Subscription(
        user_id=a["user_id"],
        merchant_name="Netflix",
        billing_cycle="monthly",
        amount=15.0,
        currency="USD",
        status="active",
    )
    scan = ScanRun(user_id=a["user_id"], status="succeeded")
    acct = EmailAccount(user_id=a["user_id"], provider="gmail", email_address="a@gmail.com")
    session.add_all([sub, scan, acct])
    await session.commit()
    await session.refresh(sub)
    await session.refresh(scan)

    # --- User B sees none of A's data ---
    r = await client.get("/api/subscriptions", headers=b["headers"])
    assert r.status_code == 200 and r.json() == []

    r = await client.get(f"/api/subscriptions/{sub.id}", headers=b["headers"])
    assert r.status_code == 404

    r = await client.get(f"/api/scans/{scan.id}", headers=b["headers"])
    assert r.status_code == 404

    r = await client.get("/api/accounts", headers=b["headers"])
    assert r.status_code == 200 and r.json() == []

    # --- User A sees exactly its own ---
    r = await client.get("/api/subscriptions", headers=a["headers"])
    assert r.status_code == 200 and len(r.json()) == 1

    r = await client.get(f"/api/subscriptions/{sub.id}", headers=a["headers"])
    assert r.status_code == 200

    r = await client.get(f"/api/scans/{scan.id}", headers=a["headers"])
    assert r.status_code == 200

    r = await client.get("/api/accounts", headers=a["headers"])
    assert r.status_code == 200 and len(r.json()) == 1
