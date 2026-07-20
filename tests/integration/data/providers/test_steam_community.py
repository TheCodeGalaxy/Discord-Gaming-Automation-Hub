"""Integration tests for SteamCommunityProvider with mocked HTTP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
import respx

from gaming_hub.core.exceptions import ProviderRateLimitError
from gaming_hub.data.providers.steam import APPDETAILS_URL, TRENDING_URL, SteamCommunityProvider
from gaming_hub.models.dto.request import SearchRequest
from gaming_hub.utils.http import close_http_client, create_http_client

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings

FIXTURES = Path(__file__).parents[3] / "fixtures" / "steam"


def _load_json(name: str) -> dict:
    with (FIXTURES / name).open() as f:
        return json.load(f)


def _load_html(name: str) -> str:
    return (FIXTURES / name).read_text()


@pytest.mark.integration
class TestSteamIntegration:
    """Integration tests using respx for HTTP mocking."""

    @pytest.mark.asyncio
    async def test_search_correct_params(
        self, settings: Settings,
    ) -> None:
        """Verify search sends appids parameter correctly."""
        data = _load_json("appdetails_730.json")
        client = create_http_client(settings)
        try:
            with respx.mock:
                route = respx.get(APPDETAILS_URL, params={"appids": 730}).mock(
                    return_value=httpx.Response(200, json=data),
                )

                provider = SteamCommunityProvider(http_client=client, settings=settings)
                request = SearchRequest(steam_app_id=730)
                result = await provider.search(request)

                assert route.called
                assert len(result.games) == 1
        finally:
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_html_error_detected(
        self, settings: Settings,
    ) -> None:
        """Verify HTML response from appdetails raises ProviderError."""
        html = _load_html("appdetails_html_error.html")
        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(APPDETAILS_URL, params={"appids": 730}).mock(
                    return_value=httpx.Response(
                        200, text=html, headers={"content-type": "text/html"},
                    ),
                )

                provider = SteamCommunityProvider(http_client=client, settings=settings)
                request = SearchRequest(steam_app_id=730)
                result = await provider.search(request)

                # ProviderError caught by search() → returned as error metadata
                assert len(result.games) == 0
                assert len(result.metadata.errors) == 1
        finally:
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_trending_correct_url(
        self, settings: Settings,
    ) -> None:
        """Verify get_trending calls the correct URL."""
        html = _load_html("trending_page.html")
        client = create_http_client(settings)
        try:
            with respx.mock:
                route = respx.get(TRENDING_URL, params={"l": "english"}).mock(
                    return_value=httpx.Response(200, text=html),
                )

                provider = SteamCommunityProvider(http_client=client, settings=settings)
                result = await provider.get_trending(limit=5)

                assert route.called
                assert len(result.games) > 0
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
                respx.get(APPDETAILS_URL, params={"appids": 1}).mock(
                    return_value=httpx.Response(429, text="Rate Limited"),
                )

                provider = SteamCommunityProvider(http_client=client, settings=settings)
                with pytest.raises(ProviderRateLimitError):
                    await provider._get(APPDETAILS_URL, params={"appids": 1})
        finally:
            await close_http_client(client)

    @pytest.mark.asyncio
    async def test_healthcheck_returns_status(
        self, settings: Settings,
    ) -> None:
        """Verify healthcheck returns available status."""
        client = create_http_client(settings)
        try:
            with respx.mock:
                respx.get(APPDETAILS_URL, params={"appids": 1}).mock(
                    return_value=httpx.Response(200, json={"1": {"success": True, "data": {}}}),
                )

                provider = SteamCommunityProvider(http_client=client, settings=settings)
                result = await provider.healthcheck()

                assert result["available"] is True
                assert result["status_code"] == 200  # noqa: PLR2004
                assert result["response_time_ms"] >= 0
        finally:
            await close_http_client(client)
