"""Unit tests for HTTP client utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings

from gaming_hub.utils.http import (
    USER_AGENT,
    check_provider_health,
    close_http_client,
    create_http_client,
)


@pytest.mark.unit
class TestCreateHttpClient:
    """Tests for create_http_client()."""

    def test_returns_async_client(self, settings: Settings) -> None:
        """Verify the factory returns a connected AsyncClient."""
        client = create_http_client(settings)
        assert isinstance(client, httpx.AsyncClient)
        assert not client.is_closed

    def test_sends_user_agent(self, settings: Settings) -> None:
        """Verify the client sends the configured User-Agent."""
        client = create_http_client(settings)
        assert client.headers["User-Agent"] == USER_AGENT

    def test_accepts_json(self, settings: Settings) -> None:
        """Verify the client sends Accept: application/json."""
        client = create_http_client(settings)
        assert client.headers["Accept"] == "application/json"

    def test_supports_gzip(self, settings: Settings) -> None:
        """Verify the client sends Accept-Encoding: gzip, deflate."""
        client = create_http_client(settings)
        assert client.headers["Accept-Encoding"] == "gzip, deflate"

    def test_follows_redirects(self, settings: Settings) -> None:
        """Verify the client follows redirects."""
        client = create_http_client(settings)
        assert client.follow_redirects is True

    def test_timeout_match_settings(self, settings: Settings) -> None:
        """Verify the timeout matches settings.http_timeout."""
        client = create_http_client(settings)
        assert client.timeout.read == settings.http_timeout


@pytest.mark.unit
@pytest.mark.asyncio
class TestCloseHttpClient:
    """Tests for close_http_client()."""

    async def test_close_none_is_noop(self) -> None:
        """Verify close_http_client(None) does not raise."""
        await close_http_client(None)

    async def test_close_client(self, settings: Settings) -> None:
        """Verify close_http_client closes the client."""
        client = create_http_client(settings)
        assert not client.is_closed
        await close_http_client(client)
        assert client.is_closed


@pytest.mark.unit
@pytest.mark.asyncio
class TestCheckProviderHealth:
    """Tests for check_provider_health()."""

    async def test_available(self) -> None:
        """Verify a successful health check returns available=True."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = AsyncMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await check_provider_health(mock_client, "https://example.com/health")
        assert result["available"] is True
        assert result["status_code"] == 200  # noqa: PLR2004
        assert isinstance(result["response_time_ms"], int)

    async def test_unavailable(self) -> None:
        """Verify a failed health check returns available=False."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        result = await check_provider_health(mock_client, "https://example.com/health")
        assert result["available"] is False
        assert "error" in result
        assert isinstance(result["response_time_ms"], int)

    async def test_http_error(self) -> None:
        """Verify an HTTP error response is treated as unavailable."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=MagicMock(),
            response=MagicMock(),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await check_provider_health(mock_client, "https://example.com/health")
        assert result["available"] is False
        assert "error" in result

    async def test_response_time_is_positive(self) -> None:
        """Verify response_time_ms is a positive integer on success."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = AsyncMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await check_provider_health(mock_client, "https://example.com/health")
        assert result["response_time_ms"] >= 0
