"""Integration tests for BaseHTTPProvider with real HTTP calls."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from gaming_hub.data.providers.base import BaseHTTPProvider
from gaming_hub.utils.http import close_http_client, create_http_client

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings


class _IntegrationTestProvider(BaseHTTPProvider):
    """Minimal subclass for end-to-end HTTP testing."""
    name = "integration_test"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_against_real_api(settings: Settings) -> None:
    """Verify _get works end-to-end against a real HTTPS endpoint."""
    client = create_http_client(settings)
    try:
        provider = _IntegrationTestProvider(http_client=client, settings=settings)
        response = await provider._get("https://api.github.com/zen")
        assert response.status_code == 200  # noqa: PLR2004
        assert isinstance(response.text, str)
    finally:
        await close_http_client(client)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_against_real_api(settings: Settings) -> None:
    """Verify _post works end-to-end against a real HTTPS endpoint."""
    client = create_http_client(settings)
    try:
        provider = _IntegrationTestProvider(http_client=client, settings=settings)
        response = await provider._post(
            "https://api.github.com/markdown",
            json={"text": "Hello **world**", "mode": "markdown"},
        )
        assert response.status_code == 200  # noqa: PLR2004
        assert b"<strong>world</strong>" in response.content
    finally:
        await close_http_client(client)
