"""Generates module-specific payloads while preserving product truth.

Demo accounts may receive deterministic simulated content. Live accounts never receive
simulated domain values for modules that do not have a live/pilot/heuristic engine.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.data.modules_registry import get_category, get_module_capability
from app.models.provenance import build_provenance
from app.models.user_context import UserContext
from app.services import live_data_service
from app.services.data_policy import allows_simulated_telemetry, resolve_data_mode
from app.utils.gcc_features import get_ramadan_mode


def _seed(slug: str) -> random.Random:
    return random.Random(int(hashlib.md5(slug.encode()).hexdigest()[:8], 16))


def _rng_val(rng: random.Random, low: float, high: float, d: int = 1) -> float:
    return round(rng.uniform(low, high), d)


def _metric_cards(rng: random.Random, category: str) -> List[Dict[str, Any]]:
    base = {
        "overview": [("Energy Today", "kWh", 2400, 3200), ("Optimization", "/100", 72, 92), ("Alerts", "", 1, 5)],
        "telemetry": [("Points/min", "", 800, 900), ("Quality", "%", 95, 99), ("Latency", "ms", 30, 60)],
        "energy": [("Peak kW", "kW", 900, 1200), ("Savings", "%", 15, 23), ("Cost/hr", "AED", 250, 400)],
        "financial": [("ROI Saved", "AED", 120000, 180000), ("Run Rate", "AED/mo", 40000, 55000), ("Payback", "mo", 8, 14)],
        "carbon": [("CO₂ Avoided", "tCO₂e", 180, 220), ("Intensity", "kg/m²", 80, 120), ("Offset", "%", 12, 28)],
        "gcc": [("Prayer Adj", "", 4, 4), ("Ramadan", "", 0, 1), ("Sandstorm", "", 0, 1)],
    }.get(category, [("Score", "/100", 70, 95), ("Status", "", 0, 1), ("Trend", "%", -5, 8)])

    return [
        {
            "label": label,
            "unit": unit,
            "value": _rng_val(rng, lo, hi, 0 if unit in ("", "/100") else 1),
            "trend_pct": _rng_val(rng, -8, 12, 1),
        }
        for label, unit, lo, hi in base
    ]


def _empty_live_payload(
    slug: str,
    building_id: str,
    category: str,
    reason: str,
    capability: Dict[str, Any],
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    message = {
        "en": "No live data received for this module yet.",
        "ar": "لم يتم استلام بيانات حية لهذه الوحدة بعد.",
    }
    if reason == "CAPABILITY_NOT_IMPLEMENTED":
        message = {
            "en": "This module is not implemented as a live production engine yet.",
            "ar": "هذه الوحدة ليست منفذة بعد كمحرك إنتاج حي.",
        }

    return {
        "slug": slug or "overview",
        "path": f"/{slug}" if slug else "/",
        "category": category,
        "building_id": building_id,
        "timestamp": now.isoformat(),
        "fetched_at": now.isoformat().replace("+00:00", "Z"),
        "demo_mode": False,
        "data_origin": None,
        "empty_state": True,
        "reason": reason,
        "state": "NO_DATA",
        "message": message,
        "metric_cards": [],
        "charts": {},
        "recommendations": [],
        "recent_activity": [],
        "capability": capability,
        "provenance": build_provenance(source=None, mode="LIVE", building_id=building_id, quality="UNKNOWN"),
    }


async def get_module_data(
    slug: str,
    building_id: str = "burj-khalifa-01",
    user: Optional[UserContext] = None,
) -> Dict[str, Any]:
    normalized_slug = slug or "overview"
    category = get_category(slug)
    capability = get_module_capability(normalized_slug)
    now = datetime.now(timezone.utc)
    simulate = allows_simulated_telemetry(user)

    # Critical product-truth guard: a generic/concept UI must not become "live"
    # merely because a building has telemetry available.
    if not simulate and capability["maturity"] in {"simulated", "concept"}:
        payload = _empty_live_payload(
            slug,
            building_id,
            category,
            "CAPABILITY_NOT_IMPLEMENTED",
            capability,
        )
        if category == "gcc":
            payload["ramadan"] = get_ramadan_mode().model_dump(mode="json")
        return payload

    live_data = await live_data_service.get_live_data(building_id, user=user)
    is_demo = simulate and (live_data is None or live_data.demo_mode)

    if not simulate and live_data is None:
        payload = _empty_live_payload(slug, building_id, category, "NO_TELEMETRY", capability)
        if category == "gcc":
            payload["ramadan"] = get_ramadan_mode().model_dump(mode="json")
        return payload

    rng = _seed(f"{slug}-{building_id}") if simulate else None

    payload: Dict[str, Any] = {
        "slug": normalized_slug,
        "path": f"/{slug}" if slug else "/",
        "category": category,
        "building_id": building_id,
        "timestamp": now.isoformat(),
        "fetched_at": now.isoformat().replace("+00:00", "Z"),
        "demo_mode": is_demo,
        "data_origin": live_data.source if live_data else ("SIMULATED" if simulate else None),
        "mode": resolve_data_mode(user),
        "state": "LIVE" if live_data and not is_demo else ("NO_DATA" if not simulate and not live_data else "DEMO"),
        "capability": capability,
    }

    if simulate and rng is not None:
        payload["metric_cards"] = _metric_cards(rng, category)

    if live_data:
        payload["live"] = live_data.model_dump(mode="json")
        payload["demo_mode"] = live_data.demo_mode
        if not live_data.demo_mode:
            payload["metric_cards"] = _live_metric_cards(live_data, category)
            payload["charts"] = _live_charts(live_data, building_id, user=user)

    if category in ("overview", "telemetry", "equipment", "optimization"):
        equipment = live_data_service.list_equipment(building_id, user=user)
        payload["equipment"] = [e.model_dump(mode="json") for e in equipment]
        alerts = live_data_service.list_alerts(user=user)
        payload["alerts_count"] = len(alerts)

    if category in ("overview", "energy", "financial", "telemetry"):
        consumption = live_data_service.get_energy_consumption(building_id, user=user)
        if consumption:
            payload["energy"] = consumption.model_dump(mode="json")
        savings = live_data_service.get_energy_savings(building_id, user=user)
        if savings:
            payload["savings"] = savings.model_dump(mode="json")
        forecast = live_data_service.get_energy_forecast(building_id, user=user)
        if forecast:
            payload["forecast"] = forecast.model_dump(mode="json")

    if category in ("energy", "gcc", "financial"):
        tariff = live_data_service.get_dewa_tariff(building_id, user=user)
        if tariff:
            payload["dewa_tariff"] = tariff.model_dump(mode="json")

    if category in ("alerts", "fault_prediction", "overview"):
        payload["alerts"] = [a.model_dump(mode="json") for a in live_data_service.list_alerts(user=user)]
        payload["fdd"] = [f.model_dump(mode="json") for f in live_data_service.list_fdd_results(user=user)]

    if category == "gcc":
        payload["ramadan"] = get_ramadan_mode().model_dump(mode="json")

    if category in ("overview", "telemetry", "optimization"):
        metrics = live_data_service.get_building_metrics(building_id, "24h", user=user)
        if metrics:
            payload["metrics_24h"] = metrics.model_dump(mode="json")

    if is_demo and rng is not None:
        payload["recommendations"] = _recommendations(rng, category)
        payload["recent_activity"] = _activity(rng, category)
        if "charts" not in payload:
            payload["charts"] = _charts(rng, category)
    elif live_data:
        payload["recommendations"] = _live_recommendations(live_data, category)
        payload["recent_activity"] = _live_activity(live_data, category)
    else:
        payload.setdefault("recommendations", [])
        payload.setdefault("recent_activity", [])
        payload.setdefault("charts", {})

    if slug == "industrial-refrigeration":
        refrig = await live_data_service.get_refrigeration_snapshot(building_id)
        if refrig:
            payload["refrigeration"] = refrig

    payload["provenance"] = build_provenance(
        source=payload.get("data_origin"),
        mode="DEMO" if is_demo else "LIVE",
        building_id=building_id,
        connector=str(payload.get("data_origin") or "") or None,
        quality="GOOD" if live_data and not is_demo else "UNKNOWN",
        observed_at=now,
    )

    return payload


def _live_metric_cards(live, category: str) -> List[Dict[str, Any]]:
    cards = [
        {"label": "Peak kW", "unit": "kW", "value": round(live.energy.total_kw, 1), "trend_pct": None},
        {"label": "HVAC COP", "unit": "", "value": live.hvac.cop, "trend_pct": None},
        {"label": "CO₂", "unit": "ppm", "value": live.environment.co2_ppm, "trend_pct": None},
        {"label": "Alerts", "unit": "", "value": live.active_alerts, "trend_pct": None},
    ]
    if category == "energy":
        cards[0] = {"label": "Cost/hr", "unit": "AED", "value": live.energy.cost_per_hour, "trend_pct": None}
    return cards


def _live_charts(live, building_id: str, user: Optional[UserContext] = None) -> Dict[str, Any]:
    metrics = live_data_service.get_building_metrics(building_id, "24h", user=user)
    energy_kwh: List[Dict[str, Any]] = []
    if metrics and metrics.metrics:
        for point in metrics.metrics[:24]:
            if point.metric != "total_kw":
                continue
            energy_kwh.append(
                {
                    "timestamp": point.timestamp.isoformat(),
                    "hour": point.timestamp.hour if hasattr(point.timestamp, "hour") else 0,
                    "actual": round(point.value, 1),
                    # Do not fabricate a predicted series. Forecast is supplied separately
                    # by the history-based forecasting service when enough history exists.
                    "predicted": None,
                }
            )
    if not energy_kwh:
        energy_kwh = [{"timestamp": live.timestamp.isoformat(), "hour": live.timestamp.hour, "actual": round(live.energy.total_kw, 1), "predicted": None}]
    return {
        "energy_kwh": energy_kwh,
        "optimization_score": [],
        "prediction_available": False,
    }


def _live_recommendations(live, category: str) -> List[Dict[str, Any]]:
    """Transparent rule-based operational observations.

    No monetary saving is invented here. Verified/potential savings come from the
    dedicated savings/M&V service, not this generic module composer.
    """
    recs: List[Dict[str, Any]] = []
    if live.hvac.cop < 3.5:
        recs.append({
            "priority": "HIGH",
            "title": "Chiller COP below target",
            "estimated_savings_aed_per_month": None,
            "category": category,
            "method": "rule_based_observation",
            "evidence": {"cop": live.hvac.cop, "threshold": 3.5},
        })
    if live.environment.co2_ppm > 800:
        recs.append({
            "priority": "MED",
            "title": "Ventilation review recommended — CO₂ elevated",
            "estimated_savings_aed_per_month": None,
            "category": category,
            "method": "rule_based_observation",
            "evidence": {"co2_ppm": live.environment.co2_ppm, "threshold": 800},
        })
    if not recs:
        recs.append({
            "priority": "LOW",
            "title": "No rule-based exception detected in current snapshot",
            "estimated_savings_aed_per_month": None,
            "category": category,
            "method": "rule_based_observation",
            "evidence": {},
        })
    return recs


def _live_activity(live, category: str) -> List[Dict[str, Any]]:
    return [
        {
            "message": f"Live snapshot: {live.energy.total_kw:.0f} kW total demand",
            "minutes_ago": 0,
            "category": category,
        },
        {
            "message": f"HVAC COP {live.hvac.cop} · Supply air {live.hvac.supply_air_temp}°C",
            "minutes_ago": 1,
            "category": category,
        },
    ]


def _recommendations(rng: random.Random, category: str) -> List[Dict[str, Any]]:
    pool = [
        ("HIGH", "Optimize Chiller Staging", 166),
        ("HIGH", "AHU Filter Replacement", 56),
        ("MED", "Enable Night Setback Zones", 189),
        ("MED", "Adjust DEWA Peak Shaving", 240),
        ("LOW", "Recalibrate CO₂ Sensors", 22),
    ]
    rng.shuffle(pool)
    return [
        {
            "priority": p,
            "title": t,
            "savings_aed_per_month": s,
            "category": category,
            "method": "demo_simulation",
        }
        for p, t, s in pool[:3]
    ]


def _activity(rng: random.Random, category: str) -> List[Dict[str, Any]]:
    events = [
        "AHU-2 supply air hunting detected — FDD-107",
        "Chiller #1 COP below threshold",
        "Zone Z14 CO₂ returned to normal",
        "Daily energy report generated",
        "Peak demand forecast updated",
    ]
    return [
        {"message": msg, "minutes_ago": rng.randint(2, 180), "category": category}
        for msg in events[:4]
    ]


def _charts(rng: random.Random, category: str) -> Dict[str, Any]:
    hours = list(range(24))
    return {
        "energy_kwh": [{"hour": h, "actual": _rng_val(rng, 40, 90, 0), "predicted": _rng_val(rng, 42, 88, 0)} for h in hours],
        "optimization_score": [{"hour": h, "score": _rng_val(rng, 70, 95, 0)} for h in hours[::2]],
        "simulation": True,
    }
