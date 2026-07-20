"""/surprise command cog.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from gaming_hub.discord_bot.bot import GamingHubBot
from gaming_hub.discord_bot.utils.embed_builder import build_surprise_embed
from gaming_hub.services.surprise_service import SurpriseService


class SurpriseCog(commands.Cog):
    def __init__(self, bot: GamingHubBot):
        self.bot = bot
        self._surprise_service = bot._container.resolve(SurpriseService)

    @app_commands.command(
        name="surprise",
        description="Get a random game",
    )
    async def surprise(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        result = await self._surprise_service.get_random()
        if not result:
            await interaction.followup.send("No games available right now.", ephemeral=True)
            return

        embed = build_surprise_embed(result)
        await interaction.followup.send(embed=embed)


async def setup(bot: GamingHubBot) -> None:
    await bot.add_cog(SurpriseCog(bot))
