"""Discord bot integration layer.

The bot knows how to receive interactions, invoke application services, and
render responses. It does not contain provider or caching logic.
"""

from gaming_hub.discord_bot.bot import GamingHubBot

__all__ = ["GamingHubBot"]
