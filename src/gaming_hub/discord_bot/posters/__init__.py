"""Poster registry for automatic Discord channel posts.

Each poster knows which service to call and which channel to post to.
Publication timing is managed by the ``ChannelScheduler`` (startup-based)
rather than external cron triggers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gaming_hub.discord_bot.posters.base import BasePoster


class PosterRegistry:
    """Registry of automatic channel posters keyed by action name."""

    def __init__(self) -> None:
        self._posters: dict[str, BasePoster] = {}

    def register(self, action: str, poster: BasePoster) -> None:
        self._posters[action] = poster

    def get(self, action: str) -> BasePoster | None:
        return self._posters.get(action)

    def all(self) -> dict[str, BasePoster]:
        return dict(self._posters)
