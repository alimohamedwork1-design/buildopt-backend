"""Pilot OS orchestration for real-site onboarding and operations.

This module composes existing durable BuildOpt services. It does not fabricate live data:
unknown/unconfigured inputs remain explicit blockers and do not receive placeholder values.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from app.models.user_context import UserContext
from app.services import live_data_service
from app.services.building_store import get_connection
from app.services.data_health_engine import registry_building_data_health
from app.services.edge_heartbeat_store import edge_heartbeat_store
from app.services.fdd_fault_store import get_fdd_fault_store
from app.services.recommendations_store import list_recommendations
from app.services.savings_engine import list_opportunities
from app.services.telemetry_store import get_telemetry_store


FDD_RULE_PACKS: Sequence[Dict[str, Any]] = (
    {
        "id": "energy_metering",
        "name": "Energy Metering",
        "description": "Whole-building demand monitoring and anomaly prerequisites.",
        "required_semantic_keys": ["total_kw"],
        "optional_semantic_keys": ["hvac_power_kw"],
    },
    {
        "id": "ahu_thermal",
        "name": "AHU Thermal",
        "description": "Supply/return-air thermal diagnostics and delta-T checks.",
        "required_semantic_keys": ["supply_air_temp", "return_air_temp"],
        "optional_semantic_keys": ["hvac_power_kw", "temp_c"],
    },
    {
        "id": "hvac_efficiency",
        "name": "HVAC Efficiency",
        "description": "Power-versus-thermal-response diagnostics for connected HVAC assets.",
        "required_semantic_keys": ["hvac_power_kw", "supply_air_temp", "return_air_temp"],
        "optional_semantic_keys": ["total_kw"],
    },
    {
        "id": "iaq_core",
        "name": "Indoor Air Quality",
        "description": "Core comfort/IAQ monitoring prerequisites.",
        "required_semantic_keys": ["temp_c", "co2_ppm"],
        "optional_semantic_keys": ["humidity_pct", "pm25"],
    },
)


MODEL_REGISTRY: Sequence[Dict[str, Any]] = (
    {
        "id": "energy_forecast_gbr_v1",
        "display_name": "Energy Forecast",
        "implementation": "gradient_boosting_autoregressive",
        "maturity": "pilot",
        "training_mode": "per-building history",
        "minimum_observations": 48,
        "validation": "chronological holdout MAE",
        "persistent_artifact": False,
        "drift_monitoring": "not_implemented",
        "writeback": False,
    },
    {
        "id": "anomaly_isolation_forest_pilot",
        "display_name": "Anomaly Detection",
        "implementation": "isolation_forest_fit_on_request",
        "maturity": "pilot",
        "training_mode": "fit on supplied site observations",
        "minimum_observations": None,
        "validation": "site validation required",
        "persistent_artifact": False,
        "drift_monitoring": "not_implemented",
        "writeback": False,
    },
    {
        "id": "fdd_rules_v1",
        "display_name": "Fault Detection & Diagnostics",
        "implementation": "deterministic_rule_framework",
        "maturity": "pilot",
        "training_mode": "not_applicable",
        "minimum_observations": None,
        "validation": "rule evidence + site commissioning",
        "persistent_artifact": True,
        "drift_monitoring": "not_applicable",
        "writeback": False,
    },
    {
        "id": "optimization_shadow_v1",
        "display_name": "Shadow Optimization",
        "implementation": "bounded_rule_advisor",
        "maturity": "heuristic",
        "training_mode": "not_applicable",
        "minimum_observations": None,
        "validation": "human approval + M&V required",
        "persistent_artifact": False,
        "drift_monitoring": "not_applicable",
        "writeback": False,
    },
)


def _serialize_dt(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _state_counts(items: Iterable[Any], attr: str = "state") -> Dict[str, int]:
    values: List[str] = []
    for item in items:
        if isinstance(item, dict):
            raw = item.get(attr)
        else:
            raw = getattr(item, attr, None)
        if raw is None:
            continue
        raw = getattr(raw, "value", raw)
        values.append(str(raw))
    return dict(Counter(values))


def _approved_semantic_keys(points: Sequence[Dict[str, Any]]) -> Set[str]:
    out: Set[str] = set()
    for point in points:
        meta = point.get("metadata") or {}
        if meta.get("mapping_status") == "APPROVED" and meta.get("semantic_key"):
            out.add(str(meta["semantic_key"]))
    return out


def evaluate_rule_packs(approved_keys: Set[str]) -> List[Dict[str, Any]]:
    packs: List[Dict[str, Any]] = []
    for pack in FDD_RULE_PACKS:
        required = set(pack["required_semantic_keys"])
        optional = set(pack["optional_semantic_keys"])
        missing = sorted(required - approved_keys)
        available_optional = sorted(optional & approved_keys)
        packs.append(
            {
                **pack,
                "ready": not missing,
                "missing_required": missing,
                "available_optional": available_optional,
                "required_coverage_pct": round(
                    100.0 * (len(required) - len(missing)) / max(1, len(required)), 1
                ),
            }
        )
    return packs


def model_registry() -> List[Dict[str, Any]]:
    return [dict(row) for row in MODEL_REGISTRY]


def _step(
    step_id: str,
    label: str,
    *,
    weight: int,
    status: str,
    detail: str,
    route: str,
    blockers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "id": step_id,
        "label": label,
        "weight": weight,
        "status": status,
        "complete": status == "READY",
        "detail": detail,
        "route": route,
        "blockers": blockers or [],
    }


def _readiness_score(steps: Sequence[Dict[str, Any]]) -> int:
    earned = 0.0
    total = 0.0
    for row in steps:
        weight = float(row["weight"])
        total += weight
        status = row["status"]
        if status == "READY":
            earned += weight
        elif status == "PARTIAL":
            earned += weight * 0.5
    return round(100 * earned / total) if total else 0


async def build_pilot_summary(user: UserContext, building_id: str) -> Dict[str, Any]:
    store = get_telemetry_store()
    tenant_id = user.user_id if user.authenticated and user.is_live_account else None
    points, total_points = store.list_points(
        tenant_id=tenant_id,
        building_id=building_id,
        limit=500,
    )
    approved_keys = _approved_semantic_keys(points)
    approved_points = sum(
        1 for p in points if (p.get("metadata") or {}).get("mapping_status") == "APPROVED"
    )
    mapping_pct = round((approved_points / total_points) * 100.0, 1) if total_points else 0.0

    health = registry_building_data_health(points)
    health_summary = health.get("building_summary") or {}
    health_availability = float(health_summary.get("availability_pct") or 0.0)

    gateways = [g for g in edge_heartbeat_store.list_gateways() if g.get("building_id") == building_id]
    if user.authenticated and user.is_live_account:
        gateways = [g for g in gateways if not g.get("tenant_id") or g.get("tenant_id") == user.user_id]
    gateway_states = _state_counts(gateways, "state")

    connection = await get_connection(building_id)
    connection_status = (connection or {}).get("status")
    connected = connection_status == "connected" or any(
        g.get("state") in {"ONLINE", "DEGRADED", "STALE"} for g in gateways
    )
    connection_kind = (connection or {}).get("protocol") or (connection or {}).get("bms_vendor")
    if not connection_kind and gateways:
        connection_kind = gateways[0].get("connector_id") or gateways[0].get("protocol")

    rule_packs = evaluate_rule_packs(approved_keys)
    ready_rule_packs = sum(1 for p in rule_packs if p["ready"])

    metrics = live_data_service.get_building_metrics(building_id, "7d", user=user)
    observations = 0
    if metrics is not None:
        observations = sum(1 for p in metrics.metrics if p.metric == "total_kw")
    baseline_ready = observations >= 48

    faults = get_fdd_fault_store().list_active(building_id, limit=100)
    recommendations = list_recommendations(building_id, limit=100)
    savings = list_opportunities(building_id, limit=100)
    verified_savings_aed = round(
        sum(float(o.verified_saving_aed or 0.0) for o in savings if getattr(o.state, "value", o.state) == "VERIFIED"),
        2,
    )

    connection_status_for_step = "READY" if connected else "BLOCKED"
    discovery_status = "READY" if total_points > 0 else "BLOCKED"
    if total_points == 0:
        mapping_status = "BLOCKED"
    elif mapping_pct >= 90:
        mapping_status = "READY"
    else:
        mapping_status = "PARTIAL"
    if health_availability >= 90:
        health_status = "READY"
    elif total_points > 0 and health_availability > 0:
        health_status = "PARTIAL"
    else:
        health_status = "BLOCKED"
    if ready_rule_packs == len(rule_packs):
        fdd_status = "READY"
    elif ready_rule_packs > 0:
        fdd_status = "PARTIAL"
    else:
        fdd_status = "BLOCKED"

    steps = [
        _step(
            "building",
            "Building registered",
            weight=10,
            status="READY" if building_id else "BLOCKED",
            detail=building_id or "No building selected",
            route="/portfolio",
            blockers=[] if building_id else ["Create or select a building"],
        ),
        _step(
            "connection",
            "BMS / edge connection",
            weight=20,
            status=connection_status_for_step,
            detail=f"Connected via {connection_kind}" if connected and connection_kind else ("Connection healthy" if connected else "No healthy building connection detected"),
            route="/integration",
            blockers=[] if connected else ["Configure and test a building-scoped BMS or edge gateway"],
        ),
        _step(
            "discovery",
            "Point discovery",
            weight=10,
            status=discovery_status,
            detail=f"{total_points} registered points",
            route="/tag-mapper",
            blockers=[] if total_points else ["Discover or ingest BMS points"],
        ),
        _step(
            "mapping",
            "Semantic mapping",
            weight=20,
            status=mapping_status,
            detail=f"{approved_points}/{total_points} points approved ({mapping_pct}%)" if total_points else "No points available for mapping",
            route="/tag-mapper",
            blockers=[] if mapping_status == "READY" else [f"Approve remaining semantic mappings ({mapping_pct}% complete)"],
        ),
        _step(
            "data_health",
            "Data health",
            weight=15,
            status=health_status,
            detail=f"{health_availability}% healthy availability across {health_summary.get('point_count', 0)} points",
            route="/data-health",
            blockers=[] if health_status == "READY" else ["Resolve stale, missing, or invalid telemetry"],
        ),
        _step(
            "fdd_readiness",
            "FDD rule-pack readiness",
            weight=10,
            status=fdd_status,
            detail=f"{ready_rule_packs}/{len(rule_packs)} core rule packs ready",
            route="/fdd",
            blockers=[] if fdd_status == "READY" else ["Map the required semantic keys for blocked rule packs"],
        ),
        _step(
            "baseline",
            "Energy baseline history",
            weight=10,
            status="READY" if baseline_ready else ("PARTIAL" if observations else "BLOCKED"),
            detail=f"{observations} total-kW observations available; minimum 48",
            route="/roi",
            blockers=[] if baseline_ready else [f"Collect {max(0, 48 - observations)} more total-kW observations"],
        ),
        _step(
            "workflow",
            "Human approval & M&V workflow",
            weight=5,
            status="READY",
            detail="Recommendation lifecycle and savings verification stores are enabled",
            route="/ai-recommendations",
        ),
    ]

    score = _readiness_score(steps)
    blockers = [b for step in steps for b in step["blockers"]]
    state = "PILOT_READY" if score >= 90 and not blockers else "PILOT_BLOCKED" if score < 50 else "PILOT_PARTIAL"

    recommendation_counts = _state_counts(recommendations)
    savings_counts = _state_counts(savings)
    fault_severity_counts = dict(Counter(str(f.get("severity") or "unknown") for f in faults))

    operations = {
        "active_faults": len(faults),
        "faults_by_severity": fault_severity_counts,
        "recommendations": recommendation_counts,
        "recommendations_awaiting_approval": recommendation_counts.get("RECOMMENDED", 0),
        "savings": savings_counts,
        "verified_savings_aed": verified_savings_aed,
        "data_health": health_summary,
        "gateway_states": gateway_states,
        "priority_actions": blockers[:8],
    }

    connections = {
        "building_id": building_id,
        "configured": bool(connection) or bool(gateways),
        "connected": connected,
        "connection_type": connection_kind,
        "connection_status": connection_status or ("edge" if gateways else "not_configured"),
        "gateway_count": len(gateways),
        "gateways": [
            {
                "gateway_id": g.get("gateway_id"),
                "connector_id": g.get("connector_id"),
                "version": g.get("version"),
                "state": g.get("state"),
                "freshness_seconds": g.get("freshness_seconds"),
                "telemetry_rate_per_minute": g.get("telemetry_rate_per_minute"),
                "queue_depth": g.get("queue_depth"),
                "clock_drift_seconds": g.get("clock_drift_seconds"),
                "connector_error": g.get("connector_error"),
                "last_successful_upload_at": _serialize_dt(g.get("last_successful_upload_at")),
            }
            for g in gateways
        ],
        "supported_connectors": [
            {"id": "metasys", "transport": "REST v4/v5", "state": "implemented"},
            {"id": "bacnet_ip", "transport": "BACnet/IP", "state": "connector_foundation"},
            {"id": "modbus_tcp", "transport": "Modbus TCP", "state": "connector_foundation"},
            {"id": "mqtt", "transport": "MQTT", "state": "connector_foundation"},
            {"id": "opc_ua", "transport": "OPC-UA", "state": "planned"},
        ],
    }

    return {
        "building_id": building_id,
        "account_mode": user.account_mode,
        "state": state,
        "readiness_score": score,
        "steps": steps,
        "blockers": blockers,
        "points": {
            "total": total_points,
            "approved_mappings": approved_points,
            "mapping_pct": mapping_pct,
            "approved_semantic_keys": sorted(approved_keys),
        },
        "data_health": health,
        "rule_packs": rule_packs,
        "connections": connections,
        "operations": operations,
        "models": model_registry(),
        "notifications": {
            "configured_channels": [],
            "state": "NOT_CONFIGURED",
            "supported_channels": ["email", "microsoft_teams", "slack", "webhook"],
            "note": "No notification channel is claimed until credentials/configuration are stored.",
        },
        "safety": {
            "optimization_mode": "shadow_only",
            "automatic_writeback": False,
            "human_approval_required": True,
            "verified_savings_only": True,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
