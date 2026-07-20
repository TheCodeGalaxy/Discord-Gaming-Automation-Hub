"""/help command cog.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from gaming_hub.discord_bot.bot import GamingHubBot
from gaming_hub.discord_bot.utils.embed_builder import build_help_embed


class HelpCog(commands.Cog):
    def __init__(self, bot: GamingHubBot):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="List all available commands",
    )
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        embed = build_help_embed()
        await interaction.followup.send(embed=embed)


async def setup(bot: GamingHubBot) -> None:
    await bot.add_cog(HelpCog(bot))
