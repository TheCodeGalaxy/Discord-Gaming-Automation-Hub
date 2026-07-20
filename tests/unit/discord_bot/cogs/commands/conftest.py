"""Shared fixtures for cog command tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from gaming_hub.config.models import Settings


class FakeInteraction:
    """Minimal stand-in for discord.Interaction used by command tests."""

    def __init__(self, user_id: int = 42) -> None:
        """Create a fake interaction owned by ``user_id``."""
        self.user = MagicMock()
        self.user.id = user_id
        self.response = MagicMock()
        self.response.defer = AsyncMock()
        self.response.send_message = AsyncMock()
        self.response.edit_message = AsyncMock()
        self.followup = MagicMock()
        self.followup.send = AsyncMock()


@pytest.fixture()
def settings() -> Settings:
    """Return a settings object with a dummy Discord token."""
    settings = Settings(_env_file=None)
    settings.discord_token = "TEST_TOKEN"
    settings.discord_guild_ids = [111222333444]
    return settings


@pytest.fixture()
def interaction() -> FakeInteraction:
    """Return a fake discord.Interaction with defer/respond/followup."""
    return FakeInteraction()


@pytest.fixture()
def bot() -> MagicMock:
    """Return a MagicMock bot whose _container.resolve returns service mocks."""
    instance = MagicMock()
    instance._container = MagicMock()
    instance._guild_ids = [111222333444]
    return instance


def resolved(bot: MagicMock, service_mock: MagicMock) -> MagicMock:
    """Wire ``bot._container.resolve`` to return ``service_mock``."""
    bot._container.resolve.return_value = service_mock
    return bot
