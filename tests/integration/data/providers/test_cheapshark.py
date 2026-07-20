"""Integration tests for CheapSharkProvider with mocked HTTP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
import respx

from gaming_hub.core.exceptions import ProviderRateLimitError
from gaming_hub.data.providers.cheapshark import DEALS_URL, LOOKUP_URL, CheapSharkProvider
from gaming_hub.models.dto.request import SearchRequest
from gaming_hub.utils.http import close_http_client, create_http_client

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings

FIXTURES = Path(__file__).parents[3] / "fixtures" / "cheapshark"


def _load_fixture(name: str) -> list[dict]:
    with (FIXTURES / name).open() as f:
        return json.load(f)


@pytest.mark.integration
class TestCheapSharkIntegration:
    """Integration tests using respx for HTTP mocking."""

    @pytest.mark.asyncio
    async def test_search_correct_url_and_params(
        self, settings: Settings,
    ) -> None:
        """Verify search calls the correct URL with title and limit params."""
        data = _load_fixture("games_search.json")
        client = create_http_client(settings)
        try:
            with respx.mock:
                route = respx.get(
                    LOOKUP_URL,
                    params={"title": "cyberpunk", "limit": 5},
                ).mock(
                    return_value=httpx.Response(200, json=data),
                )

                provider = CheapSharkProvider(http_client=client, settings=settings)
                request = SearchRequest(query="cyberpunk", limit=5)
                result = await provider.search(request)

                assert route.called
                assert len(result.games) == 2  # noqa: PLR2004
        finally:
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_retry_on_timeout(
        self, settings: Settings,
    ) -> None:
        """Verify retry on timeout: timeout twice then 200."""
        data = _load_fixture("games_search.json")
        client = create_http_client(settings)
        try:
            with respx.mock:
                route = respx.get(LOOKUP_URL, params__contains={"title": "retry"}).mock(
                    side_effect=[
                        httpx.TimeoutException("timed out"),
                        httpx.TimeoutException("timed out"),
                        httpx.Response(200, json=data),
                    ],
                )

                provider = CheapSharkProvider(http_client=client, settings=settings)
                request = SearchRequest(query="retry", limit=1)
                result = await provider.search(request)

                assert route.call_count == 3  # noqa: PLR2004
                assert len(result.games) > 0
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
                respx.get(DEALS_URL, params__contains={"pageSize": 1}).mock(
                    return_value=httpx.Response(429, text="Rate Limited"),
                )

                provider = CheapSharkProvider(http_client=client, settings=settings)
                with pytest.raises(ProviderRateLimitError):
                    await provider._get(
                        DEALS_URL,
                        params={"pageSize": 1},
                    )
        finally:
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_healthcheck_returns_status(
        self, settings: Settings,
    ) -> None:
        """Verify healthcheck returns available status."""
        data = _load_fixture("deals.json")
        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(DEALS_URL, params={"limit": 1}).mock(
                    return_value=httpx.Response(200, json=data[:1]),
                )

                provider = CheapSharkProvider(http_client=client, settings=settings)
                result = await provider.healthcheck()

                assert result["available"] is True
                assert result["status_code"] == 200  # noqa: PLR2004
                assert result["response_time_ms"] >= 0
        finally:
            await close_http_client(client)
