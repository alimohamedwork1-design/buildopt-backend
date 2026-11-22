"""Engineering acceptance tests: mathematical and cross-building boundary regressions."""
from datetime import datetime,timedelta,timezone
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import app
from app.deps.auth import get_required_user
from app.models.user_context import UserContext
from app.services.engineering_acceptance import (
 BenchmarkSite,PortfolioReviewRequest,review_portfolio,
 TwinCalibrationRequest,review_twin_calibration,
 OnPremPreflightRequest,review_onprem
)

def sites():
    return [
      dict(building_id="A",meter_reference="EVID-METER-A",category="commercial",
           climate_zone="GCC-hot",meter_boundary="whole building",
           period_start="2025-01-01",period_end="2026-01-01",
           energy_kwh=365000,floor_area_m2=1000,coverage_fraction=.98,
           cooling_degree_days=2000,occupied_hours=2800,permission_declared=True),
      dict(building_id="B",meter_reference="EVID-METER-B",category="commercial",
           climate_zone="GCC-hot",meter_boundary="whole building",
           period_start="2025-01-01",period_end="2026-01-01",
           energy_kwh=220000,floor_area_m2=1000,coverage_fraction=.97,
           cooling_degree_days=2100,occupied_hours=2760,permission_declared=True)
    ]

def portfolio(**kwargs):
    d=dict(building_id="A",sites=sites(),source_mode="operator_assumptions")
    d.update(kwargs)
    return PortfolioReviewRequest(**d)

def test_portfolio_gate_allows_only_matched_raw_eui():
    x=review_portfolio(portfolio())
    assert x["comparable_for_engineering_review"]
    assert x["results"][0]["raw_annualized_eui_kwh_m2"]==pytest.approx(365.25)
    assert x["savings_verified"] is False and x["writeback_enabled"] is False
    assert x["external_peer_percentile"] is None

def test_portfolio_blocks_weather_occupancy_permission_and_coverage():
    bad=sites()
    bad[1]={**bad[1],"cooling_degree_days":3500,"occupied_hours":1500,
            "coverage_fraction":.5,"permission_declared":False}
    x=review_portfolio(portfolio(sites=bad))
    assert not x["comparable_for_engineering_review"] and x["results"]==[]
    assert any("weather" in b for b in x["blockers"])
    assert any("permission" in b for b in x["blockers"])
    with pytest.raises(ValidationError):
        portfolio(sites=[sites()[0],sites()[0]])

def twin(**changes):
    now=datetime(2026,11,20,tzinfo=timezone.utc)
    rows=[dict(sample_id=f"hold-{i}",source_reference=f"METER-VALID-{i}",
      observed_kwh=100+i,predicted_kwh=(100+i)*1.01,
      observed_at=(now+timedelta(minutes=i)).isoformat()) for i in range(12)]
    p=dict(building_id="A",model_reference="TWIN-MODEL-001",
      holdout_points=rows,points_are_independent_holdout=True,
      source_mode="operator_assumptions")
    p.update(changes)
    return TwinCalibrationRequest(**p)

def test_twin_holdout_review_is_not_calibration_certificate():
    x=review_twin_calibration(twin())
    assert x["review_candidate"]
    assert x["metrics"]["holdout_cv_rmse_fraction"]<.15
    assert x["model_calibrated"] is False and x["savings_verified"] is False
    assert x["control_commands"]==[]

def test_twin_requires_independent_and_nonfabricated_input_format():
    x=review_twin_calibration(twin(points_are_independent_holdout=False))
    assert not x["review_candidate"]
    p=twin().model_dump(mode="json")
    p["holdout_points"][0]["observed_at"]="2026-11-20T00:00:00"
    with pytest.raises(ValidationError):
        TwinCalibrationRequest(**p)

def test_onprem_all_self_checks_still_not_certificate():
    kwargs={k:True for k in OnPremPreflightRequest.model_fields
      if k not in ("building_id","source_mode","read_only")}
    p=OnPremPreflightRequest(building_id="A",source_mode="operator_assumptions",**kwargs)
    out=review_onprem(p)
    assert out["ready_for_independent_security_validation"]
    assert not out["production_certified"]
    assert out["control_commands"]==[]
    fail=review_onprem(OnPremPreflightRequest(building_id="A",source_mode="operator_assumptions"))
    assert not fail["ready_for_independent_security_validation"]

def test_endpoints_require_auth_and_every_site_scope():
    client=TestClient(app)
    url="/api/v1/delivery-review/portfolio"
    data=portfolio().model_dump(mode="json")
    assert client.post(url,json=data).status_code==401
    async def one_site():
        return UserContext(user_id="u",authenticated=True,building_ids=["A"],roles=[])
    app.dependency_overrides[get_required_user]=one_site
    try:
        assert client.post(url,json=data).status_code==403
        assert client.post("/api/v1/delivery-review/twin-calibration",
          json=twin().model_dump(mode="json")).status_code==200
        assert client.post("/api/v1/delivery-review/onprem",
          json=OnPremPreflightRequest(building_id="B",source_mode="operator_assumptions").model_dump(mode="json")).status_code==403
    finally:
        app.dependency_overrides.clear()
    async def both():
        return UserContext(user_id="u",authenticated=True,building_ids=["A","B"],roles=[])
    app.dependency_overrides[get_required_user]=both
    try:
        assert client.post(url,json=data).status_code==200
        assert client.post(url,json={**data,"read_only":False}).status_code==422
    finally:
        app.dependency_overrides.clear()
