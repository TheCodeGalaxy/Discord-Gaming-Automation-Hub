"""Base poster abstract class for automatic Discord channel posts."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
    from gaming_hub.discord_bot.bot import GamingHubBot

logger = logging.getLogger(__name__)


@dataclass
class PosterResult:
    """Result of a single poster execution."""

    success: bool = False
    embed_count: int = 0
    message_ids: list[int] = field(default_factory=list)
    dry_run: bool = False
    error: str | None = None


class BasePoster(ABC):
    """Abstract base for all automatic channel posters.

    Each subclass implements ``_build_content`` which calls the relevant
    service and returns a list of Discord embeds. The base class handles
    dry-run mode, channel fetching, sending, and error reporting.
    """

    CHANNEL: str = ""

    def __init__(self, bot: GamingHubBot, channel_id: int) -> None:
        self.bot = bot
        self.channel_id = channel_id
        self.dry_run = False

    async def execute(self, job_data: dict[str, Any] | None = None) -> PosterResult:
        """Build and post embeds to the configured channel.

        Args:
            job_data: Optional parameters passed by n8n (e.g. limit, min_discount).

        Returns:
            A ``PosterResult`` with outcome details.
        """
        try:
            content = await self._build_content(job_data or {})
            if not content:
                logger.info("No content to post for %s", self.CHANNEL)
                return PosterResult(success=True, embed_count=0)
            if self.dry_run:
                logger.info("[DRY RUN] Would post %d embed(s) to channel %s (%d)",
                            len(content), self.CHANNEL, self.channel_id)
                return PosterResult(dry_run=True, success=True, embed_count=len(content))
            channel = self.bot.get_channel(self.channel_id) or await self.bot.fetch_channel(self.channel_id)
            messages = []
            for embed in content:
                msg = await channel.send(embed=embed)
                messages.append(msg)
            logger.info("Posted %d embed(s) to %s", len(messages), self.CHANNEL)
            return PosterResult(
                success=True,
                embed_count=len(messages),
                message_ids=[m.id for m in messages],
            )
        except Exception as e:
            logger.exception("Poster %s failed: %s", self.CHANNEL, e)
            return PosterResult(success=False, error=str(e))

    @abstractmethod
    async def _build_content(self, job_data: dict[str, Any]) -> list[discord.Embed]:
        """Build the list of embeds to post.

        Args:
            job_data: Optional parameters from the n8n payload.

        Returns:
            A list of ``discord.Embed`` instances, or an empty list when
            the service returns no data.
        """
