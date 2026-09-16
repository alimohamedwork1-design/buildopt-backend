from __future__ import annotations

from fastapi.testclient import TestClient

from app.deps.guards import require_admin
from app.main import app
from app.models.user_context import UserContext


def _admin_user() -> UserContext:
    return UserContext(
        user_id="admin-1",
        email="admin@test.com",
        account_mode="live",
        access_level="read_write",
        roles=["admin"],
        building_ids=[],
        authenticated=True,
    )


def test_admin_control_plane_is_truthful_and_secret_free(monkeypatch):
    async def fake_clients():
        return [
            {
                "user_id": "client-1",
                "email": "client@test.com",
                "display_name": "Client One",
                "organization": "Pilot Co",
                "account_mode": "live",
                "access_level": "read_only",
                "account_status": "active",
            }
        ]

    async def fake_buildings(owner_id: str):
        assert owner_id == "client-1"
        return [
            {"id": "b1", "connection_status": "connected"},
            {"id": "b2", "connection_status": "disconnected"},
        ]

    monkeypatch.setattr("app.api.admin.list_all_clients", fake_clients)
    monkeypatch.setattr("app.api.admin.list_buildings_for_owner", fake_buildings)
    app.dependency_overrides[require_admin] = _admin_user
    try:
        response = TestClient(app).get("/api/v1/admin/control-plane")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["platform"]["clients"] == 1
    assert body["platform"]["buildings"] == 2
    assert body["platform"]["connected_buildings"] == 1
    assert body["guardrails"]["automatic_writeback"] is False
    assert body["guardrails"]["live_demo_fallback"] is False
    rendered = str(body).lower()
    assert "password" not in rendered
    assert "secret_key" not in rendered
