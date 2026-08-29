"""Telemetry store backend selection and production durability rules."""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.services.telemetry_store import (
    TelemetryStore,
    TelemetryStoreUnavailableError,
    get_telemetry_store,
    get_telemetry_store_status,
    reset_telemetry_store,
    resolve_telemetry_backend,
)


@pytest.fixture(autouse=True)
def clean_store():
    reset_telemetry_store(None)
    get_settings.cache_clear()
    yield
    reset_telemetry_store(None)
    get_settings.cache_clear()


def test_auto_selects_supabase_with_service_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("TELEMETRY_STORE_BACKEND", "auto")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "eyJ-test-service-key")
    get_settings.cache_clear()

    backend, error = resolve_telemetry_backend(get_settings())
    assert backend == "supabase"
    assert error is None


def test_auto_selects_sqlite_in_development_without_supabase(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TELEMETRY_STORE_BACKEND", "auto")
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    get_settings.cache_clear()

    backend, error = resolve_telemetry_backend(get_settings())
    assert backend == "sqlite"
    assert error is None

    store = get_telemetry_store()
    assert isinstance(store, TelemetryStore)
    assert store.db_path != "supabase"


def test_production_live_does_not_silently_fallback_to_sqlite(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("TELEMETRY_STORE_BACKEND", "auto")
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    get_settings.cache_clear()

    backend, error = resolve_telemetry_backend(get_settings())
    assert backend == "unavailable"
    assert "SUPABASE_SERVICE_KEY" in (error or "")

    with pytest.raises(TelemetryStoreUnavailableError):
        get_telemetry_store()


def test_anon_key_is_not_used_for_durable_supabase(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("TELEMETRY_STORE_BACKEND", "auto")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "eyJ-anon-key-only")
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    get_settings.cache_clear()

    backend, _ = resolve_telemetry_backend(get_settings())
    assert backend == "unavailable"


def test_explicit_sqlite_allowed_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("TELEMETRY_STORE_BACKEND", "sqlite")
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    get_settings.cache_clear()

    backend, error = resolve_telemetry_backend(get_settings())
    assert backend == "sqlite"
    assert error is None

    store = get_telemetry_store()
    assert isinstance(store, TelemetryStore)


def test_status_never_exposes_service_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "super-secret-service-key-value")
    get_settings.cache_clear()

    status = get_telemetry_store_status()
    serialized = str(status)
    assert "super-secret-service-key-value" not in serialized
    assert "SUPABASE_SERVICE_KEY" not in serialized


def test_production_status_not_configured_when_durable_missing(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("TELEMETRY_STORE_BACKEND", "auto")
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.delenv("TELEMETRY_INGEST_GATED_SUPABASE", raising=False)
    get_settings.cache_clear()

    status = get_telemetry_store_status()
    assert status["required"] is True
    assert status["status"] == "not_configured"
    assert status["durable"] is False


def test_ingest_gated_supabase_when_explicitly_enabled(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("TELEMETRY_INGEST_GATED_SUPABASE", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "eyJ-test-anon-key")
    monkeypatch.setenv("INGEST_API_KEY", "test-ingest-key")
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    get_settings.cache_clear()

    backend, _ = resolve_telemetry_backend(get_settings())
    assert backend == "supabase_ingest_gated"
