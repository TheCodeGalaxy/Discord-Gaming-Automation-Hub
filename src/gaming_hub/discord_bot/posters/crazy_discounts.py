"""#crazy-discounts poster."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import discord

from gaming_hub.discord_bot.posters.base import BasePoster
from gaming_hub.services.discount_service import DiscountService

if TYPE_CHECKING:
    from gaming_hub.discord_bot.bot import GamingHubBot

logger = logging.getLogger(__name__)


class CrazyDiscountsPoster(BasePoster):
    """Post top discounts to #crazy-discounts."""

    CHANNEL = "#crazy-discounts"

    def __init__(self, bot: GamingHubBot, channel_id: int) -> None:
        super().__init__(bot, channel_id)
        self._service = bot._container.resolve(DiscountService)

    async def _build_content(self, job_data: dict[str, Any]) -> list[discord.Embed]:
        min_discount = job_data.get("min_discount", 80)
        limit = job_data.get("limit", 10)
        result = await self._service.get_crazy_discounts(limit=limit)
        if not result.deals:
            return []
        embeds = []
        for deal in result.deals:
            original_str = f"${deal.original_price:.2f}" if deal.original_price else "?"
            embed = discord.Embed(
                title=deal.title,
                url=str(deal.store_url) if deal.store_url else None,
                description=f"~~{original_str}~~ **${deal.current_price:.2f}** ({deal.discount_percent:.0f}% OFF)",
                color=discord.Color.green() if deal.discount_percent >= 90 else discord.Color.blue(),
                timestamp=datetime.now(UTC),
            )
            embed.add_field(name="Store", value=str(deal.store), inline=True)
            if deal.deal_ends_at:
                embed.set_footer(text=f"Ends {deal.deal_ends_at.strftime('%b %d')}")
            else:
                embed.set_footer(text="Crazy Discounts")
            embeds.append(embed)
        return embeds[:10]
