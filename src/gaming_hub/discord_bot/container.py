"""Lightweight service container for the Discord bot.

Resolves application services (Search, Free, Discount, Surprise, New, Top)
from ``Settings``. Providers and cache are constructed once and shared.

The roadmap's cogs call ``bot._container.resolve(Service)``; this module
provides that ``resolve`` capability. Bootstrap (future phases) may replace or
extend this container with a full DI graph.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, TypeVar, cast

from gaming_hub.calendar.adapter import GoogleCalendarAdapter
from gaming_hub.data.cache.in_memory import InMemoryCache
from gaming_hub.data.providers.registry import ProviderRegistry
from gaming_hub.services.calendar_service import CalendarService
from gaming_hub.services.discount_service import DiscountService
from gaming_hub.services.free_games_service import FreeGamesService
from gaming_hub.services.major_updates_service import MajorUpdatesService
from gaming_hub.services.new_releases_service import NewReleasesService
from gaming_hub.services.search_service import SearchService
from gaming_hub.services.surprise_service import SurpriseService
from gaming_hub.services.top_games_service import TopGamesService
from gaming_hub.utils.http import create_http_client

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import httpx

    from gaming_hub.config.models import Settings

T = TypeVar("T")

_SERVICE_FACTORIES: dict[type, str] = {
    SearchService: "_build_search",
    FreeGamesService: "_build_free",
    DiscountService: "_build_discount",
    SurpriseService: "_build_surprise",
    NewReleasesService: "_build_new",
    TopGamesService: "_build_top",
    MajorUpdatesService: "_build_major_updates",
    CalendarService: "_build_calendar",
}


class ServiceContainer:
    """Resolve and cache application services from settings."""

    def __init__(self, settings: Settings) -> None:
        """Store settings and prepare lazy dependencies."""
        self._settings = settings
        self._cache: InMemoryCache | None = None
        self._providers: list[Any] | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._instances: dict[type, Any] = {}

    def _ensure_deps(self) -> None:
        """Create the shared cache, HTTP client, and provider list once."""
        if self._cache is None:
            self._cache = InMemoryCache(default_ttl=self._settings.cache_ttl_seconds)
        if self._http_client is None:
            self._http_client = create_http_client(self._settings)
        if self._providers is None:
            registry = ProviderRegistry()
            created = registry.create_all(self._http_client, self._settings)
            self._providers = list(created.values())

    def _build_search(self) -> SearchService:
        assert self._cache is not None and self._providers is not None
        return SearchService(self._providers, self._cache)

    def _build_free(self) -> FreeGamesService:
        assert self._cache is not None and self._providers is not None
        return FreeGamesService(
            self._providers,
            self._cache,
            expiry_hours=self._settings.free_games_expiry_hours,
        )

    def _build_discount(self) -> DiscountService:
        assert self._cache is not None and self._providers is not None
        return DiscountService(
            self._providers,
            self._cache,
            favorite_genres=self._settings.favorite_genres,
            discount_threshold=80.0,
        )

    def _build_surprise(self) -> SurpriseService:
        assert self._cache is not None and self._providers is not None
        return SurpriseService(
            self._providers,
            self._cache,
            favorite_genres=self._settings.favorite_genres,
        )

    def _build_new(self) -> NewReleasesService:
        assert self._cache is not None and self._providers is not None
        return NewReleasesService(self._providers, self._cache)

    def _build_top(self) -> TopGamesService:
        assert self._cache is not None and self._providers is not None
        return TopGamesService(self._providers, self._cache)

    def _build_major_updates(self) -> MajorUpdatesService:
        assert self._providers is not None and self._http_client is not None
        return MajorUpdatesService(self._providers, self._http_client)

    def _build_calendar(self) -> CalendarService:

        settings: Settings = self._settings
        if not settings.enable_google_calendar:
            logger.info("Google Calendar disabled — returning no-op CalendarService")
            return CalendarService(settings)

        try:
            adapter = GoogleCalendarAdapter(
                calendar_id=settings.google_calendar_id,
                credentials_path=settings.google_calendar_credentials_path,
                service_account_json=settings.google_service_account_json,
            )
        except (ImportError, ValueError, OSError) as exc:
            logger.warning(
                "Google Calendar adapter failed to build — "
                "calendar features will be unavailable: %s",
                exc,
            )
            return CalendarService(settings)

        new_releases: NewReleasesService = self.resolve(NewReleasesService)
        major_updates: MajorUpdatesService = self.resolve(MajorUpdatesService)

        return CalendarService(
            settings,
            new_releases_service=new_releases,
            major_updates_service=major_updates,
            adapter=adapter,
        )

    def resolve(self, service_cls: type[T]) -> T:
        """Resolve a cached service instance by its class.

        Args:
            service_cls: The service type to resolve (e.g. ``SearchService``).

        Returns:
            A singleton instance of ``service_cls``.

        Raises:
            KeyError: If the service type is not registered.
        """
        if service_cls not in _SERVICE_FACTORIES:
            raise KeyError(f"No service registered for {service_cls.__name__}")
        if service_cls not in self._instances:
            self._ensure_deps()
            builder = getattr(self, _SERVICE_FACTORIES[service_cls])
            instance: T = builder()
            self._instances[service_cls] = instance
        return cast("T", self._instances[service_cls])
