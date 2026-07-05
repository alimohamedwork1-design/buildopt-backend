"""Tests for account mode, buildings CRUD, admin RBAC, excel import."""

from __future__ import annotations

import io

import pytest
from httpx import ASGITransport, AsyncClient

from app.models.user_context import UserContext
from app.main import app
from app.services.excel_import import parse_building_excel


@pytest.fixture
def live_user_no_buildings():
    return UserContext(
        user_id="user-live-1",
        email="live@test.com",
        account_mode="live",
        access_level="read_write",
        roles=["facility_manager"],
        building_ids=[],
        enabled_modules={"overview", "energy", "alerts"},
        authenticated=True,
    )


@pytest.fixture
def admin_user():
    return UserContext(
        user_id="admin-1",
        email="admin@test.com",
        account_mode="live",
        access_level="read_write",
        roles=["admin"],
        building_ids=[],
        enabled_modules={"overview", "energy"},
        authenticated=True,
    )


@pytest.fixture
def demo_user():
    return UserContext(authenticated=False, account_mode="demo")


def test_live_user_allows_no_demo_data(live_user_no_buildings):
    assert live_user_no_buildings.allows_demo_data() is False


def test_demo_anonymous_allows_demo_when_global_demo(demo_user, demo_settings):
    assert demo_user.allows_demo_data() is True


def test_excel_import_maps_messy_headers():
    import pandas as pd

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "Point Tag": ["AHU1.SAT", "CHW.SP"],
                "Type": ["AI", "AV"],
                "Unit": ["°C", "°C"],
            }
        ).to_excel(writer, sheet_name="Points", index=False)
        pd.DataFrame({"Building Name": ["HQ Tower"], "City": ["Dubai"]}).to_excel(
            writer, sheet_name="Building", index=False
        )
    result = parse_building_excel(buf.getvalue())
    assert len(result["points"]) == 2
    assert result["points"][0]["point_name"] == "AHU1.SAT"
    assert result["summary"]["rows_imported"] == 2
    assert result["building_metadata"].get("name") == "HQ Tower"


@pytest.mark.asyncio
async def test_create_building_without_bms_connection(demo_settings, monkeypatch):
    async def fake_create(owner_id, payload):
        return {"id": "b1", "owner_id": owner_id, "name": payload["name"], "connection_status": "disconnected"}

    monkeypatch.setattr("app.api.buildings.create_building", fake_create)

    async def fake_user():
        return UserContext(
            user_id="u1",
            account_mode="live",
            access_level="read_write",
            roles=["facility_manager"],
            building_ids=[],
            authenticated=True,
        )

    from app.deps import auth

    monkeypatch.setattr(auth, "get_required_user", fake_user)
    monkeypatch.setattr("app.api.buildings.require_write_access", fake_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        from app.deps.auth import get_required_user

        app.dependency_overrides[get_required_user] = fake_user
        from app.deps.guards import require_write_access

        app.dependency_overrides[require_write_access] = fake_user
        resp = await client.post(
            "/api/v1/buildings",
            json={"name": "Test Tower", "city": "Dubai", "total_area_sqm": 28000},
            headers={"Authorization": "Bearer test"},
        )
        app.dependency_overrides.clear()
    assert resp.status_code == 201
    assert resp.json()["building"]["connection_status"] == "disconnected"


@pytest.mark.asyncio
async def test_admin_endpoints_forbidden_for_client(demo_settings):
    from app.deps.auth import get_required_user

    async def fake_client_user():
        return UserContext(
            user_id="c1",
            roles=["facility_manager"],
            authenticated=True,
            account_mode="live",
            access_level="read_write",
        )

    app.dependency_overrides[get_required_user] = fake_client_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/admin/clients", headers={"Authorization": "Bearer x"})
    app.dependency_overrides.clear()
    assert resp.status_code == 403
