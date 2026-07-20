"""#major-updates poster.

Posts significant game updates (major patches, DLC, season launches,
expansions) discovered from the Steam Community RSS feeds of popular
games.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import discord

from gaming_hub.discord_bot.posters.base import BasePoster
from gaming_hub.services.major_updates_service import MajorUpdatesService

if TYPE_CHECKING:
    from gaming_hub.discord_bot.bot import GamingHubBot

logger = logging.getLogger(__name__)


class MajorUpdatesPoster(BasePoster):
    """Post major game/application updates to #major-updates."""

    CHANNEL = "#major-updates"

    def __init__(self, bot: GamingHubBot, channel_id: int) -> None:
        super().__init__(bot, channel_id)
        self._service = bot._container.resolve(MajorUpdatesService)

    async def _build_content(self, job_data: dict[str, Any]) -> list[discord.Embed]:
        limit = job_data.get("limit", 10)
        result = await self._service.get_major_updates(limit=limit)

        if not result.updates:
            now = datetime.now(UTC)
            month_name = now.strftime("%B %Y")
            embed = discord.Embed(
                title=f"No Major Updates — {month_name}",
                description="No major game updates were detected for this month. "
                "Check back later for patch notes, DLC, and expansion announcements.",
                color=discord.Color.dark_gray(),
            )
            return [embed]

        embeds = []
        for update in result.updates:
            embed = discord.Embed(
                title=update.game_name[:256],
                description=update.snippet[:1024] if update.snippet else None,
                color=discord.Color.blue(),
                timestamp=update.date,
            )
            embed.add_field(name="Update", value=update.update_title[:256], inline=True)
            if update.url:
                embed.add_field(name="Link", value=update.url[:1024], inline=False)
            embed.set_footer(text="Major Updates")
            embeds.append(embed)
        return embeds[:limit]
