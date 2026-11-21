"""Readiness is not evidence of vendor/OEM certification or a live twin."""
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.api.compatibility import require_assigned_building
from app.deps.auth import get_required_user
from app.main import app
from app.models.user_context import UserContext
from app.services.compatibility_service import (
    SiteAssessment, TwinReadinessRequest, assess_site, get_compatibility_matrix,
    twin_readiness,
)


def test_matrix_never_claims_field_or_lab_validation():
    rows = get_compatibility_matrix()
    assert len(rows) == 6
    assert all(row["field_validation"] == "not_verified" for row in rows)
    assert all(row["lab_validation"] == "not_verified" for row in rows)
    assert all(row["writeback"] == "disabled" for row in rows)
    assert {"bacnet_ip", "modbus_tcp", "mqtt", "opc_ua", "rest", "historian"} == {x["protocol"] for x in rows}


def test_vendor_neutral_assessment_fail_closed():
    payload = SiteAssessment(building_id="site-a", protocol="bacnet_ip")
    result = assess_site(payload)
    assert result["status"] == "owner_authorization_required"
    assert "owner_access_authorized" in result["unmet_requirements"]
    assert not result["auto_connect_attempted"]
    assert result["field_validation"] == "not_certified"
    assert result["writeback"] == "disabled"


def test_site_assessment_never_certifies_self_reported_evidence():
    payload = SiteAssessment(
        building_id="site-a", protocol="modbus_tcp",
        owner_access_authorized=True,
        network_access_approved=True,
        read_only_scope_confirmed=True,
        sample_data_observed=True,
        timestamp_and_units_verified=True,
        point_mapping_accepted=True,
        disconnection_recovery_tested=True,
        engineer_signoff_recorded=True,
    )
    result = assess_site(payload)
    assert result["status"] == "ready_for_evidence_review"
    assert result["field_validation"] == "not_certified"


def test_site_rejects_writeback_and_unknown_fields():
    with pytest.raises(ValidationError):
        SiteAssessment(building_id="site-a", protocol="mqtt", writeback_requested=True)
    with pytest.raises(ValidationError):
        SiteAssessment(building_id="site-a", protocol="mqtt", secret_password="never")


def test_twin_ready_is_not_calibrated():
    payload = TwinReadinessRequest(
        building_id="site-a", declared_assets=2, approved_asset_mappings=2,
        point_history_verified=True, units_and_clock_verified=True,
        baseline_method_approved=True,
    )
    result = twin_readiness(payload)
    assert result["status"] == "ready_for_model_validation"
    assert result["model_validated"] is False
    assert result["real_savings_verified"] is False
    assert result["automatic_control_enabled"] is False


def test_twin_rejects_cross_count():
    with pytest.raises(ValueError):
        twin_readiness(TwinReadinessRequest(
            building_id="site-a", declared_assets=1, approved_asset_mappings=2,
        ))


def test_assessment_building_scope_rejects_other_tenant():
    user = UserContext(
        user_id="user-a", authenticated=True, building_ids=["site-a"], roles=[],
    )
    require_assigned_building(user, "site-a")
    with pytest.raises(Exception) as error:
        require_assigned_building(user, "site-b")
    assert error.value.status_code == 403


def test_public_matrix_is_read_only_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/compatibility/matrix")
    assert response.status_code == 200
    assert response.json()["protocols"][0]["writeback"] == "disabled"


def test_post_assessment_authentication_and_scoping():
    client = TestClient(app)
    payload = {"building_id": "site-a", "protocol": "bacnet_ip"}
    anonymous = client.post("/api/v1/compatibility/assess", json=payload)
    assert anonymous.status_code == 401

    async def account_user():
        return UserContext(user_id="u1", authenticated=True, building_ids=["site-a"])

    app.dependency_overrides[get_required_user] = account_user
    try:
        allowed = client.post("/api/v1/compatibility/assess", json=payload)
        forbidden = client.post("/api/v1/compatibility/assess", json={
            **payload, "building_id": "site-b",
        })
        twin = client.post("/api/v1/compatibility/twin-readiness", json={
            "building_id": "site-a", "declared_assets": 0,
            "approved_asset_mappings": 0,
        })
        assert allowed.status_code == 200
        assert forbidden.status_code == 403
        assert twin.status_code == 200
        assert twin.json()["model_validated"] is False
    finally:
        app.dependency_overrides.clear()
