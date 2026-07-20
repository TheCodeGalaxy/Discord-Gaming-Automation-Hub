"""CLI entry point for the Discord bot.

Run with ``python -m gaming_hub.discord_bot``.
"""

from __future__ import annotations

from gaming_hub.config.loader import load_settings
from gaming_hub.discord_bot.bot import GamingHubBot


def main() -> None:
    """Construct and start the Discord bot."""
    settings = load_settings()
    bot = GamingHubBot(settings)
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
