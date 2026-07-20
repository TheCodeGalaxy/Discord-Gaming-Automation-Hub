"""Base classes for slash commands.

Concrete commands inherit from a shared ``BaseCommand`` so registration,
permission checks, and error handling are consistent across the bot.
"""

# TODO: Cross-reference roadmap phase 19 (Discord Slash Commands)

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from discord import Interaction

    from gaming_hub.config.models import Settings


class BaseCommand(ABC):
    """Abstract Discord slash command."""

    name: str
    description: str

    def __init__(self, settings: Settings) -> None:
        """Initialize command with settings."""
        self.settings = settings

    async def callback(self, interaction: Interaction) -> None:
        """TODO: Implement command logic."""
        raise NotImplementedError("Command callback is defined in the implementation roadmap.")
