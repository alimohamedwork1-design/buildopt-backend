from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.schemas import JCICommand
from app.services import demo_mode
from app.services.jci_metasys import JCIMetasysClient
from app.utils.arabic_utils import bilingual_error, bilingual_success

router = APIRouter(prefix="/jci", tags=["jci"])


def _get_client() -> JCIMetasysClient:
    settings = get_settings()
    return JCIMetasysClient(
        host=settings.jci_metasys_host,
        username=settings.jci_metasys_username,
        password=settings.jci_metasys_password,
        version=settings.jci_metasys_version,
        demo_mode=settings.demo_mode,
    )


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
