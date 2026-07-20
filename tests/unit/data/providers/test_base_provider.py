"""Unit tests for BaseHTTPProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from gaming_hub.core.exceptions import ProviderError, ProviderRateLimitError
from gaming_hub.data.providers.base import BaseHTTPProvider


class _TestProvider(BaseHTTPProvider):
    """Minimal concrete subclass for testing."""
    name = "test_provider"


@pytest.fixture()
def mock_client() -> AsyncMock:
    """Return a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture()
def provider(settings, mock_client) -> BaseHTTPProvider:
    """Return a configured test provider instance."""
    return _TestProvider(http_client=mock_client, settings=settings)


@pytest.mark.unit
@pytest.mark.asyncio
class TestBaseHTTPProviderGet:
    """Tests for BaseHTTPProvider._get()."""

    async def test_get_returns_response_on_success(
        self, provider: BaseHTTPProvider, mock_client: AsyncMock,
    ) -> None:
        """Verify _get returns a response on success."""
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)

        response = await provider._get("https://example.com/api")
        assert response.status_code == 200  # noqa: PLR2004

    async def test_get_raises_rate_limit_on_429(
        self, provider: BaseHTTPProvider, mock_client: AsyncMock,
    ) -> None:
        """Verify _get raises ProviderRateLimitError on HTTP 429."""
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.text = '{"error": "rate limited"}'
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=MagicMock(),
                response=mock_response,
            ),
        )
        mock_client.request = AsyncMock(return_value=mock_response)

        with pytest.raises(ProviderRateLimitError) as exc_info:
            await provider._get("https://example.com/api")

        assert exc_info.value.status_code == 429  # noqa: PLR2004

    async def test_get_raises_provider_error_on_500(
        self, provider: BaseHTTPProvider, mock_client: AsyncMock,
    ) -> None:
        """Verify _get raises ProviderError on HTTP 500."""
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "500 Internal Server Error",
                request=MagicMock(),
                response=mock_response,
            ),
        )
        mock_client.request = AsyncMock(return_value=mock_response)

        with pytest.raises(ProviderError) as exc_info:
            await provider._get("https://example.com/api")

        assert exc_info.value.status_code == 500  # noqa: PLR2004

    async def test_get_raises_provider_error_on_400(
        self, provider: BaseHTTPProvider, mock_client: AsyncMock,
    ) -> None:
        """Verify _get raises ProviderError on HTTP 400 (non-5xx)."""
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.text = '{"error": "bad request"}'
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "400 Bad Request",
                request=MagicMock(),
                response=mock_response,
            ),
        )
        mock_client.request = AsyncMock(return_value=mock_response)

        with pytest.raises(ProviderError) as exc_info:
            await provider._get("https://example.com/api")

        assert exc_info.value.status_code == 400  # noqa: PLR2004

    async def test_retries_on_timeout(
        self, provider: BaseHTTPProvider, mock_client: AsyncMock,
    ) -> None:
        """Verify _get retries on httpx.TimeoutException up to max_retries."""
        mock_client.request = AsyncMock(
            side_effect=httpx.TimeoutException("timed out"),
        )

        with pytest.raises(httpx.TimeoutException):
            await provider._get("https://example.com/api")

        assert mock_client.request.call_count == provider.max_retries

    async def test_retries_on_connect_error(
        self, provider: BaseHTTPProvider, mock_client: AsyncMock,
    ) -> None:
        """Verify _get retries on httpx.ConnectError."""
        mock_client.request = AsyncMock(
            side_effect=httpx.ConnectError("connection refused"),
        )

        with pytest.raises(httpx.ConnectError):
            await provider._get("https://example.com/api")

        assert mock_client.request.call_count == provider.max_retries

    async def test_post_method(
        self, provider: BaseHTTPProvider, mock_client: AsyncMock,
    ) -> None:
        """Verify _post sends a POST request."""
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)

        await provider._post("https://example.com/api", json={"key": "value"})

        mock_client.request.assert_called_with(
            "POST", "https://example.com/api", json={"key": "value"},
        )


@pytest.mark.unit
class TestProviderName:
    """Tests for provider name attribute."""

    def test_test_provider_name(self) -> None:
        """Verify the test provider has the correct name."""
        assert _TestProvider.name == "test_provider"
