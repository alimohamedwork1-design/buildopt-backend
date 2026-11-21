"""Decision OS: analytical correctness, no hidden savings and strict auth."""
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.deps.auth import get_required_user
from app.models.user_context import UserContext
from app.services.decision_engine import (
    ChillerDispatchRequest, ScheduleRequest, FaultPriorityRequest,
    optimize_chiller_dispatch, assess_hvac_schedule, prioritize_faults,
)
from app.services.facility_graph import FacilityGraphRequest, check_facility_graph

SITE="site-a"
CHILLERS=[
 {"unit_id":"CH-1","cooling_capacity_kw":400,"reference_cop":5.0,
  "min_load_fraction":0.0,"currently_running":True},
 {"unit_id":"CH-2","cooling_capacity_kw":400,"reference_cop":3.0,
  "min_load_fraction":0.0,"currently_running":False},
]

def dispatch(**overrides):
    args={
        "building_id":SITE,"demand_cooling_kw":300,
        "chillers":CHILLERS,"tariff_per_kwh":0.2,"currency":"USD",
        "duration_hours":2,"startup_penalty_kwh":0,
        "reserve_margin_fraction":0.1,"source_mode":"operator_assumptions"
    }
    args.update(overrides)
    return ChillerDispatchRequest(**args)


def test_dispatch_chooses_higher_cop_and_reports_all_assumptions():
    r=optimize_chiller_dispatch(dispatch())
    assert r["feasible"] is True
    assert r["best"]["dispatch"][0]["unit_id"]=="CH-1"
    assert r["best"]["electric_power_kw"]==60
    assert r["best"]["modeled_energy_kwh"]==120
    assert r["best"]["modeled_cost"]==24
    assert r["best"]["indicative_delta_cost"] is None
    assert not r["savings_verified"]
    assert not r["writeback_enabled"]
    assert r["control_commands"]==[]


def test_baseline_savings_are_only_indicative_even_if_positive():
    r=optimize_chiller_dispatch(dispatch(assumed_baseline_power_kw=100))
    assert r["best"]["indicative_delta_cost"]==16
    assert r["field_validated"] is False
    assert "unverified baseline" in " ".join(r["assumptions"])


def test_capacity_reserve_blocks_unfeasible_load():
    r=optimize_chiller_dispatch(dispatch(demand_cooling_kw=750,reserve_margin_fraction=0.2))
    assert not r["feasible"]
    assert r["best"] is None
    assert "insufficient_available_capacity_including_reserve" in r["blockers"]


def test_minimum_turndown_blocks_low_load():
    ch=[{**c,"min_load_fraction":0.4} for c in CHILLERS]
    r=optimize_chiller_dispatch(dispatch(chillers=ch,demand_cooling_kw=30))
    assert not r["feasible"]


def test_residual_load_is_conserved_and_no_overcapacity():
    r=optimize_chiller_dispatch(dispatch(demand_cooling_kw=600))
    assert r["feasible"]
    loads=r["best"]["dispatch"]
    assert sum(x["cooling_load_kw"] for x in loads)==pytest.approx(600)
    assert all(x["load_fraction"]<=1.0 for x in loads)


def test_startup_penalty_can_change_preference():
    # CH-1 is more efficient but off; CH-2 is less efficient and already running.
    chillers=[{**CHILLERS[0],"currently_running":False},
              {**CHILLERS[1],"currently_running":True}]
    r=optimize_chiller_dispatch(dispatch(chillers=chillers,duration_hours=1,
                                         startup_penalty_kwh=70))
    assert r["best"]["unit_ids"]==["CH-2"]


def test_zero_load_does_not_run_chillers():
    r=optimize_chiller_dispatch(dispatch(demand_cooling_kw=0))
    assert r["feasible"] and r["best"]["electric_power_kw"]==0
    assert r["best"]["dispatch"]==[]


@pytest.mark.parametrize("change",[
    {"demand_cooling_kw":-1},
    {"chillers":[CHILLERS[0],CHILLERS[0]]},
    {"chillers":[{**CHILLERS[0],"reference_cop":0}]},
    {"read_only":False},
    {"source_mode":"verified_metered"},
    {"writeback":{"setpoint":8}},
])
def test_dispatch_refuses_unsafe_or_false_inputs(change):
    with pytest.raises(ValidationError):
        dispatch(**change)


def schedule(**overrides):
    a={
       "building_id":SITE,"occupancy_hours":10,"preconditioning_hours":2,
       "baseline_run_hours":24,"proposed_run_hours":14,
       "assumed_active_power_kw":100,"tariff_per_kwh":0.2,
       "currency":"USD","source_mode":"operator_assumptions"
    }
    a.update(overrides)
    return ScheduleRequest(**a)


