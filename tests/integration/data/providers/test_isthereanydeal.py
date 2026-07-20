"""Integration tests for IsThereAnyDealProvider with mocked HTTP."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
import respx

from gaming_hub.core.exceptions import ProviderRateLimitError
from gaming_hub.data.providers.isthereanydeal import (
    LOWEST_URL,
    IsThereAnyDealProvider,
)
from gaming_hub.models.dto.request import SearchRequest
from gaming_hub.utils.http import close_http_client, create_http_client

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings

FIXTURES = Path(__file__).parents[3] / "fixtures" / "isthereanydeal"


def _load_fixture(name: str) -> dict:
    with (FIXTURES / name).open() as f:
        return json.load(f)


@pytest.mark.integration
class TestIsThereAnyDealIntegration:
    """Integration tests using respx for HTTP mocking.

    Note: The ITAD v01/v02/v03 APIs have been decommissioned (all return
    404). Search and deals now return empty immediately. Only the
    ``get_lowest_price`` helper (which calls ``/v02/deal/lowest``) and
    the raw ``_get`` are tested for HTTP behaviour.
    """

    @pytest.mark.asyncio
    async def test_search_returns_empty(
        self, settings: Settings,
    ) -> None:
        """Verify search returns empty without making HTTP calls
        (API decommissioned).
        """
        client = create_http_client(settings)
        try:
            provider = IsThereAnyDealProvider(http_client=client, settings=settings)
            request = SearchRequest(query="cyberpunk", limit=5)
            result = await provider.search(request)

            assert len(result.games) == 0
        finally:
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_deals_returns_empty(
        self, settings: Settings,
    ) -> None:
        """Verify get_deals returns empty without HTTP calls
        (API decommissioned).
        """
        client = create_http_client(settings)
        try:
            provider = IsThereAnyDealProvider(http_client=client, settings=settings)
            result = await provider.get_deals(limit=5)
            assert len(result.deals) == 0
        finally:
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_get_free_games_returns_empty(
        self, settings: Settings,
    ) -> None:
        """Verify get_free_games returns empty (API decommissioned)."""
        client = create_http_client(settings)
        try:
            provider = IsThereAnyDealProvider(http_client=client, settings=settings)
            result = await provider.get_free_games()
            assert len(result.deals) == 0
        finally:
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_rate_limit_429(
        self, settings: Settings,
    ) -> None:
        """Verify a 429 response raises ProviderRateLimitError."""
        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(LOWEST_URL, params={"id": "cyberpunk2077"}).mock(
                    return_value=httpx.Response(429, text="Rate Limited"),
                )

                provider = IsThereAnyDealProvider(http_client=client, settings=settings)
                with pytest.raises(ProviderRateLimitError):
                    await provider._get(
                        LOWEST_URL,
                        params={"id": "cyberpunk2077"},
                    )
        finally:
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_healthcheck_reports_unavailable(
        self, settings: Settings,
    ) -> None:
        """Verify healthcheck returns unavailable status (API decommissioned)."""
        client = create_http_client(settings)
        try:
            provider = IsThereAnyDealProvider(http_client=client, settings=settings)
            result = await provider.healthcheck()

            assert result["available"] is False
            assert "decommissioned" in result.get("error", "")
        finally:
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_lowest_price_with_key_param(
        self, settings: Settings,
    ) -> None:
        """Verify _get is called with optional key param when configured."""
        data = _load_fixture("lowest_price.json")
        client = create_http_client(settings)
        try:
            with respx.mock:
                route = respx.get(
                    LOWEST_URL,
                    params={"id": "cyberpunk2077", "key": "test-key-123"},
                ).mock(
                    return_value=httpx.Response(200, json=data),
                )

                provider = IsThereAnyDealProvider(http_client=client, settings=settings)
                provider.settings.isthereanydeal_api_key = "test-key-123"  # type: ignore[assignment]

                result = await provider.get_lowest_price("cyberpunk2077")

                assert route.called
                assert result is not None
                assert result["lowest_price"] == 4.99  # noqa: PLR2004
        finally:
            await close_http_client(client)
