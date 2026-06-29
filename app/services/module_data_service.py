"""Generates module-specific payloads for all build-opt.site pages."""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.data.modules_registry import get_category
from app.services import live_data_service
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


async def get_module_data(slug: str, building_id: str = "burj-khalifa-01") -> Dict[str, Any]:
    category = get_category(slug)
    rng = _seed(f"{slug}-{building_id}")
    now = datetime.now(timezone.utc)

    live_data = await live_data_service.get_live_data(building_id)
    is_demo = live_data is None or live_data.demo_mode

    payload: Dict[str, Any] = {
        "slug": slug or "overview",
        "path": f"/{slug}" if slug else "/",
        "category": category,
        "building_id": building_id,
        "timestamp": now.isoformat(),
        "fetched_at": now.isoformat().replace("+00:00", "Z"),
        "metric_cards": _metric_cards(rng, category),
        "demo_mode": is_demo,
    }

    if live_data:
        payload["live"] = live_data.model_dump(mode="json")
        payload["demo_mode"] = live_data.demo_mode
        if not live_data.demo_mode:
            payload["metric_cards"] = _live_metric_cards(live_data, category)
            payload["charts"] = _live_charts(live_data, building_id)

    if category in ("overview", "telemetry", "equipment", "optimization"):
        payload["equipment"] = [e.model_dump(mode="json") for e in live_data_service.list_equipment(building_id)]
        payload["alerts_count"] = len(live_data_service.list_alerts())

    if category in ("overview", "energy", "financial", "telemetry"):
        payload["energy"] = live_data_service.get_energy_consumption().model_dump(mode="json")
        payload["savings"] = live_data_service.get_energy_savings().model_dump(mode="json")
        payload["forecast"] = live_data_service.get_energy_forecast(building_id).model_dump(mode="json")

    if category in ("energy", "gcc", "financial"):
        payload["dewa_tariff"] = live_data_service.get_dewa_tariff().model_dump(mode="json")

    if category in ("alerts", "fault_prediction", "overview"):
        payload["alerts"] = [a.model_dump(mode="json") for a in live_data_service.list_alerts()]
        payload["fdd"] = [f.model_dump(mode="json") for f in live_data_service.list_fdd_results()]

    if category == "gcc":
        payload["ramadan"] = get_ramadan_mode().model_dump(mode="json")

    if category in ("overview", "telemetry", "optimization"):
        metrics = live_data_service.get_building_metrics(building_id, "24h")
        if metrics:
            payload["metrics_24h"] = metrics.model_dump(mode="json")

    if is_demo:
        payload["recommendations"] = _recommendations(rng, category)
        payload["recent_activity"] = _activity(rng, category)
        if "charts" not in payload:
            payload["charts"] = _charts(rng, category)
    else:
        payload["recommendations"] = _live_recommendations(live_data, category)
        payload["recent_activity"] = _live_activity(live_data, category)
        if "charts" not in payload:
            payload["charts"] = _charts(rng, category)

    if slug == "industrial-refrigeration":
        refrig = await live_data_service.get_refrigeration_snapshot(building_id)
        if refrig:
            payload["refrigeration"] = refrig

    return payload


def _live_metric_cards(live, category: str) -> List[Dict[str, Any]]:
    cards = [
        {"label": "Peak kW", "unit": "kW", "value": round(live.energy.total_kw, 1), "trend_pct": 0},
        {"label": "HVAC COP", "unit": "", "value": live.hvac.cop, "trend_pct": 0},
        {"label": "CO₂", "unit": "ppm", "value": live.environment.co2_ppm, "trend_pct": 0},
        {"label": "Alerts", "unit": "", "value": live.active_alerts, "trend_pct": 0},
    ]
    if category == "energy":
        cards[0] = {"label": "Cost/hr", "unit": "AED", "value": live.energy.cost_per_hour, "trend_pct": 0}
    return cards


def _live_charts(live, building_id: str) -> Dict[str, Any]:
    metrics = live_data_service.get_building_metrics(building_id, "24h")
    energy_kwh = []
    if metrics and metrics.metrics:
        for point in metrics.metrics[:24]:
            energy_kwh.append(
                {
                    "hour": point.timestamp.hour if hasattr(point.timestamp, "hour") else 0,
                    "actual": round(point.value, 1),
                    "predicted": round(point.value * 1.02, 1),
                }
            )
    if not energy_kwh:
        hour = datetime.now(timezone.utc).hour
        energy_kwh = [
            {"hour": h, "actual": round(live.energy.total_kw * 0.9, 0), "predicted": round(live.energy.total_kw, 0)}
            for h in range(max(0, hour - 12), hour + 1)
        ]
    return {
        "energy_kwh": energy_kwh,
        "optimization_score": [{"hour": i, "score": 85} for i in range(0, 24, 2)],
    }


def _live_recommendations(live, category: str) -> List[Dict[str, Any]]:
    recs = []
    if live.hvac.cop < 3.5:
        recs.append({"priority": "HIGH", "title": "Chiller COP below target", "savings_aed_per_month": 240, "category": category})
    if live.environment.co2_ppm > 800:
        recs.append({"priority": "MED", "title": "Increase ventilation — CO₂ elevated", "savings_aed_per_month": 45, "category": category})
    if not recs:
        recs.append({"priority": "LOW", "title": "System operating within normal range", "savings_aed_per_month": 0, "category": category})
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
        {"priority": p, "title": t, "savings_aed_per_month": s, "category": category}
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
    }
