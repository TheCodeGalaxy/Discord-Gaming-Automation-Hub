"""Domain ports (interfaces) that drive the architecture.

These abstract classes define contracts for infrastructure adapters.
The application layer depends on these ports, never on concrete providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from gaming_hub.models.dto.provider import (
    ProviderResult,  # noqa: TC001 — required at runtime for type annotations used by subclasses
)
from gaming_hub.models.dto.request import (
    SearchRequest,  # noqa: TC001 — required at runtime for type annotations used by subclasses
)


class DataProvider(ABC):
    """Port for all external gaming data providers."""

    name: str

    @abstractmethod
    async def search(self, request: SearchRequest) -> ProviderResult:
        """Search the provider catalog and return normalized results."""
        raise NotImplementedError

    @abstractmethod
    async def get_free_games(self, *, upcoming: bool = False) -> ProviderResult:
        """Return current or upcoming free games."""
        raise NotImplementedError

    @abstractmethod
    async def get_deals(self, *, limit: int = 10) -> ProviderResult:
        """Return current deals from the provider."""
        raise NotImplementedError

    @abstractmethod
    async def healthcheck(self) -> dict[str, Any]:
        """Return a lightweight health/status summary."""
        raise NotImplementedError


class CacheBackend(ABC):
    """Port for caching provider responses and computed aggregates.

    Implementations store Python objects directly (no serialization required)
    and support TTL-based expiration.
    """

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Retrieve a cached value by key."""
        raise NotImplementedError

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store a value by key with optional TTL in seconds."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove a cached value."""
        raise NotImplementedError

    @abstractmethod
    async def clear(self) -> None:
        """Remove all cached values."""
        raise NotImplementedError

    @abstractmethod
    async def stats(self) -> dict[str, Any]:
        """Return cache statistics (hit, miss, hit_ratio, size)."""
        raise NotImplementedError


class UnitOfWork(ABC):
    """Port for transactional persistence.

    Implementations wrap the ORM session and ensure atomic writes.
    """

    @abstractmethod
    async def __aenter__(self) -> UnitOfWork:
        """Enter the async context manager."""
        raise NotImplementedError

    @abstractmethod
    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Exit the async context manager."""
        raise NotImplementedError

    @abstractmethod
    async def commit(self) -> None:
        """Commit the transaction."""
        raise NotImplementedError

    @abstractmethod
    async def rollback(self) -> None:
        """Roll back the transaction."""
        raise NotImplementedError


class DiscordAdapter(ABC):
    """Port for Discord interactions."""

    @abstractmethod
    async def send_message(self, channel_id: int, content: str, **kwargs: Any) -> None:
        """Send a text or embed message to a channel."""
        raise NotImplementedError

    @abstractmethod
    async def register_slash_command(self, command: Any) -> None:
        """Register a slash command with Discord."""
        raise NotImplementedError


class CalendarAdapter(ABC):
    """Port for Google Calendar integration."""

    @abstractmethod
    async def create_event(self, *, title: str, start: str, end: str, reminder_minutes: int) -> str:
        """Create a calendar event and return its ID."""
        raise NotImplementedError

    @abstractmethod
    async def update_event(  # noqa: PLR0913
        self,
        event_id: str,
        *,
        title: str,
        start: str,
        end: str,
        reminder_minutes: int,
        color_id: int | None = None,
    ) -> None:
        """Update an existing calendar event."""
        raise NotImplementedError

    @abstractmethod
    async def delete_event(self, event_id: str) -> None:
        """Delete a calendar event by its Google event ID."""
        raise NotImplementedError

    @abstractmethod
    async def find_events_by_ext_id(self, ext_id: str) -> list[dict[str, Any]]:
        """Search for calendar events whose extendedProperties contains *ext_id*."""
        raise NotImplementedError

    @abstractmethod
    async def list_events_in_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Return all calendar events whose start date falls in the range."""
        raise NotImplementedError


class Scheduler(ABC):
    """Port for automation scheduling (n8n/trigger bridge)."""

    @abstractmethod
    async def trigger(self, job_name: str, payload: dict[str, Any] | None = None) -> None:
        """Trigger an automation job by name."""
        raise NotImplementedError
