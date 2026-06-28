import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alerts, buildings, energy, equipment, gcc, health, ingest, jci, ml, modules, protocols, sessions, site
from app.config import get_settings
from app.services.pipeline import run_poll_cycle


scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    scheduler.add_job(
        run_poll_cycle,
        "interval",
        seconds=settings.poll_interval_seconds,
        id="poll_building_data",
    )
    scheduler.start()
    await run_poll_cycle()
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
