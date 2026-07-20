"""Unit tests for the /surprise command cog."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from gaming_hub.discord_bot.cogs.commands.surprise_cog import SurpriseCog
from gaming_hub.models.domain.game import Game

from .conftest import resolved


@pytest.mark.unit
class TestSurpriseCog:
    """Surprise command behavior."""

    @pytest.mark.asyncio
    async def test_surprise_responds_with_embed(
        self, bot: MagicMock, interaction: MagicMock,
    ) -> None:
        """/surprise responds with an embed when a game is returned."""
        game = Game(id="1", title="Hades", provider_name="steam")
        service = MagicMock()
        service.get_random = AsyncMock(return_value=game)
        resolved(bot, service)
        cog = SurpriseCog(bot)

        await cog.surprise.callback(cog, interaction)

        service.get_random.assert_awaited_once()
        interaction.response.defer.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert kwargs["embed"] is not None
        assert "Hades" in kwargs["embed"].title

    @pytest.mark.asyncio
    async def test_surprise_none_responds_ephemeral(
        self, bot: MagicMock, interaction: MagicMock,
    ) -> None:
        """No game available produces an ephemeral message."""
        service = MagicMock()
        service.get_random = AsyncMock(return_value=None)
        resolved(bot, service)
        cog = SurpriseCog(bot)

        await cog.surprise.callback(cog, interaction)

        _, kwargs = interaction.followup.send.call_args
        assert kwargs["ephemeral"] is True
