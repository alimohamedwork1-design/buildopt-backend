"""Database client factories for InfluxDB and Supabase."""

from app.config import get_settings
from app.services.influx_client import InfluxService
from app.services.supabase_client import SupabaseService


def get_influx_service() -> InfluxService:
    settings = get_settings()
    return InfluxService(
        url=settings.influx_url,
        token=settings.influx_token,
        org=settings.influx_org,
        bucket=settings.influx_bucket,
        demo_mode=settings.demo_mode,
    )


def get_supabase_service() -> SupabaseService:
    settings = get_settings()
    return SupabaseService(
        url=settings.supabase_url,
        key=settings.supabase_key,
        service_key=settings.supabase_service_key,
        demo_mode=settings.demo_mode,
    )
