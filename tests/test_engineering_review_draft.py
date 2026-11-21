"""Engineer's workbench is a DRAFT generator, not a control system."""
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.deps.auth import get_required_user
from app.main import app
from app.models.user_context import UserContext


def payload(**extra):
    return dict(
        building_id="site-a",
        fault_id="FDD-17",
        asset_id="AHU-2",
        rule_id="low-delta-t",
        observed_at=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat(),
        measured_points=["AHU-2.SAT","AHU-2.RAT"],
        question="What should an engineer verify?",
        **extra,
    )


def test_authentication_required():
    response = TestClient(app).post("/api/v1/engineering/review-draft",json=payload())
    assert response.status_code==401


def test_building_scope_cannot_cross_tenants():
    app.dependency_overrides[get_required_user]=lambda: UserContext(
        user_id="operator-a", authenticated=True, building_ids=["site-a"],
    )
    try:
        client=TestClient(app)
        allowed=client.post("/api/v1/engineering/review-draft",json=payload())
        denied=client.post("/api/v1/engineering/review-draft",json={
            **payload(), "building_id":"site-b",
        })
        assert allowed.status_code==200
        assert denied.status_code==403
        body=allowed.json()
        assert body["source_integrity"]=="UNVERIFIED_OPERATOR_SUPPLIED_REFERENCES"
        assert body["readings_fetched"] is False
        assert body["fault_confirmed"] is False
        assert body["confidence"] is None
        assert body["verified_savings"] is None
        assert body["writeback_enabled"] is False
        assert body["automatic_work_order_created"] is False
        assert body["review_required"] is True
        assert len(body["draft"]["evidence_refs"])==2
    finally:
        app.dependency_overrides.clear()


def test_writeback_prohibited_even_for_authorized_user():
    app.dependency_overrides[get_required_user]=lambda: UserContext(
        user_id="operator-a", authenticated=True, building_ids=["site-a"],
    )
    try:
        client=TestClient(app)
        body=payload()
        body["request_writeback"]=True
        response=client.post("/api/v1/engineering/review-draft",json=body)
        assert response.status_code==403
    finally:
        app.dependency_overrides.clear()


def test_bad_timestamp_and_unbounded_payload_rejected():
    app.dependency_overrides[get_required_user]=lambda: UserContext(
        user_id="operator-a", authenticated=True, building_ids=["site-a"],
    )
    try:
        client=TestClient(app)
        for patch in (
            {"observed_at":"2026-11-21T11:01:00"},
            {"observed_at":(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()},
            {"measured_points":[]},
            {"measured_points":[f"POINT-{i}" for i in range(40)]},
        ):
            response=client.post("/api/v1/engineering/review-draft",json={**payload(),**patch})
            assert response.status_code==422
    finally:
        app.dependency_overrides.clear()
