"""Generates module-specific payloads for all build-opt.site pages."""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.data.modules_registry import get_category
from app.services import demo_mode, live_data_service
from app.utils.dewa_tariff import calculate_dewa_tariff
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

    payload: Dict[str, Any] = {
        "slug": slug or "overview",
        "path": f"/{slug}" if slug else "/",
        "category": category,
        "building_id": building_id,
        "timestamp": now.isoformat(),
        "fetched_at": now.isoformat().replace("+00:00", "Z"),
        "metric_cards": _metric_cards(rng, category),
        "demo_mode": True,
    }

    live_data = await live_data_service.get_live_data(building_id)
    if live_data:
        payload["live"] = live_data.model_dump(mode="json")
        payload["demo_mode"] = live_data.demo_mode

    if category in ("overview", "telemetry", "equipment", "optimization"):
        payload["equipment"] = [e.model_dump(mode="json") for e in live_data_service.list_equipment(building_id)]
        payload["alerts_count"] = len(live_data_service.list_alerts())

    if category in ("overview", "energy", "financial", "telemetry"):
        payload["energy"] = live_data_service.get_energy_consumption().model_dump(mode="json")
        payload["savings"] = live_data_service.get_energy_savings().model_dump(mode="json")
        payload["forecast"] = live_data_service.get_energy_forecast(building_id).model_dump(mode="json")

    if category in ("energy", "gcc", "financial"):
        payload["dewa_tariff"] = calculate_dewa_tariff(52000, 34000, 950).model_dump(mode="json")

    if category in ("alerts", "fault_prediction", "overview"):
        payload["alerts"] = [a.model_dump(mode="json") for a in live_data_service.list_alerts()]
        payload["fdd"] = [f.model_dump(mode="json") for f in live_data_service.list_fdd_results()]

    if category == "gcc":
        payload["ramadan"] = get_ramadan_mode().model_dump(mode="json")

    if category in ("overview", "telemetry", "optimization"):
        metrics = live_data_service.get_building_metrics(building_id, "24h")
        if metrics:
            payload["metrics_24h"] = metrics.model_dump(mode="json")

    payload["recommendations"] = _recommendations(rng, category)
    payload["recent_activity"] = _activity(rng, category)
    payload["charts"] = _charts(rng, category)

    return payload


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
