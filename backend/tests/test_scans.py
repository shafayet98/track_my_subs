"""Scan endpoint tests. The background scan job is patched out (no LLM/Gmail)."""

from sqlalchemy import select

from app.core.security import encrypt_token
from app.models import EmailAccount, ScanRun


async def test_start_scan_requires_connected_account(client, make_user):
    user = await make_user("noacct@example.com")
    r = await client.post("/api/scans", headers=user["headers"])
    assert r.status_code == 400


async def test_start_scan_creates_run_and_schedules_job(client, make_user, session, monkeypatch):
    import app.api.scans as scans_mod

    scheduled = []

    async def fake_job(scan_id, user_id):
        scheduled.append((scan_id, user_id))

    monkeypatch.setattr(scans_mod, "run_scan_job", fake_job)

    user = await make_user("scan@example.com")
    session.add(
        EmailAccount(
            user_id=user["user_id"],
            provider="gmail",
            email_address="inbox@gmail.com",
            oauth_refresh_token_encrypted=encrypt_token("refresh"),
        )
    )
    await session.commit()

    r = await client.post("/api/scans", headers=user["headers"])
    assert r.status_code == 202
    assert r.json()["status"] == "running"

    runs = (await session.scalars(select(ScanRun).where(ScanRun.user_id == user["user_id"]))).all()
    assert len(runs) == 1
    assert scheduled == [(runs[0].id, user["user_id"])]


async def test_get_scan_is_tenant_scoped(client, make_user, session):
    owner = await make_user("owner@example.com")
    other = await make_user("other@example.com")

    scan = ScanRun(user_id=owner["user_id"], status="succeeded")
    session.add(scan)
    await session.commit()
    await session.refresh(scan)

    r_owner = await client.get(f"/api/scans/{scan.id}", headers=owner["headers"])
    assert r_owner.status_code == 200

    r_other = await client.get(f"/api/scans/{scan.id}", headers=other["headers"])
    assert r_other.status_code == 404
