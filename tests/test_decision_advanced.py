"""Decision OS V2: deterministic engineering and tenant/auth safety regressions."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.deps.auth import get_required_user
from app.models.user_context import UserContext
from app.services.decision_advanced import (
    TariffProfileRequest, CompressorUnit, RefrigerationAdvisoryRequest,
    analyze_tariff_profile, review_refrigeration_staging,
)
from app.services.decision_measurement_review import (
    MeterPeriod, MeasurementReviewRequest, prepare_mv_review,
)


def tariff(**changes):
    data={
        "building_id":"A",
        "baseline_hourly_kwh":[100.0]*24,
        "proposed_hourly_kwh":[80.0]*24,
        "hourly_rate_per_kwh":[0.2]*24,
        "currency":"USD",
        "demand_charge_per_kw_for_period":0.1,
        "tax_fraction":0.1,
        "source_mode":"operator_assumptions",
    }
    data.update(changes)
    return TariffProfileRequest(**data)


def test_tou_costs_with_per_period_demand_and_tax():
    outcome=analyze_tariff_profile(tariff())
    assert outcome["feasible"]
    c=outcome["comparison"]
    assert c["baseline_kwh"]==2400
    assert c["proposed_kwh"]==1920
    assert c["baseline"]["total_modeled_cost"]==539.0
    assert c["proposed"]["total_modeled_cost"]==431.2
    assert c["indicative_cost_difference"]==pytest.approx(107.8)
    assert outcome["savings_verified"] is False
    assert outcome["control_commands"]==[]
    assert outcome["writeback_enabled"] is False


def test_tou_hourly_peak_guard_and_no_negative_energy():
    blocked=analyze_tariff_profile(tariff(peak_limit_kw=75))
    assert blocked["feasible"] is False
    assert len(blocked["violating_hour_indices"])==24
    with pytest.raises(ValidationError):
        tariff(baseline_hourly_kwh=[100]*23)
    with pytest.raises(ValidationError):
        tariff(proposed_hourly_kwh=[-1]+[80]*23)
    with pytest.raises(ValidationError):
        tariff(hourly_rate_per_kwh=[float("nan")]*24)


def test_tou_peak_is_proxy_and_favorable_model_not_measured_savings():
    r=analyze_tariff_profile(tariff())
    assert "actual demand peaks can be higher" in " ".join(r["assumptions"])
    assert r["field_validated"] is False


UNITS=[
    {"unit_id":"CP-1","rated_cooling_kw":400,"assumed_cop":4,
     "min_load_fraction":0,"available":True,"currently_running":True},
    {"unit_id":"CP-2","rated_cooling_kw":400,"assumed_cop":2,
     "min_load_fraction":0,"available":True,"currently_running":False},
]


def cooling(**changes):
    data={
        "building_id":"A","medium":"R717","assumed_cooling_demand_kw":300,
        "compressors":UNITS,"availability_reserve_fraction":.1,
        "duration_hours":2,"startup_energy_kwh_per_start":0,
        "site_safety_interlocks_reviewed":True,
        "operating_envelope_approved":True,
        "source_mode":"operator_assumptions",
    }
    data.update(changes)
    return RefrigerationAdvisoryRequest(**data)


def test_refrigeration_requires_declared_interlocks_and_operating_limits():
    for kwargs in ({"site_safety_interlocks_reviewed":False},
                   {"operating_envelope_approved":False}):
        result=review_refrigeration_staging(cooling(**kwargs))
        assert not result["feasible"]
        assert result["best"] is None
        assert "site_safety_and_operating_limits_not_reviewed" in result["blockers"]
        assert result["control_commands"]==[]


def test_refrigeration_selects_efficient_unlocked_compressor():
    r=review_refrigeration_staging(cooling())
    assert r["feasible"]
    assert r["best"]["unit_ids"]==["CP-1"]
    assert r["best"]["electric_power_kw"]==75
    assert r["best"]["modeled_energy_kwh"]==150
    assert r["writeback_enabled"] is False
    assert r["savings_verified"] is False


def test_refrigeration_interlock_avoids_locked_equipment_and_blocks_low_turndown():
    locked=[{**UNITS[0],"safety_locked_out":True},UNITS[1]]
    r=review_refrigeration_staging(cooling(compressors=locked))
    assert r["feasible"]
    assert r["best"]["unit_ids"]==["CP-2"]
    blocked=review_refrigeration_staging(cooling(compressors=locked,assumed_cooling_demand_kw=600))
    assert not blocked["feasible"]
    constrained=[{**c,"min_load_fraction":0.6} for c in UNITS]
    r=review_refrigeration_staging(cooling(compressors=constrained,assumed_cooling_demand_kw=50))
    assert not r["feasible"]
    with pytest.raises(ValidationError):
        cooling(compressors=[UNITS[0],UNITS[0]])


def test_refrigeration_does_not_issue_commands_for_zero_load():
    r=review_refrigeration_staging(cooling(assumed_cooling_demand_kw=0))
    assert r["feasible"] and r["best"]["dispatch"]==[]
    assert r["control_commands"]==[]


def baseline_periods():
    return [
        {"period_id":f"B{i:02d}","meter_reference":f"OPERATOR-ENERGY-METER-B{i:02d}",
         "energy_kwh":1000+3*(20+i)+2*(180+8*(i%4)),
         "cooling_degree_days":20+i,"operating_hours":180+8*(i%4),
         "coverage_fraction":1.0} for i in range(12)
    ]


def reporting_periods():
    return [
        {"period_id":f"R{i:02d}","meter_reference":f"OPERATOR-ENERGY-METER-R{i:02d}",
         "energy_kwh":1000+3*(32+i)+2*(180+8*(i%3))-200,
         "cooling_degree_days":32+i,"operating_hours":180+8*(i%3),
         "coverage_fraction":1.0} for i in range(3)
    ]


def mv(**changes):
    data={
        "building_id":"A","measurement_boundary":"Chiller plant main energy meter",
        "baseline_periods":baseline_periods(),"reporting_periods":reporting_periods(),
        "source_mode":"operator_assumptions",
    }
    data.update(changes)
    return MeasurementReviewRequest(**data)


def test_mv_regression_adjusts_weather_and_runtime_but_stays_unverified():
    result=prepare_mv_review(mv())
    assert result["feasible"]
    assert result["best"]["indicative_adjusted_difference_kwh"]==pytest.approx(600)
    assert result["baseline_model"]["training_cv_rmse_fraction"]==pytest.approx(0,abs=1e-8)
    assert result["verification_status"]=="READY_FOR_INDEPENDENT_ENGINEERING_REVIEW_ONLY"
    assert result["savings_verified"] is False
    assert result["writeback_enabled"] is False
    assert result["measurement_status"].startswith("OPERATOR_OBSERVED")


def test_mv_rejects_weak_coverage_duplicate_periods_and_collinearity():
    reporting=reporting_periods()
    reporting[0]["coverage_fraction"]=0.45
    result=prepare_mv_review(mv(reporting_periods=reporting))
    assert not result["feasible"]
    assert result["blockers"]==["inadequate_meter_coverage"]
    with pytest.raises(ValidationError):
        mv(reporting_periods=[{**reporting_periods()[0],"period_id":"B00"}])
    bad=[{**b,"operating_hours":100+2*b["cooling_degree_days"]}
         for b in baseline_periods()]
    collinear=prepare_mv_review(mv(baseline_periods=bad))
    assert not collinear["feasible"]
    assert "collinear_or_insufficient_baseline_variation" in collinear["blockers"]
    with pytest.raises(ValidationError):
        mv(baseline_periods=baseline_periods()[:5])


def test_mv_refuses_spurious_negative_baseline_predictions():
    # Large unseen covariates can yield a negative extrapolated baseline.
    b=baseline_periods()
    b=[{**row, "energy_kwh":5000-10*row["cooling_degree_days"]+2*row["operating_hours"]} for row in b]
    bad=reporting_periods()
    bad=[{**row,"cooling_degree_days":5000} for row in bad]
    result=prepare_mv_review(mv(baseline_periods=b,reporting_periods=bad))
    assert not result["feasible"]
    assert result["blockers"]==["nonphysical_negative_predicted_energy"]


def test_advanced_endpoints_need_auth_and_correct_site():
    client=TestClient(app)
    catalog=client.get("/api/v1/decision-os/catalog")
    assert catalog.status_code==200
    assert len(catalog.json()["engines"])>=6
    path="/api/v1/decision-os/scenarios/tou-energy-cost"
    body=tariff().model_dump(mode="json")
    assert client.post(path,json=body).status_code==401
    async def allowed():
        return UserContext(user_id="test-user",authenticated=True,building_ids=["A"],roles=[])
    app.dependency_overrides[get_required_user]=allowed
    try:
        assert client.post(path,json=body).status_code==200
        assert client.post(path,json={**body,"building_id":"B"}).status_code==403
        ref=client.post("/api/v1/decision-os/scenarios/industrial-cooling-advisory",json=cooling().model_dump(mode="json"))
        assert ref.status_code==200
        obs=client.post("/api/v1/decision-os/scenarios/baseline-mv-review",json=mv().model_dump(mode="json"))
        assert obs.status_code==200
        assert obs.json()["savings_verified"] is False
    finally:
        app.dependency_overrides.clear()


def validation_periods(offset=0):
    """Synthetic, disjoint periods: used only as an independently supplied model holdout."""
    return [
        {"period_id":f"V{i:02d}", "meter_reference":f"SIMULATED-VALIDATION-METER-{i:02d}",
         "energy_kwh":1000+3*(40+i)+2*(172+8*i)+offset,
         "cooling_degree_days":40+i, "operating_hours":172+8*i,
         "coverage_fraction":1.0} for i in range(4)
    ]


def test_mv_optional_holdout_is_reported_without_claiming_field_calibration():
    r=prepare_mv_review(mv(validation_periods=validation_periods()))
    assert r["feasible"]
    assert r["independent_holdout_provided"] is True
    assert r["field_calibrated"] is False
    assert r["holdout_validation"]["period_count"]==4
    assert r["holdout_validation"]["cv_rmse_fraction"]==pytest.approx(0, abs=1e-8)
    assert r["holdout_validation"]["nmbe_fraction"]==pytest.approx(0, abs=1e-8)
    assert r["holdout_validation"]["independently_verified"] is False
    assert r["savings_verified"] is False and r["control_commands"]==[]


def test_mv_holdout_bias_blocks_draft_result_even_with_perfect_training_fit():
    r=prepare_mv_review(mv(validation_periods=validation_periods(offset=600)))
    assert not r["feasible"]
    assert r["best"] is None
    assert "holdout_bias_exceeds_review_threshold" in r["blockers"]
    assert r["holdout_validation"]["independently_verified"] is False


def test_mv_holdout_requires_three_unique_covered_periods_and_no_injection():
    with pytest.raises(ValidationError):
        mv(validation_periods=validation_periods()[:2])
    with pytest.raises(ValidationError):
        mv(validation_periods=[{**validation_periods()[0], "period_id":"B00"}, *validation_periods()[1:]])
    low=validation_periods()
    low[0]["coverage_fraction"]=.3
    r=prepare_mv_review(mv(validation_periods=low))
    assert not r["feasible"] and r["blockers"]==["inadequate_meter_coverage"]
    with pytest.raises(ValidationError):
        mv(validation_periods=[{**row, "energy_kwh":float("nan")} for row in validation_periods()])
