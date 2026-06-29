"""One-shot BMS connect: discover Metasys objects, auto-map, poll live data."""

from __future__ import annotations

from typing import Any, Dict, List

from app.config import get_settings
from app.data.buildings_registry import BUILDING_REGISTRY
from app.services.connection_store import connection_store
from app.services.jci_metasys import JCIMetasysClient
from app.services.live_data_service import poll_metasys_buildings
from app.services.log_handler import log_event
from app.services.metasys_auto_mapper import (
    LOGICAL_KEYS,
    flatten_metasys_objects,
    suggest_mappings,
)
from app.services.metasys_object_store import get_metasys_objects, set_metasys_objects


async def run_bms_auto_connect(*, merge: bool = True, force: bool = False) -> Dict[str, Any]:
    settings = get_settings()
    creds = connection_store.get_metasys()

    if not connection_store.has_saved_metasys() and not creds.host:
        return {
            "status": "not_configured",
            "message": "No Metasys credentials saved",
            "buildings": [],
            "mapped_keys_total": 0,
            "polled_buildings": 0,
        }

    client = JCIMetasysClient(
        host=creds.host,
        username=creds.username,
        password=creds.password,
        version=creds.version,
        demo_mode=settings.demo_mode,
    )

    try:
        raw_objects = await client.get_objects()
    except Exception as exc:
        log_event("error", f"Metasys object discovery failed: {exc}", "فشل اكتشاف كائنات Metasys")
        return {
            "status": "discovery_failed",
            "message": str(exc),
            "buildings": [],
            "mapped_keys_total": 0,
            "polled_buildings": 0,
        }

    objects = flatten_metasys_objects(raw_objects)
    building_results: List[Dict[str, Any]] = []
    mapped_total = 0

    for cfg in BUILDING_REGISTRY:
        building_id = cfg["id"]
        current = get_metasys_objects(building_id)
        merged = suggest_mappings(objects, current, merge=merge and not force)
        if merged != current or force:
            set_metasys_objects(building_id, merged)
        mapped_count = sum(1 for k in LOGICAL_KEYS if merged.get(k))
        mapped_total += mapped_count
        building_results.append(
            {
                "building_id": building_id,
                "building_name": cfg.get("name", building_id),
                "mapped_keys": mapped_count,
                "metasys_objects": merged,
                "discovered_objects": len(objects),
            }
        )

    polled = 0
    if not settings.demo_mode and connection_store.has_saved_metasys():
        polled = await poll_metasys_buildings()

    status = "connected" if mapped_total > 0 else "mapped_partial"
    log_event(
        "info",
        f"BMS auto-connect: {mapped_total} keys mapped, {polled} buildings polled",
        f"اتصال BMS تلقائي: {mapped_total} مفاتيح، {polled} مباني",
    )

    return {
        "status": status,
        "message": "Platform connected — object map updated and live poll started",
        "message_ar": "تم ربط المنصة — تحديث الخريطة وبدء القراءة الحية",
        "discovered_objects": len(objects),
        "mapped_keys_total": mapped_total,
        "polled_buildings": polled,
        "logical_keys": LOGICAL_KEYS,
        "buildings": building_results,
    }
