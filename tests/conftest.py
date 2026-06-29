"""Pytest fixtures for demo vs production paths."""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def demo_settings(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("APP_ENV", "development")
    from app.config import get_settings

    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def prod_settings(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("INGEST_API_KEY", "test-ingest-key")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-not-default")
    from app.config import get_settings

    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()
