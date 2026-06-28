from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

_lock = Lock()
_jobs: Dict[str, Dict[str, Any]] = {}


def record_job_run(
    job_id: str,
    *,
    name: str,
    name_ar: str,
    interval_label: str,
    interval_seconds: int,
    status: str = "healthy",
) -> None:
    now = datetime.now(timezone.utc)
    with _lock:
        _jobs[job_id] = {
            "name": name,
            "name_ar": name_ar,
            "interval": interval_label,
            "interval_seconds": interval_seconds,
            "status": status,
            "last_run": now,
        }


def get_pipeline_jobs() -> List[Dict[str, Any]]:
    with _lock:
        snapshot = dict(_jobs)
    return list(snapshot.values())


def seed_demo_jobs() -> None:
    now = datetime.now(timezone.utc)
    demo = [
        ("sensor_poll", "Sensor Poll", "استطلاع المستشعرات", "Every 30s", 30, now - timedelta(seconds=12)),
        ("fdd_engine", "FDD Engine", "محرك كشف الأعطال", "Every 60s", 60, now - timedelta(seconds=42)),
        ("ml_anomaly", "ML Anomaly Detection", "كشف الشذوذ بالذكاء الاصطناعي", "Every 5min", 300, now - timedelta(minutes=2)),
        ("dewa_tariff", "DEWA Tariff Update", "تحديث تعرفة ديوا", "Every 1h", 3600, now - timedelta(minutes=30)),
        ("prayer_sync", "Prayer Times Sync", "مزامنة أوقات الصلاة", "Every 24h", 86400, now - timedelta(hours=8)),
    ]
    with _lock:
        for job_id, name, name_ar, interval, seconds, last_run in demo:
            _jobs[job_id] = {
                "name": name,
                "name_ar": name_ar,
                "interval": interval,
                "interval_seconds": seconds,
                "status": "healthy",
                "last_run": last_run,
            }
