"""Integration tests for EpicProvider with mocked HTTP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
import respx

from gaming_hub.core.exceptions import ProviderRateLimitError
from gaming_hub.data.providers.epic import PROMOTIONS_URL, EpicProvider
from gaming_hub.models.dto.request import SearchRequest
from gaming_hub.utils.http import close_http_client, create_http_client

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings

FIXTURES = Path(__file__).parents[3] / "fixtures" / "epic"


def _load_fixture(name: str) -> dict:
    with (FIXTURES / name).open() as f:
        return json.load(f)


@pytest.mark.integration
class TestEpicIntegration:
    """Integration tests using respx for HTTP mocking."""

    @pytest.mark.asyncio
    async def test_get_free_games_correct_url(
        self, settings: Settings,
    ) -> None:
        """Verify get_free_games calls the correct promotions URL."""
        data = _load_fixture("free_games_current.json")
        client = create_http_client(settings)
        try:
            with respx.mock:
                route = respx.get(PROMOTIONS_URL).mock(
                    return_value=httpx.Response(200, json=data),
                )

                provider = EpicProvider(http_client=client, settings=settings)
                result = await provider.get_free_games()

                assert route.called
                assert len(result.games) == 2  # noqa: PLR2004
        finally:
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_search_uses_catalog_endpoint(
        self, settings: Settings,
    ) -> None:
        """Verify search filters the catalog feed by keyword title."""
        data = _load_fixture("catalog_search.json")
        client = create_http_client(settings)
        try:
            with respx.mock:
                route = respx.get(PROMOTIONS_URL).mock(
                    return_value=httpx.Response(200, json=data),
                )

                provider = EpicProvider(http_client=client, settings=settings)
                request = SearchRequest(query="cyberpunk", limit=5)
                result = await provider.search(request)

                assert route.called
                assert result.metadata.query == "cyberpunk"
                assert len(result.games) == 1
                assert result.games[0].title == "Cyberpunk 2077"
        finally:
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_rate_limit_429(
        self, settings: Settings,
    ) -> None:
        """Verify a 429 response raises ProviderRateLimitError at _get level."""
        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(PROMOTIONS_URL).mock(
                    return_value=httpx.Response(429, text="Rate Limited"),
                )

                provider = EpicProvider(http_client=client, settings=settings)
                with pytest.raises(ProviderRateLimitError):
                    await provider._get(PROMOTIONS_URL)
        finally:
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_retry_on_timeout(
        self, settings: Settings,
    ) -> None:
        """Verify retry behavior on timeout followed by success."""
        data = _load_fixture("free_games_current.json")
        client = create_http_client(settings)
        try:
            with respx.mock:
                route = respx.get(PROMOTIONS_URL).mock(
                    side_effect=[
                        httpx.TimeoutException("timed out"),
                        httpx.TimeoutException("timed out"),
                        httpx.Response(200, json=data),
                    ],
                )

                provider = EpicProvider(http_client=client, settings=settings)
                result = await provider.get_free_games()

                assert route.call_count == 3  # noqa: PLR2004
                assert len(result.games) > 0
        finally:
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_healthcheck_returns_status(
        self, settings: Settings,
    ) -> None:
        """Verify healthcheck returns available status."""
        data = _load_fixture("free_games_current.json")
        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(PROMOTIONS_URL, params__contains={"locale": "en-US"}).mock(
                    return_value=httpx.Response(200, json=data),
                )

                provider = EpicProvider(http_client=client, settings=settings)
                result = await provider.healthcheck()

                assert result["available"] is True
                assert result["status_code"] == 200  # noqa: PLR2004
                assert result["response_time_ms"] >= 0
        finally:
            await close_http_client(client)
