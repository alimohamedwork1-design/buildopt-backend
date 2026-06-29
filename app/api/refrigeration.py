from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.data.buildings_registry import get_building_config
from app.services.connection_store import connection_store
from app.services.jci_metasys import JCIMetasysClient
from app.services.refrigeration_auto_mapper import (
    REFRIGERATION_LOGICAL_KEYS,
    flatten_metasys_objects,
    suggest_refrigeration_mappings,
)
from app.services.refrigeration_connection_store import (
    get_refrigeration_connection,
    set_refrigeration_connection,
)
from app.services.refrigeration_map_store import get_bacnet_map, get_modbus_map, set_bacnet_map, set_modbus_map
from app.services.refrigeration_object_store import get_refrigeration_objects, set_refrigeration_objects
from app.services.refrigeration_poll import get_cached_snapshot, poll_building
from app.utils.arabic_utils import bilingual_error

router = APIRouter(prefix="/refrigeration", tags=["refrigeration"])


def _require_building(building_id: str) -> Dict[str, Any]:
    cfg = get_building_config(building_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))
    return cfg


@router.get("/logical-keys")
async def list_logical_keys() -> Dict[str, Any]:
    return {"domain": "refrigeration", "logical_keys": REFRIGERATION_LOGICAL_KEYS}


@router.get("/buildings/{building_id}/objects")
async def get_building_objects(building_id: str) -> Dict[str, Any]:
    _require_building(building_id)
    return {"building_id": building_id, "refrigeration_objects": get_refrigeration_objects(building_id)}


@router.put("/buildings/{building_id}/objects")
async def put_building_objects(building_id: str, body: Dict[str, str]) -> Dict[str, Any]:
    _require_building(building_id)
    objects = body.get("refrigeration_objects") or body.get("objects") or body
    if not isinstance(objects, dict):
        raise HTTPException(status_code=400, detail="Expected object map")
    saved = set_refrigeration_objects(building_id, objects)
    return {"building_id": building_id, "refrigeration_objects": saved}


@router.post("/buildings/{building_id}/objects/auto-map")
async def auto_map_building(building_id: str, merge: bool = True, force: bool = False) -> Dict[str, Any]:
    _require_building(building_id)
    settings = get_settings()
    creds = connection_store.get_metasys()
    client = JCIMetasysClient(
        host=creds.host,
        username=creds.username,
        password=creds.password,
        version=creds.version,
        demo_mode=settings.demo_mode,
    )
    raw = await client.get_objects()
    objects = flatten_metasys_objects(raw)
    current = get_refrigeration_objects(building_id)
    mapped = suggest_refrigeration_mappings(objects, current, merge=merge and not force)
    set_refrigeration_objects(building_id, mapped)
    polled = await poll_building(building_id) if connection_store.has_saved_metasys() else None
    return {
        "building_id": building_id,
        "refrigeration_objects": mapped,
        "discovered_objects": len(objects),
        "mapped_keys": sum(1 for k in REFRIGERATION_LOGICAL_KEYS if mapped.get(k)),
        "snapshot": polled,
    }


@router.get("/buildings/{building_id}/connection")
async def get_connection(building_id: str) -> Dict[str, Any]:
    _require_building(building_id)
    return {"building_id": building_id, **get_refrigeration_connection(building_id)}


@router.put("/buildings/{building_id}/connection")
async def put_connection(building_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    _require_building(building_id)
    saved = set_refrigeration_connection(building_id, body)
    snapshot = await poll_building(building_id)
    return {"building_id": building_id, **saved, "snapshot": snapshot}


@router.post("/buildings/{building_id}/test-connection")
async def test_connection(building_id: str) -> Dict[str, Any]:
    _require_building(building_id)
    snapshot = await poll_building(building_id)
    conn = get_refrigeration_connection(building_id)
    ok = snapshot is not None and bool(snapshot.get("readings"))
    return {
        "building_id": building_id,
        "status": "connected" if ok else "disconnected",
        "source": conn.get("source"),
        "readings_count": len(snapshot.get("readings", {})) if snapshot else 0,
        "snapshot": snapshot,
    }


@router.get("/buildings/{building_id}/modbus-map")
async def get_modbus(building_id: str) -> Dict[str, Any]:
    _require_building(building_id)
    return {"building_id": building_id, "modbus_map": get_modbus_map(building_id)}


@router.put("/buildings/{building_id}/modbus-map")
async def put_modbus(building_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    _require_building(building_id)
    mapping = body.get("modbus_map") or body
    saved = set_modbus_map(building_id, mapping)
    return {"building_id": building_id, "modbus_map": saved}


@router.get("/buildings/{building_id}/bacnet-map")
async def get_bacnet(building_id: str) -> Dict[str, Any]:
    _require_building(building_id)
    return {"building_id": building_id, "bacnet_map": get_bacnet_map(building_id)}


@router.put("/buildings/{building_id}/bacnet-map")
async def put_bacnet(building_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    _require_building(building_id)
    mapping = body.get("bacnet_map") or body
    saved = set_bacnet_map(building_id, mapping)
    return {"building_id": building_id, "bacnet_map": saved}


@router.get("/snapshot/{building_id}")
async def get_snapshot(building_id: str) -> Dict[str, Any]:
    _require_building(building_id)
    cached = get_cached_snapshot(building_id)
    if cached:
        return cached
    snapshot = await poll_building(building_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=bilingual_error("No refrigeration data", "لا توجد بيانات تبريد"))
    return snapshot
