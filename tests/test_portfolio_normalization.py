from copy import deepcopy
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from app.main import app
from app.deps.auth import get_required_user
from app.models.user_context import UserContext
from app.services.portfolio_normalization import NormalizedPortfolioRequest, review_normalized_portfolio

def meter(month, cdd, hours, scale=1):
    return dict(month=month,cooling_degree_days=cdd,occupied_hours=hours,
                energy_kwh=scale*(1000+3*cdd+2*hours),coverage_fraction=.99,
                source_ref="METER-REF-"+month)

def site(building,scale=1):
    return dict(building_id=building,category="commercial",meter_boundary="whole building",
                floor_area_m2=1000,permission_declared=True,weather_reference="WEATHER-REF-001",
                occupancy_definition="building operating hours",cdd_base_c=18,
                training_months=[meter(f"2024-{i+1:02d}-01",20+i,180+8*(i%4),scale) for i in range(12)],
                holdout_months=[meter(f"2025-{i+1:02d}-01",23+i,188+8*(i%3),scale) for i in range(3)])

def payload():
    return dict(building_id="A",sites=[site("A"),site("B",2)],
                reference_months=[dict(month=f"2026-{i+1:02d}-01",
                cooling_degree_days=23,occupied_hours=188) for i in range(12)],
                reference_label="REFERENCE-SCHEDULE-2026",source_mode="operator_assumptions",read_only=True)

def test_normalization_computes_common_conditions_with_distinct_holdout():
    x=review_normalized_portfolio(NormalizedPortfolioRequest(**payload()))
    assert x["comparable_for_engineering_review"]
    assert x["results"][0]["model_normalized_annual_kwh"]==pytest.approx(12*(1000+3*23+2*188))
    assert x["results"][1]["model_normalized_eui_kwh_m2"]==pytest.approx(2*x["results"][0]["model_normalized_eui_kwh_m2"],abs=.002)
    assert x["diagnostics"][0]["metrics"]["holdout_cv_rmse"]==pytest.approx(0)
    assert x["model_calibrated"] is False and x["savings_verified"] is False
    assert x["control_commands"]==[]

def test_normalization_blocks_bad_holdout_permission_extrapolation_and_scope():
    for key in ["holdout_fit_failed","permission_not_declared","conditions_outside_training_range","occupancy_definition_mismatch"]:
        p=payload()
        if key=="holdout_fit_failed":
            for m in p["sites"][1]["holdout_months"]:m["energy_kwh"]*=3
        elif key=="permission_not_declared":p["sites"][1]["permission_declared"]=False
        elif key=="conditions_outside_training_range":p["reference_months"][0]["cooling_degree_days"]=80
        else:p["sites"][1]["occupancy_definition"]="different declared basis"
        x=review_normalized_portfolio(NormalizedPortfolioRequest(**p))
        assert not x["comparable_for_engineering_review"] and x["results"]==[]
        assert any(key in v for v in x["blockers"])

def test_normalization_requires_calendar_intervals_and_no_shared_holdout():
    p=payload()
    p["reference_months"][1]["month"]="2026-01-01"
    with pytest.raises(ValidationError):NormalizedPortfolioRequest(**p)
    p=payload()
    p["sites"][0]["holdout_months"][0]["month"]="2024-12-01"
    with pytest.raises(ValidationError):NormalizedPortfolioRequest(**p)
    p=payload()
    p["sites"][0]["training_months"][1]["occupied_hours"]=744
    with pytest.raises(ValidationError):NormalizedPortfolioRequest(**p)

def test_normalization_authenticates_and_checks_every_building():
    c=TestClient(app)
    url="/api/v1/delivery-review/portfolio-normalized"
    assert c.post(url,json=payload()).status_code==401
    async def one():return UserContext(user_id="u",authenticated=True,building_ids=["A"],roles=[])
    async def both():return UserContext(user_id="u",authenticated=True,building_ids=["A","B"],roles=[])
    try:
        app.dependency_overrides[get_required_user]=one
        assert c.post(url,json=payload()).status_code==403
        app.dependency_overrides[get_required_user]=both
        assert c.post(url,json=payload()).status_code==200
        p=payload();p["read_only"]=False
        assert c.post(url,json=p).status_code==422
    finally:app.dependency_overrides.clear()
