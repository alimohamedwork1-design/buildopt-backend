import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alerts, buildings, energy, equipment, gcc, health, ingest, jci, ml, modules, protocols, refrigeration, sessions, site
from app.config import get_settings
from app.services.bms_auto_connect import run_bms_auto_connect
from app.services.connection_store import connection_store
from app.services.log_handler import install_log_handler, log_event
from app.services.pipeline import run_fdd_cycle, run_metasys_keepalive, run_ml_cycle, run_poll_cycle, run_prayer_sync, run_tariff_update
from app.services.pipeline_tracker import seed_demo_jobs


scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    install_log_handler()
    await connection_store.load_metasys_from_supabase()
    if connection_store.has_saved_metasys() and not settings.demo_mode:
        await run_bms_auto_connect(merge=True)

    if settings.app_env.lower() in ("production", "prod") and not settings.ingest_api_key:
        log_event(
            "warning",
            "INGEST_API_KEY unset in production — ingest endpoint will reject requests",
            "مفتاح INGEST_API_KEY غير مُعد في الإنتاج",
        )

    if settings.demo_mode:
        seed_demo_jobs()

    scheduler.add_job(
        run_poll_cycle,
        "interval",
        seconds=settings.poll_interval_seconds,
        id="poll_building_data",
    )
    scheduler.add_job(run_fdd_cycle, "interval", seconds=60, id="fdd_engine")
    scheduler.add_job(run_ml_cycle, "interval", minutes=5, id="ml_anomaly")
    scheduler.add_job(run_tariff_update, "interval", hours=1, id="dewa_tariff")
    scheduler.add_job(run_prayer_sync, "interval", hours=24, id="prayer_sync")
    scheduler.add_job(run_metasys_keepalive, "interval", minutes=10, id="metasys_keepalive")
    scheduler.start()

    log_event("info", "BuildOpt pipeline started", "تم تشغيل خط أنابيب BuildOpt")
    await run_poll_cycle()
    await run_fdd_cycle()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="BuildOpt AI Backend",
    description="Smart building optimization API for GCC markets",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.(lovable\.app|lovableproject\.com)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api/v1"
app.include_router(health.router, prefix=api_prefix)
app.include_router(buildings.router, prefix=api_prefix)
app.include_router(energy.router, prefix=api_prefix)
app.include_router(equipment.router, prefix=api_prefix)
app.include_router(alerts.router, prefix=api_prefix)
app.include_router(ml.router, prefix=api_prefix)
app.include_router(jci.router, prefix=api_prefix)
app.include_router(refrigeration.router, prefix=api_prefix)
app.include_router(gcc.router, prefix=api_prefix)
app.include_router(protocols.router, prefix=api_prefix)
app.include_router(ingest.router, prefix=api_prefix)
app.include_router(modules.router, prefix=api_prefix)
app.include_router(sessions.router, prefix=api_prefix)
app.include_router(site.router, prefix=api_prefix)


@app.get("/")
async def root() -> dict:
    return {
        "service": "BuildOpt AI Backend",
        "docs": "/docs",
        "health": f"{api_prefix}/health",
        "demo_mode": settings.demo_mode,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=settings.app_env == "development")
