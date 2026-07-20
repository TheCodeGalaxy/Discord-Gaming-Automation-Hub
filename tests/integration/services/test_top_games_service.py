"""Integration tests for TopGamesService with mocked HTTP providers."""

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
from gaming_hub.services.top_games_service import TopGamesService
from gaming_hub.utils.http import close_http_client, create_http_client

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings

FIXTURES = Path(__file__).parents[2] / "fixtures"
CHEAPSHARK_FIXTURES = FIXTURES / "cheapshark"
STEAM_FIXTURES = FIXTURES / "steam"


def _load_cheapshark(name: str) -> list[dict[str, object]]:
    with (CHEAPSHARK_FIXTURES / name).open() as f:
        return json.load(f)


def _load_steam_fixture(name: str) -> str:
    with (STEAM_FIXTURES / name).open() as f:
        return f.read()


def _load_steam_json(name: str) -> dict[str, object]:
    with (STEAM_FIXTURES / name).open() as f:
        return json.load(f)


@pytest.mark.integration
class TestTopGamesServiceIntegration:
    """Integration tests with real provider adapters and mocked HTTP."""

    @pytest.mark.asyncio
    async def test_signal_collection_from_cheapshark_and_steam(
        self,
        settings: Settings,
    ) -> None:
        """Verify signal collection gathers deal + trending data from providers."""
        deals_data = _load_cheapshark("deals.json")
        trending_html = _load_steam_fixture("trending_page.html")
        appdetails_730 = _load_steam_json("appdetails_730.json")

        client = create_http_client(settings)
        try:
            with respx.mock:
                # CheapShark deals endpoint
                respx.get(
                    "https://www.cheapshark.com/api/1.0/deals",
                    params={"pageSize": 100, "sortBy": "Savings"},
                ).mock(return_value=httpx.Response(200, json=deals_data))

                # Steam trending page (HTML)
                respx.get(
                    "https://steamcommunity.com/trending",
                    params={"l": "english"},
                ).mock(return_value=httpx.Response(200, text=trending_html))

                # Steam appdetails lookup for CS2 (appid 730)
                respx.get(
                    "https://store.steampowered.com/api/appdetails",
                    params={"appids": 730},
                ).mock(return_value=httpx.Response(200, json=appdetails_730))

                cache = InMemoryCache(default_ttl=600)
                providers: list = [
                    CheapSharkProvider(http_client=client, settings=settings),
                    SteamCommunityProvider(http_client=client, settings=settings),
                ]
                service = TopGamesService(providers, cache)

                signals = await service._collect_signals()

            assert len(signals) > 0
            # At least one signal should have discount data from CheapShark
            # or trending data from Steam
            has_discount = any(s.discount_percent > 0 for s in signals)
            has_trending = any(s.is_trending for s in signals)
            assert has_discount or has_trending
        finally:
            await cache.stop()
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_get_weekly_top_with_mocked_providers(
        self,
        settings: Settings,
    ) -> None:
        """Verify get_weekly_top produces ranked results from real providers."""
        deals_data = _load_cheapshark("deals.json")

        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(
                    "https://www.cheapshark.com/api/1.0/deals",
                    params={"pageSize": 100, "sortBy": "Savings"},
                ).mock(return_value=httpx.Response(200, json=deals_data))

                cache = InMemoryCache(default_ttl=600)
                providers = [
                    CheapSharkProvider(http_client=client, settings=settings),
                ]
                service = TopGamesService(providers, cache)

                result = await service.get_weekly_top(limit=10)

            assert result.total >= 0
            assert result.week_ending is not None
            assert result.computed_at is not None
            # Games should be sorted by score descending
            for i in range(len(result.games) - 1):
                assert result.games[i].score >= result.games[i + 1].score
        finally:
            await cache.stop()
            await close_http_client(client)
