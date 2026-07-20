"""Integration tests for HTTP client with real network calls."""

from __future__ import annotations

from typing import TYPE_CHECKING

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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_request_succeeds(settings: Settings) -> None:
    """Verify a real HTTP request succeeds with the configured client."""
    client = create_http_client(settings)
    try:
        response = await client.get("https://api.github.com/zen")
        assert response.status_code == 200  # noqa: PLR2004
        assert isinstance(response.text, str)
        assert len(response.text) > 0
    finally:
        await close_http_client(client)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_agent_sent(settings: Settings) -> None:
    """Verify the User-Agent header is sent in real requests."""
    client = create_http_client(settings)
    try:
        response = await client.get("https://api.github.com/zen")
        request_headers = response.request.headers
        assert "User-Agent" in request_headers
        assert USER_AGENT in request_headers["User-Agent"]
    finally:
        await close_http_client(client)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_timeout_raises(settings: Settings) -> None:
    """Verify a timeout exception is raised for slow endpoints."""
    client = create_http_client(settings)
    try:
        with pytest.raises(httpx.TimeoutException):
            await client.get("https://api.github.com/zen", timeout=0.001)
    finally:
        await close_http_client(client)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_check_available(settings: Settings) -> None:
    """Verify check_provider_health returns available=True for a live endpoint."""
    client = create_http_client(settings)
    try:
        result = await check_provider_health(client, "https://api.github.com/zen")
        assert result["available"] is True
        assert result["status_code"] == 200  # noqa: PLR2004
        assert result["response_time_ms"] >= 0
    finally:
        await close_http_client(client)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_check_unavailable(settings: Settings) -> None:
    """Verify check_provider_health returns available=False for unreachable."""
    client = create_http_client(settings)
    try:
        result = await check_provider_health(
            client, "https://nonexistent.example.com/api",
        )
        assert result["available"] is False
        assert "error" in result
        assert result["response_time_ms"] >= 0
    finally:
        await close_http_client(client)
