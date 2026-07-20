"""Unit tests for ProviderRegistry."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from gaming_hub.core.enums import ProviderName
from gaming_hub.data.providers.cheapshark import CheapSharkProvider
from gaming_hub.data.providers.epic import EpicProvider
from gaming_hub.data.providers.isthereanydeal import IsThereAnyDealProvider
from gaming_hub.data.providers.registry import ProviderRegistry
from gaming_hub.data.providers.steam import SteamCommunityProvider


@pytest.fixture()
def registry() -> ProviderRegistry:
    """Return a fresh ProviderRegistry."""
    return ProviderRegistry()


@pytest.fixture()
def mock_client() -> AsyncMock:
    """Return a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.mark.unit
class TestProviderRegistryList:
    """Tests for listing provider names."""

    def test_list_names_returns_all(self, registry: ProviderRegistry) -> None:
        """Verify list_names returns all registered names."""
        names = registry.list_names()
        assert ProviderName.CheapShark in names
        assert ProviderName.Epic in names
        assert ProviderName.SteamCommunity in names
        assert ProviderName.IsThereAnyDeal in names
        assert ProviderName.Rawg in names

    def test_list_names_length(self, registry: ProviderRegistry) -> None:
        """Verify list_names returns exactly 5 providers."""
        assert len(registry.list_names()) == 5  # noqa: PLR2004


@pytest.mark.unit
class TestProviderRegistryGet:
    """Tests for ProviderRegistry.get()."""

    def test_get_known_provider(self, registry: ProviderRegistry) -> None:
        """Verify get returns the correct class for a known name."""
        cls = registry.get(ProviderName.CheapShark)
        assert cls is CheapSharkProvider

    def test_get_unknown_provider_raises(self, registry: ProviderRegistry) -> None:
        """Verify get raises KeyError for an unknown name."""
        with pytest.raises(KeyError, match="unknown_provider"):
            registry.get("unknown_provider")

    def test_get_epic_provider(self, registry: ProviderRegistry) -> None:
        """Verify get returns EpicProvider."""
        cls = registry.get(ProviderName.Epic)
        assert cls is EpicProvider

    def test_get_steam_provider(self, registry: ProviderRegistry) -> None:
        """Verify get returns SteamCommunityProvider."""
        cls = registry.get(ProviderName.SteamCommunity)
        assert cls is SteamCommunityProvider

    def test_get_isthereanydeal_provider(self, registry: ProviderRegistry) -> None:
        """Verify get returns IsThereAnyDealProvider."""
        cls = registry.get(ProviderName.IsThereAnyDeal)
        assert cls is IsThereAnyDealProvider


@pytest.mark.unit
class TestProviderRegistryCreate:
    """Tests for ProviderRegistry.create() and create_all()."""

    def test_create_all_returns_all_providers(
        self, registry: ProviderRegistry, mock_client: AsyncMock, settings,
    ) -> None:
        """Verify create_all returns all providers."""
        providers = registry.create_all(mock_client, settings)
        assert len(providers) == 5  # noqa: PLR2004
        assert ProviderName.CheapShark in providers
        assert ProviderName.Epic in providers
        assert ProviderName.SteamCommunity in providers
        assert ProviderName.IsThereAnyDeal in providers
        assert ProviderName.Rawg in providers

    def test_create_all_instances_have_correct_names(
        self, registry: ProviderRegistry, mock_client: AsyncMock, settings,
    ) -> None:
        """Verify each created instance has the correct .name."""
        providers = registry.create_all(mock_client, settings)
        for name, instance in providers.items():
            assert instance.name == name

    def test_create_cheapshark(
        self, registry: ProviderRegistry, mock_client: AsyncMock, settings,
    ) -> None:
        """Verify create('cheapshark') returns a CheapSharkProvider instance."""
        provider = registry.create(ProviderName.CheapShark, mock_client, settings)
        assert isinstance(provider, CheapSharkProvider)
        assert provider.name == ProviderName.CheapShark

    def test_create_unknown_raises(
        self, registry: ProviderRegistry, mock_client: AsyncMock, settings,
    ) -> None:
        """Verify create with unknown name raises KeyError."""
        with pytest.raises(KeyError, match="unknown"):
            registry.create("unknown", mock_client, settings)

    def test_create_all_passes_http_client(
        self, registry: ProviderRegistry, mock_client: AsyncMock, settings,
    ) -> None:
        """Verify create_all passes the http_client to each instance."""
        providers = registry.create_all(mock_client, settings)
        for instance in providers.values():
            assert instance.http_client is mock_client


@pytest.mark.unit
class TestProviderRegistryRegistration:
    """Tests for custom provider registration."""

    def test_register_new_provider(self, registry: ProviderRegistry) -> None:
        """Verify register adds a new provider."""
        mock_cls = type("MockProvider", (object,), {})
        registry.register("custom", mock_cls)
        assert registry.get("custom") is mock_cls

    def test_register_overwrites_existing(self, registry: ProviderRegistry) -> None:
        """Verify register overwrites an existing mapping."""
        old_cls = registry.get(ProviderName.CheapShark)
        new_cls = type("NewCheapShark", (object,), {})
        registry.register(ProviderName.CheapShark, new_cls)
        assert registry.get(ProviderName.CheapShark) is new_cls
        assert registry.get(ProviderName.CheapShark) is not old_cls
