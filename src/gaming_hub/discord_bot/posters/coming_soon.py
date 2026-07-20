"""#coming-soon poster.

Filters game releases to only the current calendar month — no future
or past months. Shows an informative embed when nothing is scheduled.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import discord

from gaming_hub.discord_bot.posters.base import BasePoster
from gaming_hub.services.new_releases_service import NewReleasesService

if TYPE_CHECKING:
    from gaming_hub.discord_bot.bot import GamingHubBot

logger = logging.getLogger(__name__)


class ComingSoonPoster(BasePoster):
    """Post upcoming game releases to #coming-soon."""

    CHANNEL = "#coming-soon"

    def __init__(self, bot: GamingHubBot, channel_id: int) -> None:
        super().__init__(bot, channel_id)
        self._service = bot._container.resolve(NewReleasesService)

    async def _build_content(self, job_data: dict[str, Any]) -> list[discord.Embed]:
        limit = job_data.get("limit", 20)
        result = await self._service.get_current_month(limit=limit)

        if not result.games:
            now = datetime.now(UTC)
            month_name = now.strftime("%B %Y")
            embed = discord.Embed(
                title=f"No Releases Scheduled — {month_name}",
                description="No major releases scheduled for this month.",
                color=discord.Color.purple(),
            )
            return [embed]

        embeds = []
        for game in result.games:
            description = (game.short_description or game.description or "")[:512]
            embed = discord.Embed(
                title=game.title,
                description=description or None,
                color=discord.Color.purple(),
                url=str(game.provider_url) if game.provider_url else None,
            )
            if game.release_date:
                embed.add_field(
                    name="Release Date",
                    value=game.release_date.strftime("%b %d, %Y"),
                    inline=False,
                )
            if game.platforms:
                embed.add_field(
                    name="Platforms",
                    value=", ".join(game.platforms[:5]),
                    inline=False,
                )
            if game.genres:
                embed.add_field(name="Genres", value=", ".join(game.genres[:3]), inline=True)
            if game.cover_url:
                embed.set_thumbnail(url=str(game.cover_url))
            embed.set_footer(text="Coming Soon")
            embeds.append(embed)
        return embeds[:limit]
