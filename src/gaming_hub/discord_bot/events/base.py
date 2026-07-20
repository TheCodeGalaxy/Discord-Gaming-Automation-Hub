"""Base event handler.

Keeps event subscription organized and testable. Concrete event handlers
receive the bot instance and settings.
"""

# TODO: Cross-reference roadmap phase 19 (Discord Slash Commands)

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from discord.ext.commands import Bot

    from gaming_hub.config.models import Settings


class BaseEventHandler(ABC):
    """Abstract Discord event handler."""

    event_name: str

    def __init__(self, bot: Bot, settings: Settings) -> None:
        """Bind handler to bot and settings."""
        self.bot = bot
        self.settings = settings

    async def handle(self, *args: Any, **kwargs: Any) -> None:
        """TODO: Implement event handling."""
        raise NotImplementedError("Event handler is defined in the implementation roadmap.")
