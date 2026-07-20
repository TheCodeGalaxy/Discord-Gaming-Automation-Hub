"""/discount command cog.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from gaming_hub.discord_bot.bot import GamingHubBot
from gaming_hub.discord_bot.utils.embed_builder import build_discount_embeds
from gaming_hub.discord_bot.utils.pagination import PaginatorView
from gaming_hub.services.discount_service import DiscountService


class DiscountCog(commands.Cog):
    def __init__(self, bot: GamingHubBot):
        self.bot = bot
        self._discount_service = bot._container.resolve(DiscountService)

    @app_commands.command(
        name="discount",
        description="List top game discounts",
    )
    async def discount(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        result = await self._discount_service.get_crazy_discounts()
        if not result.deals:
            await interaction.followup.send("No discounts available right now.", ephemeral=True)
            return

        embeds = build_discount_embeds(result.deals)
        paginator = PaginatorView(embeds, interaction.user.id)
        await interaction.followup.send(embed=embeds[0], view=paginator)


async def setup(bot: GamingHubBot) -> None:
    await bot.add_cog(DiscountCog(bot))
