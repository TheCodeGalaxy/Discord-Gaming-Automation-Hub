"""Application bootstrap and composition root.

This module is responsible for:

- Loading configuration.
- Initializing logging.
- Building the dependency graph (inversion-of-control container).
- Starting the Discord client, internal API, or CLI tooling.

It is intentionally thin: concrete implementations live in their respective
layers. The bootstrap layer wires implementations to domain interfaces.
"""

from __future__ import annotations

import logging
from typing import Any

from gaming_hub.config.loader import load_settings
from gaming_hub.data.database import Database
from gaming_hub.discord_bot.bot import GamingHubBot
from gaming_hub.utils.logging import configure_logging


class Application:
    """Application lifecycle manager and composition root."""

    def __init__(self) -> None:
        """Initialize settings, logging, and placeholder state."""
        self.settings = load_settings()
        configure_logging(self.settings)
        self.logger = logging.getLogger(__name__)
        self.database = Database()

    def run(self, args: list[str]) -> int:
        """Start the runtime based on configuration and CLI arguments.

        Args:
            args: Command-line arguments passed from ``sys.argv``.

        Returns:
            Process exit code.
        """
        self.logger.info("application_start", extra={"run_args": args})
        # TODO: Implement full startup orchestration in roadmap phase 18+.
        self.bot = GamingHubBot(self.settings)
        self.bot.run(self.settings.discord_token)

    def build_container(self) -> dict[str, Any]:
        """Build the dependency injection container.

        Returns:
            A mapping of interface names to concrete implementation instances.
        """
        # TODO: Wire providers, cache, database, services, and Discord adapter.
        container = {}
        return container
