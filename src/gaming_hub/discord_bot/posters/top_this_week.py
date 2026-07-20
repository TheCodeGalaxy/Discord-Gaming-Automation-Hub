"""#top-this-week poster."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import discord

from gaming_hub.discord_bot.posters.base import BasePoster
from gaming_hub.services.top_games_service import TopGamesService

if TYPE_CHECKING:
    from gaming_hub.discord_bot.bot import GamingHubBot

logger = logging.getLogger(__name__)


class TopThisWeekPoster(BasePoster):
    """Post weekly top-ranked games to #top-this-week."""

    CHANNEL = "#top-this-week"

    def __init__(self, bot: GamingHubBot, channel_id: int) -> None:
        super().__init__(bot, channel_id)
        self._service = bot._container.resolve(TopGamesService)

    async def _build_content(self, job_data: dict[str, Any]) -> list[discord.Embed]:
        limit = job_data.get("limit", 10)
        result = await self._service.get_weekly_top(limit=limit)
        if not result.games:
            return []
        embeds = []
        for rank, game in enumerate(result.games, 1):
            embed = discord.Embed(
                title=game.title,
                description=f"Score: {game.score:.2f}",
                color=discord.Color.gold(),
                timestamp=datetime.now(UTC),
            )
            embed.add_field(name="Rank", value=f"#{rank}", inline=True)
            if game.signals.review_score:
                embed.add_field(name="Review Score", value=f"{game.signals.review_score:.0f}/100", inline=True)
            if game.signals.discount_percent:
                embed.add_field(name="Discount", value=f"{game.signals.discount_percent:.0f}%", inline=True)
            embed.set_footer(text="Top This Week")
            embeds.append(embed)
        return embeds[:10]
