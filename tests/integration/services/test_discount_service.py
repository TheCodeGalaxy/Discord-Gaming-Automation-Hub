"""Integration tests for DiscountService with mocked HTTP providers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
import respx

from gaming_hub.data.cache.in_memory import InMemoryCache
from gaming_hub.data.providers.cheapshark import CheapSharkProvider
from gaming_hub.data.providers.isthereanydeal import IsThereAnyDealProvider
from gaming_hub.services.discount_service import DiscountService
from gaming_hub.utils.http import close_http_client, create_http_client

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings

FIXTURES = Path(__file__).parents[2] / "fixtures"
CHEAPSHARK_FIXTURES = FIXTURES / "cheapshark"
ITAD_FIXTURES = FIXTURES / "isthereanydeal"


def _load_cheapshark(name: str) -> list[dict]:
    with (CHEAPSHARK_FIXTURES / name).open() as f:
        return json.load(f)


def _load_itad(name: str) -> dict:
    with (ITAD_FIXTURES / name).open() as f:
        return json.load(f)


@pytest.mark.integration
class TestDiscountServiceIntegration:
    """Integration tests with real provider adapters and mocked HTTP."""

    @pytest.mark.asyncio
    async def test_get_crazy_discounts_with_cheapshark_and_itad(
        self,
        settings: Settings,
    ) -> None:
        """Verify get_crazy_discounts aggregates deals from CheapShark and ITAD."""
        deals_data = _load_cheapshark("deals.json")
        itad_deals = _load_itad("deal_list.json")

        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(
                    "https://www.cheapshark.com/api/1.0/deals",
                    params={"pageSize": 10, "sortBy": "Savings"},
                ).mock(return_value=httpx.Response(200, json=deals_data))

                respx.get(
                    "https://api.isthereanydeal.com/v01/deal/list",
                ).mock(return_value=httpx.Response(200, json={"data": itad_deals}))

                cache = InMemoryCache(default_ttl=60)
                providers = [
                    CheapSharkProvider(http_client=client, settings=settings),
                    IsThereAnyDealProvider(http_client=client, settings=settings),
                ]
                service = DiscountService(providers, cache, discount_threshold=50.0)
                result = await service.get_crazy_discounts(limit=10)

                assert result.total >= 1
                assert result.fetched_at is not None
                assert len(result.errors) == 0
        finally:
            await cache.stop()
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_provider_error_isolation(
        self,
        settings: Settings,
    ) -> None:
        """Verify one failing provider doesn't block results."""
        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(
                    "https://www.cheapshark.com/api/1.0/deals",
                    params={"pageSize": 60, "sortBy": "Savings"},
                ).mock(return_value=httpx.Response(200, json=[]))

                respx.get(
                    "https://api.isthereanydeal.com/v01/deal/list",
                ).mock(side_effect=httpx.TimeoutException("timed out"))

                cache = InMemoryCache(default_ttl=60)
                providers = [
                    CheapSharkProvider(http_client=client, settings=settings),
                    IsThereAnyDealProvider(http_client=client, settings=settings),
                ]
                service = DiscountService(providers, cache, discount_threshold=0.0)
                result = await service.get_crazy_discounts(limit=10)

                assert len(result.errors) >= 1
        finally:
            await cache.stop()
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_all_providers_fail_returns_empty(
        self,
        settings: Settings,
    ) -> None:
        """Verify when all providers fail, results are empty."""
        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(
                    "https://www.cheapshark.com/api/1.0/deals",
                    params={"pageSize": 60, "sortBy": "Savings"},
                ).mock(side_effect=httpx.TimeoutException("timed out"))

                respx.get(
                    "https://api.isthereanydeal.com/v01/deal/list",
                ).mock(side_effect=httpx.TimeoutException("timed out"))

                cache = InMemoryCache(default_ttl=60)
                providers = [
                    CheapSharkProvider(http_client=client, settings=settings),
                    IsThereAnyDealProvider(http_client=client, settings=settings),
                ]
                service = DiscountService(providers, cache, discount_threshold=0.0)
                result = await service.get_crazy_discounts(limit=10)

                assert result.total == 0
                assert len(result.errors) >= 1
        finally:
            await cache.stop()
            await close_http_client(client)
