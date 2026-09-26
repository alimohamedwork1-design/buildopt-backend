from fastapi.testclient import TestClient

from app.main import app
from app.models.user_context import UserContext
from app.deps.guards import require_write_access, require_bms_config


client = TestClient(app)


def test_sensitive_jci_probe_requires_authentication():
    response = client.post(
        "/api/v1/jci/test-connection",
        json={"host": "https://example.invalid", "username": "u", "password": "p", "version": "v4"},
    )
    assert response.status_code == 401


def test_direct_jci_write_is_blocked_even_for_write_user():
    async def fake_write_user():
        return UserContext(
            user_id="pilot-engineer",
            account_mode="live",
            access_level="read_write",
            roles=["facility_manager"],
            authenticated=True,
        )

    app.dependency_overrides[require_write_access] = fake_write_user
    try:
        response = client.post(
            "/api/v1/jci/objects/obj-1/command",
            json={"attribute": "presentValue", "value": 22.0},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.pop(require_write_access, None)

    assert response.status_code == 403


def test_bms_config_guard_rejects_untrusted_role():
    async def fake_tenant():
        return UserContext(
            user_id="tenant-1",
            account_mode="live",
            access_level="read_write",
            roles=["tenant"],
            authenticated=True,
        )

    from app.deps.auth import get_required_user

    app.dependency_overrides[get_required_user] = fake_tenant
    try:
        response = client.post(
            "/api/v1/jci/network-diagnostic",
            json={"host": "https://example.invalid", "username": "u", "password": "p", "version": "v4"},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.pop(get_required_user, None)

    assert response.status_code == 403
