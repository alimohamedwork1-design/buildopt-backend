"""Phase 5 — semantic review workflow, audit, config versioning, RBAC."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.collection_config_service import CollectionConfigService, reset_collection_config_service
from app.services.gateway_token_store import GatewayTokenStore, reset_gateway_token_store
from app.services.semantic_audit_store import SemanticAuditStore, reset_semantic_audit_store
from app.services.semantic_mapping_service import (
    approve_registry_mapping,
    build_review_queue,
    edit_registry_mapping,
    reject_registry_mapping,
    revert_registry_mapping,
)
from app.services.telemetry_store import TelemetryStore, reset_telemetry_store


@pytest.fixture(autouse=True)
def fresh_store():
    store = TelemetryStore(":memory:")
    reset_telemetry_store(store)
    reset_gateway_token_store(GatewayTokenStore(store))
    reset_semantic_audit_store(SemanticAuditStore(store))
    reset_collection_config_service(CollectionConfigService(store))
    yield store
    reset_telemetry_store(None)
    reset_gateway_token_store(None)
    reset_semantic_audit_store(None)
    reset_collection_config_service(None)


@pytest.fixture
def client():
    return TestClient(app)


def _seed(store: TelemetryStore, *, sid: str, name: str, building: str = "b1", tenant: str = "tenant-a"):
    store.register_gateway(gateway_id="gw-1", tenant_id=tenant, building_id=building, connector_id="metasys")
    return store.upsert_raw_point(
        {
            "tenant_id": tenant,
            "building_id": building,
            "gateway_id": "gw-1",
            "connector_id": "metasys",
            "source": "metasys",
            "source_point_id": sid,
            "source_name": name,
            "raw_unit": "degC",
        }
    )


def test_review_queue_statuses(fresh_store):
    _seed(fresh_store, sid="obj-sat", name="AHU1 Supply Air Temp")
    points, _ = fresh_store.list_points(building_id="b1")
    queue = build_review_queue(points)
    assert len(queue) == 1
    assert queue[0]["status"] in ("SUGGESTED", "REVIEW_REQUIRED", "UNMAPPED")


def test_approve_reject_revert_audit(fresh_store):
    _seed(fresh_store, sid="obj-sat", name="SAT")
    approve_registry_mapping(
        fresh_store, building_id="b1", semantic_key="supply_air_temp", source_point_id="obj-sat", actor_user_id="u1"
    )
    audit = fresh_store.list_semantic_audit(building_id="b1")
    assert any(a["action"] == "APPROVED" for a in audit)

    reject_registry_mapping(fresh_store, building_id="b1", source_point_id="obj-sat", reason="wrong tag")
    meta = fresh_store.get_point(fresh_store.list_points(building_id="b1")[0][0]["id"]) if False else None
    p = fresh_store.list_points(building_id="b1")[0][0]
    assert p["metadata"]["mapping_status"] == "REJECTED"

    revert_registry_mapping(fresh_store, building_id="b1", source_point_id="obj-sat")
    p2 = fresh_store.get_point(p["id"])
    assert (p2.get("metadata") or {}).get("mapping_status") == "UNMAPPED"
    assert len(fresh_store.list_semantic_audit(building_id="b1")) >= 3


def test_edit_mapping(fresh_store):
    _seed(fresh_store, sid="obj-sat", name="SAT")
    edit_registry_mapping(
        fresh_store,
        building_id="b1",
        source_point_id="obj-sat",
        patch={"semantic_key": "supply_air_temp", "equipment_id": "AHU-01"},
        actor_user_id="u1",
    )
    p = fresh_store.list_points(building_id="b1")[0][0]
    assert p["metadata"]["equipment_id"] == "AHU-01"


def test_config_versioning_approved_only(fresh_store):
    _seed(fresh_store, sid="obj-sat", name="SAT")
    svc = CollectionConfigService(fresh_store)
    draft = svc.publish(building_id="b1", activate=False)
    assert draft["status"] == "DRAFT"
    assert draft["approved_count"] == 0

    approve_registry_mapping(
        fresh_store, building_id="b1", semantic_key="supply_air_temp", source_point_id="obj-sat"
    )
    active = svc.publish(building_id="b1", activate=True)
    assert active["status"] == "ACTIVE"
    assert active["approved_count"] == 1
    assert active["mapping"]["supply_air_temp"] == "obj-sat"

    fetched = svc.get_active(building_id="b1")
    assert fetched["config_version"] == active["config_version"]

    active2 = svc.publish(building_id="b1", activate=True)
    assert active2["mapping_revision"] > active["mapping_revision"]
    only_active = [
        v for v in fresh_store.list_config_versions("b1", limit=10) if v["status"] == "ACTIVE"
    ]
    assert len(only_active) == 1


def test_audit_chain_immutable(fresh_store):
    _seed(fresh_store, sid="obj-sat", name="SAT")
    approve_registry_mapping(
        fresh_store, building_id="b1", semantic_key="supply_air_temp", source_point_id="obj-sat", actor_user_id="u1"
    )
    edit_registry_mapping(
        fresh_store,
        building_id="b1",
        source_point_id="obj-sat",
        patch={"equipment_id": "AHU-01"},
        actor_user_id="u1",
    )
    reject_registry_mapping(fresh_store, building_id="b1", source_point_id="obj-sat", reason="wrong")
    revert_registry_mapping(fresh_store, building_id="b1", source_point_id="obj-sat")
    audit = fresh_store.list_semantic_audit(building_id="b1")
    actions = [a["action"] for a in audit]
    assert "APPROVED" in actions
    assert "EDITED" in actions
    assert "REJECTED" in actions
    assert "REVERTED" in actions
    assert len(audit) >= 4
    ids = {a["audit_id"] for a in audit}
    assert len(ids) == len(audit)


def test_tenant_isolation_building_mismatch(fresh_store):
    _seed(fresh_store, sid="obj-sat", name="SAT", building="b2")
    with pytest.raises(ValueError, match="source_point_not_found"):
        approve_registry_mapping(
            fresh_store, building_id="b1", semantic_key="supply_air_temp", source_point_id="obj-sat"
        )


def test_review_queue_endpoint(client, fresh_store):
    _seed(fresh_store, sid="obj-sat", name="AHU1 Supply Air Temp")
    res = client.get("/api/v1/semantic/buildings/b1/review-queue")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1


def test_gateway_scoped_config(client, fresh_store, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "master-key")
    _seed(fresh_store, sid="obj-sat", name="SAT")
    approve_registry_mapping(
        fresh_store, building_id="b1", semantic_key="supply_air_temp", source_point_id="obj-sat"
    )
    CollectionConfigService(fresh_store).publish(building_id="b1", gateway_id="gw-1", activate=True)
    token_store = GatewayTokenStore(fresh_store)
    issued = token_store.issue(gateway_id="gw-1")
    res = client.get(
        "/api/v1/gateways/gw-1/collection-config",
        headers={"X-API-Key": issued["token"]},
    )
    assert res.status_code == 200
    assert res.json()["mapping"]["supply_air_temp"] == "obj-sat"

    bad = client.get(
        "/api/v1/gateways/gw-other/collection-config",
        headers={"X-API-Key": issued["token"]},
    )
    assert bad.status_code == 403
