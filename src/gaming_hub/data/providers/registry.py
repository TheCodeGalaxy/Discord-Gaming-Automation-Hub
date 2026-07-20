"""Provider registry.

Provides name-to-class mapping and factory lookup without hard-coding
provider imports throughout the codebase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gaming_hub.core.enums import ProviderName
from gaming_hub.data.providers.cheapshark import CheapSharkProvider
from gaming_hub.data.providers.epic import EpicProvider
from gaming_hub.data.providers.isthereanydeal import IsThereAnyDealProvider
from gaming_hub.data.providers.rawg import RawgProvider
from gaming_hub.data.providers.steam import SteamCommunityProvider

if TYPE_CHECKING:
    import httpx

    from gaming_hub.config.models import Settings
    from gaming_hub.core.interfaces import DataProvider


class ProviderRegistry:
    """Registry mapping provider names to adapter classes."""

    def __init__(self) -> None:
        """Initialize built-in provider mappings."""
        self._providers: dict[str, type[DataProvider]] = {
            ProviderName.CheapShark: CheapSharkProvider,
            ProviderName.Epic: EpicProvider,
            ProviderName.SteamCommunity: SteamCommunityProvider,
            ProviderName.IsThereAnyDeal: IsThereAnyDealProvider,
            ProviderName.Rawg: RawgProvider,
        }

    def register(self, name: str, provider_cls: type[DataProvider]) -> None:
        """Register a provider adapter under a unique name."""
        self._providers[name] = provider_cls

    def get(self, name: str) -> type[DataProvider]:
        """Return the provider class registered under ``name``."""
        if name not in self._providers:
            raise KeyError(f"Unknown provider: {name}")
        return self._providers[name]

    def list_names(self) -> list[str]:
        """Return all registered provider names."""
        return list(self._providers.keys())

    def create_all(
        self,
        http_client: httpx.AsyncClient,
        settings: Settings,
    ) -> dict[str, DataProvider]:
        """Instantiate all registered providers with shared dependencies.

        Args:
            http_client: Shared HTTP client.
            settings: Application settings.

        Returns:
            Dict mapping provider name to configured instance.
        """
        return {
            name: cls(http_client=http_client, settings=settings)  # type: ignore[call-arg]
            for name, cls in self._providers.items()
        }

    def create(
        self,
        name: str,
        http_client: httpx.AsyncClient,
        settings: Settings,
    ) -> DataProvider:
        """Instantiate a single named provider.

        Args:
            name: Provider name string.
            http_client: Shared HTTP client.
            settings: Application settings.

        Returns:
            Configured provider instance.

        Raises:
            KeyError: If the name is not registered.
        """
        cls = self.get(name)
        return cls(http_client=http_client, settings=settings)  # type: ignore[call-arg]
