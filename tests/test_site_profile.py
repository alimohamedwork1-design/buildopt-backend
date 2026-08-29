"""Tests for per-building site profile store and API."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import site_profile_store


@pytest.fixture(autouse=True)
def _reset_site_profiles(tmp_path, monkeypatch):
    store_path = tmp_path / "site_profiles.json"
    monkeypatch.setattr(site_profile_store, "_STORE_PATH", store_path)
    yield


def test_get_site_profile_defaults_from_registry():
    assert site_profile_store.get_site_profile("burj-khalifa-01") == "building_with_industrial_cooling"
    assert site_profile_store.get_site_profile("dubai-mall-01") == "building_only"
    assert site_profile_store.get_site_profile("difc-gate-01") == "industrial_cooling_only"


def test_set_and_get_site_profile():
    saved = site_profile_store.set_site_profile("dubai-mall-01", "building_with_industrial_cooling")
    assert saved == "building_with_industrial_cooling"
    assert site_profile_store.get_site_profile("dubai-mall-01") == "building_with_industrial_cooling"


def test_set_site_profile_rejects_invalid():
    with pytest.raises(ValueError, match="Invalid site_profile"):
        site_profile_store.set_site_profile("dubai-mall-01", "invalid_profile")


def test_shows_hvac_and_refrigeration_helpers():
    assert site_profile_store.shows_hvac_connection("building_only") is True
    assert site_profile_store.shows_hvac_connection("industrial_cooling_only") is False
    assert site_profile_store.shows_refrigeration_connection("industrial_cooling_only") is True
    assert site_profile_store.shows_refrigeration_connection("building_only") is False


def test_site_profile_api_get_and_put():
    from app.deps.auth import get_required_user
    from app.models.user_context import UserContext

    def _demo_writer():
        return UserContext(account_mode="demo", authenticated=True, access_level="read_write", roles=["admin"])

    app.dependency_overrides[get_required_user] = _demo_writer
    try:
        client = TestClient(app)
        get_resp = client.get("/api/v1/buildings/burj-khalifa-01/site-profile")
        assert get_resp.status_code == 200
        assert get_resp.json()["site_profile"] == "building_with_industrial_cooling"

        put_resp = client.put(
            "/api/v1/buildings/burj-khalifa-01/site-profile",
            json={"site_profile": "building_only"},
            headers={"Authorization": "Bearer demo-test"},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["site_profile"] == "building_only"

        invalid_resp = client.put(
            "/api/v1/buildings/burj-khalifa-01/site-profile",
            json={"site_profile": "not_a_profile"},
            headers={"Authorization": "Bearer demo-test"},
        )
        assert invalid_resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_required_user, None)
