"""Base application service.

Services are use-case objects invoked by Discord commands, n8n webhooks,
or the web API. They are stateless and receive dependencies through their
constructor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings


class BaseService:
    """Minimal base for application services."""

    def __init__(self, settings: Settings) -> None:
        """Initialize service with settings.

        Args:
            settings: Application settings.
        """
        self.settings = settings

    @property
    def name(self) -> str:
        """Return service name for logging and metrics."""
        return self.__class__.__name__
