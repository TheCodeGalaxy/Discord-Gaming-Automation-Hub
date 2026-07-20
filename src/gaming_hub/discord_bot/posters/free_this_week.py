"""#free-this-week poster."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import discord

from gaming_hub.discord_bot.posters.base import BasePoster
from gaming_hub.services.free_games_service import FreeGamesService

if TYPE_CHECKING:
    from gaming_hub.discord_bot.bot import GamingHubBot

logger = logging.getLogger(__name__)


class FreeThisWeekPoster(BasePoster):
    """Post currently-free games to #free-this-week."""

    CHANNEL = "#free-this-week"

    def __init__(self, bot: GamingHubBot, channel_id: int) -> None:
        super().__init__(bot, channel_id)
        self._service = bot._container.resolve(FreeGamesService)

    async def _build_content(self, job_data: dict[str, Any]) -> list[discord.Embed]:
        result = await self._service.get_current()
        if not result.current:
            return []
        embeds = []
        for game in result.current:
            embed = discord.Embed(
                title=game.title,
                color=discord.Color.green(),
                timestamp=datetime.now(UTC),
            )
            free_until = getattr(game, "free_until", None)
            if free_until:
                embed.add_field(name="Free Until", value=free_until.strftime("%b %d, %Y"), inline=True)
            cover = getattr(game, "cover_url", None)
            if cover:
                embed.set_thumbnail(url=str(cover))
            embed.set_footer(text="Free Games")
            embeds.append(embed)
        return embeds[:10]
