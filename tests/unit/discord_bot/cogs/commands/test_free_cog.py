"""Unit tests for the /free command cog."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from gaming_hub.discord_bot.cogs.commands.free_cog import FreeCog
from gaming_hub.services.free_games_service import FreeGamesResult

from .conftest import resolved


@pytest.mark.unit
class TestFreeCog:
    """Free command behavior."""

    @pytest.mark.asyncio
    async def test_free_responds_with_embed(
        self, bot: MagicMock, interaction: MagicMock,
    ) -> None:
        """/free responds with an embed when games are present."""
        game = MagicMock()
        game.title = "Free Game"
        game.store = MagicMock()
        game.store.value = "epic"
        game.free_until = None
        result = FreeGamesResult(current=[game], total=1)
        service = MagicMock()
        service.get_current = AsyncMock(return_value=result)
        resolved(bot, service)
        cog = FreeCog(bot)

        await cog.free.callback(cog, interaction)

        service.get_current.assert_awaited_once()
        interaction.response.defer.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert kwargs["embed"] is not None
        assert kwargs["embed"].title == "Free Game"

    @pytest.mark.asyncio
    async def test_free_empty_responds_ephemeral(
        self, bot: MagicMock, interaction: MagicMock,
    ) -> None:
        """Empty free list produces an ephemeral message."""
        service = MagicMock()
        service.get_current = AsyncMock(return_value=FreeGamesResult())
        resolved(bot, service)
        cog = FreeCog(bot)

        await cog.free.callback(cog, interaction)

        _, kwargs = interaction.followup.send.call_args
        assert kwargs["ephemeral"] is True
