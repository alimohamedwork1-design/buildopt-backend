from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.schemas import JCICommand, JCIConnectionRequest
from app.services.bms_auto_connect import run_bms_auto_connect
from app.services.connection_store import connection_store
from app.services.jci_metasys import JCIMetasysClient
from app.services.log_handler import log_event
from app.services.metasys_auto_mapper import LOGICAL_KEYS, flatten_metasys_objects, suggest_mappings
from app.services.metasys_object_store import get_metasys_objects, list_all_mappings, set_metasys_objects
from app.utils.arabic_utils import bilingual_error, bilingual_success

router = APIRouter(prefix="/jci", tags=["jci"])


def _get_client() -> JCIMetasysClient:
    settings = get_settings()
    creds = connection_store.get_metasys()
    return JCIMetasysClient(
        host=creds.host or settings.jci_metasys_host,
        username=creds.username or settings.jci_metasys_username,
        password=creds.password or settings.jci_metasys_password,
        version=creds.version or settings.jci_metasys_version,
        demo_mode=settings.demo_mode,
    )


@router.post("/test-connection")
async def test_connection(body: JCIConnectionRequest) -> Dict[str, Any]:
    client = JCIMetasysClient(
        host=body.host,
        username=body.username,
        password=body.password,
        version=body.version,
        demo_mode=False,
    )
    result = await client.test_connection(body.host, body.username, body.password, body.version)
    if result.get("status") == "connected":
        log_event(
            "info",
            f"Metasys test connection succeeded ({result.get('response_ms')}ms)",
            "نجح اختبار اتصال Metasys",
        )
    return result


@router.post("/save-credentials")
async def save_credentials(body: JCIConnectionRequest) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.demo_mode:
        client = JCIMetasysClient(
            host=body.host,
            username=body.username,
            password=body.password,
            version=body.version,
            demo_mode=False,
        )
        test = await client.test_connection(body.host, body.username, body.password, body.version)
        if test.get("status") != "connected":
            raise HTTPException(status_code=400, detail=test)

    result = await connection_store.save_metasys(
        body.host,
        body.username,
        body.password,
        body.version,
    )
    auto = await run_bms_auto_connect(merge=True)
    result["auto_connect"] = auto
    log_event(
        "info",
        "Metasys credentials saved",
        "تم حفظ بيانات Metasys",
    )
    return result


@router.post("/network-diagnostic")
async def network_diagnostic(body: JCIConnectionRequest) -> Dict[str, Any]:
    settings = get_settings()
    client = JCIMetasysClient(
        host=body.host,
        username=body.username,
        password=body.password,
        version=body.version,
        demo_mode=settings.demo_mode,
    )
    return await client.network_diagnostic(body.host, body.username, body.password, body.version)


@router.get("/logical-keys")
async def list_logical_keys(domain: str = "hvac") -> Dict[str, Any]:
    if domain == "refrigeration":
        from app.services.refrigeration_auto_mapper import REFRIGERATION_LOGICAL_KEYS

        return {"domain": "refrigeration", "logical_keys": REFRIGERATION_LOGICAL_KEYS}
    return {"domain": "hvac", "logical_keys": LOGICAL_KEYS}


@router.post("/auto-connect")
async def auto_connect(merge: bool = True, force: bool = False) -> Dict[str, Any]:
    """Discover Metasys objects, auto-map all buildings, poll live telemetry."""
    return await run_bms_auto_connect(merge=merge, force=force)


@router.post("/buildings/{building_id}/objects/auto-map")
async def auto_map_building_objects(
    building_id: str,
    merge: bool = True,
    force: bool = False,
) -> Dict[str, Any]:
    from app.data.buildings_registry import get_building_config

    if not get_building_config(building_id):
        raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))

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
    current = get_metasys_objects(building_id)
    mapped = suggest_mappings(objects, current, merge=merge and not force)
    set_metasys_objects(building_id, mapped)
    from app.services.live_data_service import poll_metasys_buildings

    polled = await poll_metasys_buildings() if connection_store.has_saved_metasys() else 0
    return {
        "building_id": building_id,
        "metasys_objects": mapped,
        "discovered_objects": len(objects),
        "mapped_keys": sum(1 for k in LOGICAL_KEYS if mapped.get(k)),
        "polled_buildings": polled,
    }


@router.get("/buildings/{building_id}/objects")
async def get_building_objects(building_id: str) -> Dict[str, Any]:
    from app.data.buildings_registry import get_building_config

    if not get_building_config(building_id):
        raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))
    return {"building_id": building_id, "metasys_objects": get_metasys_objects(building_id)}


@router.put("/buildings/{building_id}/objects")
async def update_building_objects(building_id: str, body: Dict[str, str]) -> Dict[str, Any]:
    from app.data.buildings_registry import get_building_config

    if not get_building_config(building_id):
        raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))
    objects = set_metasys_objects(building_id, body)
    log_event("info", f"Metasys object map updated for {building_id}", "تم تحديث خريطة كائنات Metasys")
    return {"building_id": building_id, "metasys_objects": objects}


@router.get("/object-mappings")
async def list_object_mappings() -> Dict[str, Any]:
    return {"mappings": list_all_mappings()}


@router.get("/objects")
async def list_objects() -> Dict[str, Any]:
    client = _get_client()
    raw = await client.get_objects()
    items = flatten_metasys_objects(raw if isinstance(raw, (list, dict)) else {"items": raw})
    return {"objects": items, "count": len(items)}


@router.get("/objects/{object_id}/present-value")
async def get_present_value(object_id: str) -> Dict[str, Any]:
    client = _get_client()
    value = await client.get_present_value(object_id)
    if value is None:
        raise HTTPException(status_code=404, detail=bilingual_error("Object not found", "الكائن غير موجود"))
    return {"object_id": object_id, "present_value": value}


@router.post("/objects/{object_id}/command")
async def write_command(object_id: str, command: JCICommand) -> dict:
    client = _get_client()
    success = await client.write_command(object_id, command.attribute, command.value)
    if not success:
        raise HTTPException(status_code=502, detail=bilingual_error("Command failed", "فشل تنفيذ الأمر"))
    return {
        "success": True,
        "object_id": object_id,
        "message": bilingual_success("Command sent to Metasys", "تم إرسال الأمر إلى Metasys"),
    }


@router.get("/alarms")
async def get_alarms() -> List[Dict[str, Any]]:
    client = _get_client()
    return await client.get_alarms()


@router.get("/trends/{object_id}")
async def get_trend(object_id: str) -> List[Dict[str, Any]]:
    client = _get_client()
    return await client.get_trend(object_id)
