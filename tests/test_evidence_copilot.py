from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.evidence_copilot import router
from app.deps.auth import get_required_user
from app.main import app
from app.models.user_context import UserContext
from app.services.evidence_copilot import InvestigationRequest, analyze_evidence

NOW=datetime(2026,11,21,12,tzinfo=timezone.utc)

def point(kind,value,quality="good",age=1,unit="°C"):
    t=NOW-timedelta(minutes=age)
    return {
        "point_id":"chiller01."+kind,"equipment_id":"chiller01","kind":kind,
        "value":value,"unit":unit,"quality":quality,"measured_at":t.isoformat(),
        "received_at":(t+timedelta(seconds=1)).isoformat(),
        "processed_at":(t+timedelta(seconds=2)).isoformat()
    }

def case(supply=6,ret=8):
    return InvestigationRequest(building_id="building-a",equipment_id="chiller01",
        equipment_type="chiller_plant",points=[
            point("chw_supply_c",supply),point("chw_return_c",ret)
        ])

def test_low_delta_has_source_provenance_without_savings():
    result=analyze_evidence(case(),now=NOW)
    assert result["findings"][0]["code"]=="LOW_CHW_DELTA"
    assert len(result["findings"][0]["point_ids"])==2
    assert result["findings"][0]["verified_savings"] is None
    assert result["automated_writeback"] is False
    assert result["control_commands"]==[]

def test_stale_data_blocks_inference():
    req=case()
    req.points[1].measured_at=NOW-timedelta(hours=3)
    # Modified timestamp remains ordered before originally received timestamp.
    result=analyze_evidence(req,now=NOW)
    assert result["overall_status"]=="insufficient_data"
    assert result["findings"][0]["code"]=="INSUFFICIENT_CHW_EVIDENCE"

def test_invalid_units_rejects_temperature_calculation():
    req=case()
    req.points[0].unit="°F"
    result=analyze_evidence(req,now=NOW)
    assert result["findings"][0]["code"]=="INVALID_UNITS"

def test_bad_source_or_unsigned_permission_is_rejected():
    data=case().model_dump(mode="json")
    data["points"][0]["measured_at"]="2026-11-21T13:00:00+00:00"
    with pytest.raises(ValidationError):
        InvestigationRequest(**data)
    data=case().model_dump(mode="json")
    data["explicitly_authorized_data"]=False
    with pytest.raises(ValidationError):
        InvestigationRequest(**data)
    data=case().model_dump(mode="json")
    data["control_command"]="enable chiller"
    with pytest.raises(ValidationError):
        InvestigationRequest(**data)

def test_other_equipment_is_never_silently_analyzed():
    req=InvestigationRequest(building_id="building-a",equipment_id="ahu01",
        equipment_type="air_handling_unit",points=[{
           **point("ahu_supply_c",16),"equipment_id":"ahu01"}])
    r=analyze_evidence(req,now=NOW)
    assert r["overall_status"]=="insufficient_data"
    assert r["findings"][0]["code"]=="NO_ENGINEERING_RULE"

def test_endpoint_requires_real_building_entitlement():
    client=TestClient(app)
    payload=case().model_dump(mode="json")
    assert client.post("/api/v1/engineering-copilot/investigate",json=payload).status_code==401
    async def user():
        return UserContext(user_id="u",authenticated=True,building_ids=["building-a"])
    app.dependency_overrides[get_required_user]=user
    try:
        assert client.post("/api/v1/engineering-copilot/investigate",json=payload).status_code==200
        payload["building_id"]="building-b"
        assert client.post("/api/v1/engineering-copilot/investigate",json=payload).status_code==403
    finally:
        app.dependency_overrides.clear()


def test_copilot_rejects_nan_and_timezone_free_evidence():
    d=case().model_dump(mode="json")
    d["points"][0]["value"]=float("nan")
    with pytest.raises(ValidationError):
        InvestigationRequest(**d)
    d=case().model_dump(mode="json")
    d["points"][0]["received_at"]="2026-11-21T11:59:01"
    with pytest.raises(ValidationError):
        InvestigationRequest(**d)

def test_copilot_does_not_infer_delta_t_from_misaligned_samples():
    d=case().model_dump(mode="json")
    # Both sensors are fresh but readings are five minutes apart.
    d["points"][0]=point("chw_supply_c",6,age=1)
    d["points"][1]=point("chw_return_c",8,age=6)
    req=InvestigationRequest(**d)
    r=analyze_evidence(req,now=NOW)
    assert r["overall_status"]=="insufficient_data"
    assert r["findings"][0]["code"]=="UNALIGNED_CHW_SAMPLES"
    assert r["control_commands"]==[]
