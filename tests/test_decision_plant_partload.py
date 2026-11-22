"""Part-load Decision OS engine: safety, honest provenance and tenant scope."""
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.main import app
from app.deps.auth import get_required_user
from app.models.user_context import UserContext
from app.services.decision_plant_partload import PlantPartLoadRequest, review_plant_part_load


UNITS = [
    dict(unit_id="CH-1", rated_cooling_kw=500, cop_at_25_pct=3.0,
         cop_at_50_pct=5.0, cop_at_100_pct=4.0, minimum_load_fraction=.25,
         auxiliary_power_kw=10, currently_running=True),
    dict(unit_id="CH-2", rated_cooling_kw=500, cop_at_25_pct=2.0,
         cop_at_50_pct=3.0, cop_at_100_pct=3.0, minimum_load_fraction=.25,
         auxiliary_power_kw=15, currently_running=False),
]


def make(**changes):
    data = dict(building_id="site-A", required_cooling_kw=250, chillers=UNITS,
                spare_capacity_fraction=.1, max_new_starts=1, duration_hours=2,
                startup_energy_kwh=5, engineering_limits_reviewed=True,
                site_interlocks_reviewed=True, source_mode="operator_assumptions")
    data.update(changes)
    return PlantPartLoadRequest(**data)


def test_cop_interpolation_and_auxiliary_power_are_counted():
    out = review_plant_part_load(make())
    assert out["feasible"]
    assert out["best"]["unit_ids"] == ["CH-1"]
    assert out["best"]["electric_power_kw"] == 60
    assert out["best"]["modeled_energy_kwh"] == 120
    assert out["best"]["dispatch"][0]["interpolated_assumed_cop"] == 5
    assert out["model_calibrated"] is False
    assert out["savings_verified"] is False
    assert out["writeback_enabled"] is False
    assert out["control_commands"] == []


def test_safety_declarations_gate_model():
    for change in (dict(engineering_limits_reviewed=False),
                   dict(site_interlocks_reviewed=False)):
        out = review_plant_part_load(make(**change))
        assert not out["feasible"]
        assert out["best"] is None
        assert out["blockers"] == ["engineering_limits_and_site_interlocks_not_reviewed"]


def test_spare_min_load_starts_and_lockout_constraints():
    assert not review_plant_part_load(make(spare_capacity_fraction=.4,
        required_cooling_kw=900))["feasible"]
    assert not review_plant_part_load(make(required_cooling_kw=40))["feasible"]
    assert not review_plant_part_load(make(max_new_starts=0, chillers=[
        {**UNITS[0], "currently_running":False}, UNITS[1]]))["feasible"]
    blocked=[{**UNITS[0],"locked_out":True},UNITS[1]]
    out=review_plant_part_load(make(chillers=blocked,spare_capacity_fraction=0))
    assert out["best"]["unit_ids"] == ["CH-2"]


def test_zero_demand_never_starts_units():
    out=review_plant_part_load(make(required_cooling_kw=0))
    assert out["feasible"] and out["best"]["dispatch"] == []
    assert out["best"]["modeled_energy_kwh"] == 0


@pytest.mark.parametrize("change",[
    {"chillers": [UNITS[0],UNITS[0]]},
    {"chillers": [{**UNITS[0],"cop_at_50_pct":float("nan")}]},
    {"chillers": [{**UNITS[0],"minimum_load_fraction":0}]},
    {"read_only":False},
    {"source_mode":"verified_metered"},
    {"control_commands":[{"start":"CH-1"}]},
])
def test_forged_or_invalid_parameters_are_refused(change):
    with pytest.raises(ValidationError):
        make(**change)


def test_endpoint_requires_auth_and_explicit_building_membership():
    client=TestClient(app)
    url="/api/v1/decision-os/scenarios/chiller-part-load-review"
    payload=make().model_dump(mode="json")
    assert client.post(url,json=payload).status_code==401
    async def user():
        return UserContext(user_id="u1",authenticated=True,building_ids=["site-A"],roles=[])
    app.dependency_overrides[get_required_user]=user
    try:
        assert client.post(url,json=payload).status_code==200
        assert client.post(url,json={**payload,"building_id":"site-B"}).status_code==403
        assert client.post(url,json={**payload,"read_only":False}).status_code==422
    finally:
        app.dependency_overrides.clear()
