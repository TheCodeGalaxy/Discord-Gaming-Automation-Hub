"""Unit tests for the /new command cog."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from gaming_hub.discord_bot.cogs.commands.new_cog import NewCog
from gaming_hub.models.domain.game import Game
from gaming_hub.services.new_releases_service import NewReleasesResult

from .conftest import resolved


@pytest.mark.unit
class TestNewCog:
    """New command behavior."""

    @pytest.mark.asyncio
    async def test_new_responds_with_pagination(
        self, bot: MagicMock, interaction: MagicMock,
    ) -> None:
        """/new responds with embeds and a paginator when releases exist."""
        game = Game(id="1", title="GTA VI", provider_name="steam")
        service = MagicMock()
        service.get_upcoming = AsyncMock(
            return_value=NewReleasesResult(games=[game], total=1),
        )
        resolved(bot, service)
        cog = NewCog(bot)

        await cog.new.callback(cog, interaction)

        service.get_upcoming.assert_awaited_once()
        interaction.response.defer.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert kwargs["embed"] is not None
        assert kwargs["view"] is not None

    @pytest.mark.asyncio
    async def test_new_empty_responds_ephemeral(
        self, bot: MagicMock, interaction: MagicMock,
    ) -> None:
        """No releases produce an ephemeral message."""
        service = MagicMock()
        service.get_upcoming = AsyncMock(return_value=NewReleasesResult())
        resolved(bot, service)
        cog = NewCog(bot)

        await cog.new.callback(cog, interaction)

        _, kwargs = interaction.followup.send.call_args
        assert kwargs["ephemeral"] is True
