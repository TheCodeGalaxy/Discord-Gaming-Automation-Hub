"""/new command cog.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from gaming_hub.discord_bot.bot import GamingHubBot
from gaming_hub.discord_bot.utils.embed_builder import build_new_releases_embeds
from gaming_hub.discord_bot.utils.pagination import PaginatorView
from gaming_hub.services.new_releases_service import NewReleasesService


class NewCog(commands.Cog):
    def __init__(self, bot: GamingHubBot):
        self.bot = bot
        self._new_releases_service = bot._container.resolve(NewReleasesService)

    @app_commands.command(
        name="new",
        description="List recent game releases",
    )
    async def new(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        result = await self._new_releases_service.get_upcoming()
        if not result.games:
            await interaction.followup.send("No recent releases available right now.", ephemeral=True)
            return

        embeds = build_new_releases_embeds(result.games)
        paginator = PaginatorView(embeds, interaction.user.id)
        await interaction.followup.send(embed=embeds[0], view=paginator)


async def setup(bot: GamingHubBot) -> None:
    await bot.add_cog(NewCog(bot))
