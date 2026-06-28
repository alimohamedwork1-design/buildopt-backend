from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.schemas import JCICommand, JCIConnectionRequest
from app.services.connection_store import connection_store
from app.services.jci_metasys import JCIMetasysClient
from app.services.log_handler import log_event
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
    settings = get_settings()
    client = JCIMetasysClient(
        host=body.host,
        username=body.username,
        password=body.password,
        version=body.version,
        demo_mode=settings.demo_mode,
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


@router.get("/objects")
async def list_objects() -> List[Dict[str, Any]]:
    client = _get_client()
    return await client.get_objects()


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
