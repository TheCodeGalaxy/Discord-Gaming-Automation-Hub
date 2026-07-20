"""Integration tests for SearchService with mocked HTTP providers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
import respx

from gaming_hub.data.cache.in_memory import InMemoryCache
from gaming_hub.data.providers.cheapshark import CheapSharkProvider
from gaming_hub.data.providers.steam import SteamCommunityProvider
from gaming_hub.models.dto.request import SearchRequest
from gaming_hub.services.search_service import SearchService
from gaming_hub.utils.http import close_http_client, create_http_client

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings

FIXTURES = Path(__file__).parents[2] / "fixtures"
CHEAPSHARK_FIXTURES = FIXTURES / "cheapshark"
STEAM_FIXTURES = FIXTURES / "steam"


def _load_cheapshark(name: str) -> list[dict]:
    with (CHEAPSHARK_FIXTURES / name).open() as f:
        return json.load(f)


def _load_steam_json(name: str) -> dict:
    with (STEAM_FIXTURES / name).open() as f:
        return json.load(f)


@pytest.mark.integration
class TestSearchServiceIntegration:
    """Integration tests with real provider adapters and mocked HTTP."""

    @pytest.mark.asyncio
    async def test_search_with_two_real_providers(
        self, settings: Settings,
    ) -> None:
        """Verify search aggregates results from CheapShark and Steam."""
        games_data = _load_cheapshark("games_search.json")
        appdetails_data = _load_steam_json("appdetails_730.json")

        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(
                    "https://www.cheapshark.com/api/1.0/games",
                    params={"title": "", "limit": 10},
                ).mock(return_value=httpx.Response(200, json=games_data))

                respx.get(
                    "https://store.steampowered.com/api/appdetails",
                    params={"appids": 730},
                ).mock(return_value=httpx.Response(200, json=appdetails_data))

                cache = InMemoryCache(default_ttl=60)
                providers = [
                    CheapSharkProvider(http_client=client, settings=settings),
                    SteamCommunityProvider(http_client=client, settings=settings),
                ]
                service = SearchService(providers, cache)
                request = SearchRequest(steam_app_id=730, limit=10)
                result = await service.search(request)

                assert result.total_games > 0
                assert result.took_ms >= 0
                assert len(result.errors) == 0
        finally:
            await cache.stop()
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_slow_provider_does_not_block(
        self, settings: Settings,
    ) -> None:
        """Verify a slow provider does not prevent results from returning."""
        games_data = _load_cheapshark("games_search.json")

        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(
                    "https://www.cheapshark.com/api/1.0/games",
                    params={"title": "", "limit": 10},
                ).mock(return_value=httpx.Response(200, json=games_data))

                respx.get(
                    "https://store.steampowered.com/api/appdetails",
                    params={"appids": 730},
                ).mock(
                    side_effect=httpx.TimeoutException("timed out"),
                )

                cache = InMemoryCache(default_ttl=60)
                providers = [
                    CheapSharkProvider(http_client=client, settings=settings),
                    SteamCommunityProvider(http_client=client, settings=settings),
                ]
                service = SearchService(providers, cache)
                request = SearchRequest(steam_app_id=730, limit=10)
                result = await service.search(request)

                assert result.total_games > 0
                assert len(result.errors) >= 1
        finally:
            await cache.stop()
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_all_providers_fail_returns_empty_with_errors(
        self, settings: Settings,
    ) -> None:
        """Verify when all providers fail, results are empty with errors."""
        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(
                    "https://www.cheapshark.com/api/1.0/games",
                    params={"title": "", "limit": 10},
                ).mock(
                    side_effect=httpx.TimeoutException("timed out"),
                )

                respx.get(
                    "https://store.steampowered.com/api/appdetails",
                    params={"appids": 730},
                ).mock(
                    side_effect=httpx.TimeoutException("timed out"),
                )

                cache = InMemoryCache(default_ttl=60)
                providers = [
                    CheapSharkProvider(http_client=client, settings=settings),
                    SteamCommunityProvider(http_client=client, settings=settings),
                ]
                service = SearchService(providers, cache)
                request = SearchRequest(steam_app_id=730, limit=10)
                result = await service.search(request)

                assert result.total_games == 0
                assert result.took_ms >= 0
                assert len(result.errors) >= 1
        finally:
            await cache.stop()
            await close_http_client(client)
