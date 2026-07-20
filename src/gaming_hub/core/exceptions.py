"""Domain exceptions.

All project-specific exceptions inherit from ``GamingHubError`` so callers can
catch failures uniformly while still inspecting specialized error types.
"""

from __future__ import annotations

from typing import Any


class GamingHubError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        """Initialize with a message and optional structured details."""
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(GamingHubError):
    """Raised when settings are invalid or missing."""


class ProviderError(GamingHubError):
    """Raised when a data provider operation fails."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize with provider context."""
        super().__init__(message, details=details)
        self.provider = provider
        self.status_code = status_code


class ProviderTimeoutError(ProviderError):
    """Raised when a provider request exceeds the configured timeout."""


class ProviderRateLimitError(ProviderError):
    """Raised when a provider signals rate-limiting."""


class NotFoundError(GamingHubError):
    """Raised when a requested entity cannot be found."""


class ValidationError(GamingHubError):
    """Raised when domain validation fails."""


class DiscordError(GamingHubError):
    """Raised when Discord interaction or posting fails."""


class CalendarError(GamingHubError):
    """Raised when Google Calendar integration fails."""
