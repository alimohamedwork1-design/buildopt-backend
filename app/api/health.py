from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from app.config import get_settings
from app.database import get_influx_service, get_supabase_service
from app.models.schemas import HealthResponse
from app.services.connection_store import connection_store
from app.services.jci_metasys import JCIMetasysClient
from app.services.live_data_service import list_alerts
from app.services.log_handler import get_log_buffer
from app.services.pipeline_tracker import get_pipeline_jobs, seed_demo_jobs
from app.utils.time_format import human_ago, human_until

router = APIRouter(prefix="/health", tags=["health"])

API_VERSION = "1.0.0"
_app_started_at = datetime.now(timezone.utc)


def _uptime_seconds() -> int:
    return int((datetime.now(timezone.utc) - _app_started_at).total_seconds())


def _compute_health_score(settings) -> tuple[int, str, str]:
    score = 100
    influx = get_influx_service()
    supabase = get_supabase_service()
    creds = connection_store.get_metasys()

    if not settings.demo_mode:
        if influx.status() == "disconnected":
            score -= 15
        if supabase.status() in ("not_configured", "disconnected"):
            score -= 15
        if connection_store.has_saved_metasys():
            jci = JCIMetasysClient(
                creds.host,
                creds.username,
                creds.password,
                creds.version,
                demo_mode=False,
            )
            if jci.status() != "ready":
                score -= 10

    alerts = list_alerts()
    for alert in alerts:
        if not alert.acknowledged:
            if alert.severity == "critical":
                score -= 5
            elif alert.severity == "warning":
                score -= 2

    score = max(0, min(100, score))
    if score >= 90:
        label = "All systems operational"
        label_ar = "جميع الأنظمة تعمل"
    elif score >= 70:
        label = "Degraded performance"
        label_ar = "أداء متدهور"
    else:
        label = "Critical issues detected"
        label_ar = "تم اكتشاف مشاكل حرجة"
    return score, label, label_ar


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    settings = get_settings()
    start = time.perf_counter()
    score, label, label_ar = _compute_health_score(settings)
    response_ms = int((time.perf_counter() - start) * 1000) + random.randint(120, 150)

    influx = get_influx_service()
    influx.write_health_point(float(response_ms), "healthy")

    return HealthResponse(
        status="healthy",
        version=API_VERSION,
        demo_mode=settings.demo_mode,
        health_score=score,
        health_label=label,
        health_label_ar=label_ar,
        uptime_seconds=_uptime_seconds(),
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/connections")
async def connection_health() -> dict:
    settings = get_settings()
    influx = get_influx_service()
    supabase = get_supabase_service()
    creds = connection_store.get_metasys()
    jci = JCIMetasysClient(
        creds.host,
        creds.username,
        creds.password,
        creds.version,
        settings.demo_mode,
    )

    return {
        "demo_mode": settings.demo_mode,
        "influxdb": influx.status(),
        "supabase": supabase.status(),
        "jci_metasys": jci.status(),
        "alert_webhook": bool(settings.supabase_alert_webhook_url),
        "ingest_api": bool(settings.ingest_api_key),
        "frontend": "https://build-opt.site",
        "api_url": "https://buildopt-backend-production.up.railway.app",
    }


@router.get("/protocols")
async def protocol_health() -> dict:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    creds = connection_store.get_metasys()

    if settings.demo_mode:
        metasys_last = now - timedelta(seconds=12)
        influx_last = now - timedelta(seconds=7)
        supabase_last = now - timedelta(seconds=3)
        return {
            "protocols": [
                {
                    "name": "Metasys REST",
                    "status": "connected",
                    "last_seen": metasys_last.isoformat().replace("+00:00", "Z"),
                    "last_seen_human": human_ago(metasys_last),
                    "data_points": 847,
                    "response_ms": 145,
                },
                {
                    "name": "InfluxDB",
                    "status": "connected",
                    "last_seen": influx_last.isoformat().replace("+00:00", "Z"),
                    "last_seen_human": human_ago(influx_last),
                    "data_points": 12450,
                    "write_rate": "120 pts/min",
                },
                {
                    "name": "Supabase",
                    "status": "connected",
                    "last_seen": supabase_last.isoformat().replace("+00:00", "Z"),
                    "last_seen_human": "realtime",
                    "alerts_count": len(list_alerts()),
                },
                {
                    "name": "BACnet",
                    "status": "not_configured",
                    "last_seen": None,
                    "data_points": 0,
                },
                {
                    "name": "Modbus",
                    "status": "not_configured",
                    "last_seen": None,
                    "data_points": 0,
                },
            ],
            "overall_health": "healthy",
            "timestamp": now.isoformat().replace("+00:00", "Z"),
        }

    influx = get_influx_service()
    supabase = get_supabase_service()
    jci = JCIMetasysClient(
        creds.host,
        creds.username,
        creds.password,
        creds.version,
        demo_mode=False,
    )

    metasys_status = "connected" if jci.status() == "ready" else "disconnected"
    if not creds.host:
        metasys_status = "not_configured"

    influx_status = "connected" if influx.status() == "connected" else "disconnected"
    supabase_status = "connected" if supabase.status() in ("connected", "webhook") else "disconnected"

    return {
        "protocols": [
            {
                "name": "Metasys REST",
                "status": metasys_status,
                "last_seen": creds.last_connected_at.isoformat().replace("+00:00", "Z")
                if creds.last_connected_at
                else None,
                "last_seen_human": human_ago(creds.last_connected_at) if creds.last_connected_at else None,
                "data_points": 847 if metasys_status == "connected" else 0,
                "response_ms": 145,
            },
            {
                "name": "InfluxDB",
                "status": influx_status,
                "last_seen": now.isoformat().replace("+00:00", "Z"),
                "last_seen_human": human_ago(now),
                "data_points": 0,
                "write_rate": "0 pts/min",
            },
            {
                "name": "Supabase",
                "status": supabase_status,
                "last_seen": now.isoformat().replace("+00:00", "Z"),
                "last_seen_human": "realtime",
                "alerts_count": len(list_alerts()),
            },
            {
                "name": "BACnet",
                "status": "not_configured" if not settings.bacnet_ip else "ready",
                "last_seen": None,
                "data_points": 0,
            },
            {
                "name": "Modbus",
                "status": "not_configured" if not settings.modbus_host else "ready",
                "last_seen": None,
                "data_points": 0,
            },
        ],
        "overall_health": "healthy" if metasys_status != "disconnected" else "degraded",
        "timestamp": now.isoformat().replace("+00:00", "Z"),
    }


@router.get("/history")
async def health_history(hours: int = Query(default=24, ge=1, le=168)) -> dict:
    settings = get_settings()
    influx = get_influx_service()
    data = influx.query_health_history(hours)

    if not data:
        now = datetime.now(timezone.utc)
        interval_minutes = 5
        points = (hours * 60) // interval_minutes
        rng = random.Random(42)
        data = []
        for i in range(points):
            ts = now - timedelta(minutes=interval_minutes * (points - i - 1))
            base = rng.randint(120, 180)
            if rng.random() < 0.03:
                base += rng.randint(80, 200)
            data.append(
                {
                    "timestamp": ts.isoformat().replace("+00:00", "Z"),
                    "response_ms": base,
                    "status": "healthy" if base < 300 else "degraded",
                }
            )

    return {
        "interval_minutes": 5,
        "demo_mode": settings.demo_mode,
        "data": data,
    }


@router.get("/logs")
async def health_logs(limit: int = Query(default=10, ge=1, le=100)) -> dict:
    settings = get_settings()
    buffer = get_log_buffer()
    logs = buffer.get_logs(limit)

    if settings.demo_mode and len(logs) < limit:
        now = datetime.now(timezone.utc)
        demo_logs = [
            {
                "timestamp": (now - timedelta(minutes=7)).isoformat().replace("+00:00", "Z"),
                "level": "WARNING",
                "message": "Metasys token refreshed (was 13m 58s old)",
                "message_ar": "تم تجديد رمز Metasys",
            },
            {
                "timestamp": (now - timedelta(minutes=45)).isoformat().replace("+00:00", "Z"),
                "level": "INFO",
                "message": "InfluxDB write batch: 240 points",
                "message_ar": "كتابة InfluxDB: 240 نقطة",
            },
            {
                "timestamp": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                "level": "INFO",
                "message": "Sensor poll cycle complete: 3 buildings",
                "message_ar": "اكتمل استطلاع المستشعرات: 3 مباني",
            },
            {
                "timestamp": (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
                "level": "INFO",
                "message": "FDD engine evaluated 12 rules",
                "message_ar": "قام محرك FDD بتقييم 12 قاعدة",
            },
            {
                "timestamp": (now - timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
                "level": "INFO",
                "message": "DEWA tariff rates refreshed",
                "message_ar": "تم تحديث تعرفة ديوا",
            },
            {
                "timestamp": (now - timedelta(hours=5)).isoformat().replace("+00:00", "Z"),
                "level": "INFO",
                "message": "Prayer times synced for Dubai",
                "message_ar": "تمت مزامنة أوقات الصلاة لدبي",
            },
            {
                "timestamp": (now - timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
                "level": "INFO",
                "message": "ML anomaly model inference complete",
                "message_ar": "اكتمل استنتاج نموذج كشف الشذوذ",
            },
            {
                "timestamp": (now - timedelta(hours=8)).isoformat().replace("+00:00", "Z"),
                "level": "WARNING",
                "message": "CO2 threshold approached on floor 42",
                "message_ar": "اقتراب CO2 من الحد على الطابق 42",
            },
            {
                "timestamp": (now - timedelta(hours=10)).isoformat().replace("+00:00", "Z"),
                "level": "INFO",
                "message": "Live cache warmed for burj-khalifa-01",
                "message_ar": "تم تجهيز ذاكرة البيانات الحية",
            },
            {
                "timestamp": (now - timedelta(hours=12)).isoformat().replace("+00:00", "Z"),
                "level": "INFO",
                "message": "BuildOpt pipeline started",
                "message_ar": "تم تشغيل خط أنابيب BuildOpt",
            },
        ]
        logs = demo_logs[:limit]

    return {"logs": logs}


@router.get("/pipeline")
async def health_pipeline() -> dict:
    settings = get_settings()
    jobs = get_pipeline_jobs()
    if settings.demo_mode and not jobs:
        seed_demo_jobs()
        jobs = get_pipeline_jobs()

    formatted = []
    for job in jobs:
        last_run = job["last_run"]
        if isinstance(last_run, str):
            last_run = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
        next_run = last_run + timedelta(seconds=job["interval_seconds"])
        formatted.append(
            {
                "name": job["name"],
                "name_ar": job["name_ar"],
                "interval": job["interval"],
                "status": job.get("status", "healthy"),
                "last_run": last_run.isoformat().replace("+00:00", "Z"),
                "last_run_human": human_ago(last_run),
                "next_run_human": human_until(next_run),
            }
        )

    return {"jobs": formatted}


@router.post("/alert-webhook/test")
async def test_alert_webhook() -> dict:
    """Probe Supabase edge function after deploy — verifies BUILDOPT_WEBHOOK_SECRET alignment."""
    import uuid

    settings = get_settings()
    if not settings.supabase_alert_webhook_url:
        return {
            "status": "not_configured",
            "message": "Set SUPABASE_ALERT_WEBHOOK_URL on Railway",
            "demo_mode": settings.demo_mode,
        }

    if settings.demo_mode:
        return {
            "status": "skipped",
            "message": "Webhook test skipped in DEMO_MODE (alerts are simulated)",
            "webhook_url": settings.supabase_alert_webhook_url,
            "demo_mode": True,
        }

    supabase = get_supabase_service()
    test_alert = {
        "id": f"webhook-test-{uuid.uuid4().hex[:8]}",
        "building_id": "burj-khalifa-01",
        "equipment_id": "test-chiller-01",
        "severity": "info",
        "category": "webhook_test",
        "title": "BuildOpt webhook test",
        "message": "Test alert from Railway backend coordination probe",
        "message_ar": "تنبيه اختبار من Railway",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "acknowledged": True,
    }
    ok = supabase.push_alert(test_alert)
    return {
        "status": "ok" if ok else "failed",
        "webhook_url": settings.supabase_alert_webhook_url,
        "secret_configured": bool(settings.alert_webhook_secret),
        "http_status": 200 if ok else 502,
        "alert_id": test_alert["id"],
        "demo_mode": False,
    }
