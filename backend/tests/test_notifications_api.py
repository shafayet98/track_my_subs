"""Notification-preferences API: defaults, update, validation, tenant scoping."""

from app.models.notification_preference import DEFAULT_LEAD_TIME_DAYS


async def test_get_returns_defaults_when_no_row(client, make_user):
    u = await make_user("a@example.com")
    r = await client.get("/api/notifications/preferences", headers=u["headers"])
    assert r.status_code == 200, r.text
    assert r.json() == {
        "renewals_enabled": True,
        "trial_conversions_enabled": True,
        "missed_payments_enabled": True,
        "lead_time_days": DEFAULT_LEAD_TIME_DAYS,
    }


async def test_put_updates_and_persists(client, make_user):
    u = await make_user("b@example.com")
    r = await client.put(
        "/api/notifications/preferences",
        headers=u["headers"],
        json={"missed_payments_enabled": False, "lead_time_days": 7},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["missed_payments_enabled"] is False
    assert body["lead_time_days"] == 7
    assert body["renewals_enabled"] is True  # untouched

    again = await client.get("/api/notifications/preferences", headers=u["headers"])
    assert again.json()["lead_time_days"] == 7


async def test_put_rejects_out_of_range_lead_time(client, make_user):
    u = await make_user("c@example.com")
    r = await client.put(
        "/api/notifications/preferences",
        headers=u["headers"],
        json={"lead_time_days": 99},
    )
    assert r.status_code == 422


async def test_preferences_are_tenant_scoped(client, make_user):
    a = await make_user("d@example.com")
    b = await make_user("e@example.com")
    await client.put(
        "/api/notifications/preferences",
        headers=a["headers"],
        json={"lead_time_days": 10},
    )
    r = await client.get("/api/notifications/preferences", headers=b["headers"])
    assert r.json()["lead_time_days"] == DEFAULT_LEAD_TIME_DAYS
