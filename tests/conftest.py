"""Shared pytest fixtures and configuration."""

from __future__ import annotations

import os

import pytest

from gaming_hub.config.loader import load_settings
from gaming_hub.config.models import Settings


@pytest.fixture(scope="session", autouse=True)
def _test_environment() -> None:
    """Ensure tests never read a local .env file by accident."""
    os.environ.setdefault("ENVIRONMENT", "test")
    load_settings.cache_clear()


@pytest.fixture()
def settings() -> Settings:
    """Return a fresh default settings object for a test."""
    return Settings(_env_file=None)
