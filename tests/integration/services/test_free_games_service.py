"""Integration tests for FreeGamesService with mocked HTTP providers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
import respx

from gaming_hub.data.cache.in_memory import InMemoryCache
from gaming_hub.data.providers.cheapshark import CheapSharkProvider
from gaming_hub.data.providers.epic import EpicProvider
from gaming_hub.services.free_games_service import FreeGamesService
from gaming_hub.utils.http import close_http_client, create_http_client

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings

FIXTURES = Path(__file__).parents[2] / "fixtures"
EPIC_FIXTURES = FIXTURES / "epic"
CHEAPSHARK_FIXTURES = FIXTURES / "cheapshark"


def _load_epic(name: str) -> dict:
    with (EPIC_FIXTURES / name).open() as f:
        return json.load(f)


def _load_cheapshark(name: str) -> list[dict]:
    with (CHEAPSHARK_FIXTURES / name).open() as f:
        return json.load(f)


@pytest.mark.integration
class TestFreeGamesServiceIntegration:
    """Integration tests with real provider adapters and mocked HTTP."""

    @pytest.mark.asyncio
    async def test_get_current_with_epic_and_cheapshark(
        self, settings: Settings,
    ) -> None:
        """Verify get_current aggregates free games from Epic and CheapShark."""
        epic_data = _load_epic("free_games_current.json")
        deals_data = _load_cheapshark("deals.json")

        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(
                    "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions",
                    params={"locale": "en-US", "country": "US", "allowCountries": "US"},
                ).mock(return_value=httpx.Response(200, json=epic_data))

                respx.get(
                    "https://www.cheapshark.com/api/1.0/deals",
                    params={"pageSize": 60, "sortBy": "Savings"},
                ).mock(return_value=httpx.Response(200, json=deals_data))

                cache = InMemoryCache(default_ttl=60)
                providers = [
                    EpicProvider(http_client=client, settings=settings),
                    CheapSharkProvider(http_client=client, settings=settings),
                ]
                service = FreeGamesService(providers, cache)
                result = await service.get_current()

                # Epic fixture has 2 games, CheapShark has 1 free game
                assert result.total >= 1
                assert result.fetched_at is not None
                assert len(result.errors) == 0
        finally:
            await cache.stop()
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_provider_error_isolation(
        self, settings: Settings,
    ) -> None:
        """Verify one failing provider doesn't block results."""
        epic_data = _load_epic("free_games_current.json")

        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(
                    "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions",
                    params={"locale": "en-US", "country": "US", "allowCountries": "US"},
                ).mock(return_value=httpx.Response(200, json=epic_data))

                respx.get(
                    "https://www.cheapshark.com/api/1.0/deals",
                    params={"pageSize": 60, "sortBy": "Savings"},
                ).mock(
                    side_effect=httpx.TimeoutException("timed out"),
                )

                cache = InMemoryCache(default_ttl=60)
                providers = [
                    EpicProvider(http_client=client, settings=settings),
                    CheapSharkProvider(http_client=client, settings=settings),
                ]
                service = FreeGamesService(providers, cache)
                result = await service.get_current()

                # Epic should still return results despite CheapShark failure
                assert result.total >= 1
        finally:
            await cache.stop()
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_all_providers_fail_returns_empty(
        self, settings: Settings,
    ) -> None:
        """Verify when all providers fail, results are empty."""
        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(
                    "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions",
                    params={"locale": "en-US", "country": "US", "allowCountries": "US"},
                ).mock(
                    side_effect=httpx.TimeoutException("timed out"),
                )

                respx.get(
                    "https://www.cheapshark.com/api/1.0/deals",
                    params={"pageSize": 60, "sortBy": "Savings"},
                ).mock(
                    side_effect=httpx.TimeoutException("timed out"),
                )

                cache = InMemoryCache(default_ttl=60)
                providers = [
                    EpicProvider(http_client=client, settings=settings),
                    CheapSharkProvider(http_client=client, settings=settings),
                ]
                service = FreeGamesService(providers, cache)
                result = await service.get_current()

                assert result.total == 0
                assert len(result.errors) >= 1
        finally:
            await cache.stop()
            await close_http_client(client)