def test_hvac_schedule_occupancy_guard_and_indicative_cost():
    r=assess_hvac_schedule(schedule())
    assert r["feasible"]
    assert r["best"]["indicative_energy_difference_kwh"]==1000
    assert r["best"]["indicative_cost_difference"]==200
    assert r["best"]["comfort_verified"] is False
    assert r["writeback_enabled"] is False
    for proposed in (0,11.5):
        blocked=assess_hvac_schedule(schedule(proposed_run_hours=proposed))
        assert blocked["best"] is None
        assert not blocked["feasible"]


def test_hvac_schedule_baseline_itself_cannot_violate_occupancy():
    r=assess_hvac_schedule(schedule(baseline_run_hours=5))
    assert r["blockers"] == ["baseline_hours_below_occupied_plus_preconditioning"]


def test_fault_ranking_escalates_safety_independent_of_score():
    req=FaultPriorityRequest(building_id=SITE,source_mode="operator_assumptions",
       faults=[
           {"fault_id":"F1","asset_id":"AHU-1","severity":5,"asset_criticality":5,"age_days":30,"evidence_quality":"accepted"},
           {"fault_id":"F2","asset_id":"SAFETY-1","severity":1,"asset_criticality":1,"age_days":0,"evidence_quality":"missing","safety_related":True}
       ])
    r=prioritize_faults(req)
    assert r["ranked_faults"][0]["fault_id"]=="F2"
    assert r["ranked_faults"][0]["review_action"]=="safety_escalation"
    assert r["ranked_faults"][0]["score_is_probability"] is False
    assert r["writeback_enabled"] is False


def graph(**overrides):
    now=datetime.now(timezone.utc).isoformat()
    a={
     "building_id":SITE,"source_mode":"operator_assumptions",
     "assets":[{"asset_id":"CH-1","name":"Chiller 1","asset_type":"chiller"},
               {"asset_id":"M-1","name":"Electricity meter","asset_type":"meter"}],
     "edges":[{"source_asset_id":"M-1","target_asset_id":"CH-1","relation":"meters"}],
     "points":[{"point_id":"CH1.POWER","asset_id":"CH-1","semantic_key":"electric_power",
                "unit":"kW","source_system":"operator_import","quality":"good",
                "source_timestamp":now}]
    }
    a.update(overrides)
    return FacilityGraphRequest(**a)


def test_graph_checks_reference_integrity_and_readiness_is_not_certification():
    r=check_facility_graph(graph())
    assert r["engineering_review_ready"]
    assert not r["field_validated"]
    assert not r["writeback_enabled"]
    for issue in (
      {"assets":[{"asset_id":"x","name":"One","asset_type":"chiller"}]},
      {"points":[{**graph().points[0].model_dump(mode="json"),"asset_id":"missing"}]},
      {"edges":[{"source_asset_id":"M-1","target_asset_id":"UNKNOWN","relation":"meters"}]}
    ):
        # First case contains unknown edges/points, both are rejected.
        with pytest.raises(ValidationError):
            graph(**issue)


def test_stale_or_invalid_points_cannot_be_called_engineering_review_ready():
    old=(datetime.now(timezone.utc)-timedelta(hours=5)).isoformat()
    stale={**graph().points[0].model_dump(mode="json"),"source_timestamp":old}
    r=check_facility_graph(graph(points=[stale]))
    assert not r["engineering_review_ready"]
    assert r["quality_issues"][0]["reason"]=="stale_telemetry"


def test_decision_api_strict_building_scope_and_public_catalog_only():
    client=TestClient(app)
    catalog=client.get("/api/v1/decision-os/catalog")
    assert catalog.status_code==200
    assert len(catalog.json()["engines"])==3
    assert catalog.json()["can_send_equipment_commands"] is False
    body=dispatch().model_dump(mode="json")
    assert client.post("/api/v1/decision-os/scenarios/chiller-dispatch",json=body).status_code==401
    async def user():
        return UserContext(user_id="a",authenticated=True,building_ids=[SITE],roles=[])
    app.dependency_overrides[get_required_user]=user
    try:
        allowed=client.post("/api/v1/decision-os/scenarios/chiller-dispatch",json=body)
        assert allowed.status_code==200
        assert allowed.json()["best"]["electric_power_kw"]==60
        denied=client.post("/api/v1/decision-os/scenarios/chiller-dispatch",json={
            **body,"building_id":"site-b"})
        assert denied.status_code==403
        graph_payload=graph().model_dump(mode="json")
        assert client.post("/api/v1/decision-os/graph/validate",json=graph_payload).status_code==200
    finally:
        app.dependency_overrides.clear()
