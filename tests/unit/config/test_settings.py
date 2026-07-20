"""Tests for settings model."""

from __future__ import annotations

import pytest

from gaming_hub.config.models import Settings


@pytest.mark.unit
def test_settings_defaults() -> None:
    """Default settings should be valid and development-oriented."""
    settings = Settings(_env_file=None, environment="development")
    assert settings.app_name == "GamingHub"
    assert settings.environment == "development"
    assert not settings.is_production


@pytest.mark.unit
def test_environment_normalization() -> None:
    """Environment values should be normalized to lowercase."""
    settings = Settings(environment="PRODUCTION", _env_file=None)
    assert settings.environment == "production"
    assert settings.is_production


@pytest.mark.unit
def test_comma_separated_fields_parsed() -> None:
    """Comma-separated strings should become lists."""
    settings = Settings(favorite_genres="RPG, Strategy, Indie", _env_file=None)
    assert settings.favorite_genres == ["RPG", "Strategy", "Indie"]
