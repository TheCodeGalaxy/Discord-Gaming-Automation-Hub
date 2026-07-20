"""Unit tests for the /help command cog."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gaming_hub.discord_bot.cogs.commands.help_cog import HelpCog

from .conftest import resolved


@pytest.mark.unit
class TestHelpCog:
    """Help command behavior."""

    @pytest.mark.asyncio
    async def test_help_responds_with_embed(
        self, bot: MagicMock, interaction: MagicMock,
    ) -> None:
        """/help responds with an embed (no service needed)."""
        resolved(bot, MagicMock())
        cog = HelpCog(bot)
        await cog.help.callback(cog, interaction)
        interaction.response.defer.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert kwargs["embed"] is not None
        assert kwargs["embed"].title == "Gaming Hub Commands"
