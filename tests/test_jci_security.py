"""Security invariants for direct JCI/Metasys routes."""

from fastapi.testclient import TestClient

from app.main import app
from app.deps.guards import require_bms_config_write
from app.models.user_context import UserContext


client = TestClient(app)


def test_jci_connection_probe_requires_auth():
    response = client.post(
        "/api/v1/jci/test-connection",
        json={"host": "https://127.0.0.1", "username": "u", "password": "p", "version": "v4"},
    )
    assert response.status_code == 401


def test_direct_jci_write_is_blocked_in_pilot():
    async def fake_bms_config_user():
        return UserContext(
            user_id="integrator-1",
            account_mode="live",
            access_level="read_write",
            roles=["bms_integrator"],
            building_ids=["b1"],
            authenticated=True,
        )

    app.dependency_overrides[require_bms_config_write] = fake_bms_config_user
    try:
        response = client.post(
            "/api/v1/jci/objects/av-1/command",
            json={"attribute": "presentValue", "value": 22.0},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    body = response.json()
    assert "detail" in body
