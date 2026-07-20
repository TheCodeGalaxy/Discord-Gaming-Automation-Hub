"""Shared foundation for HTTP-based providers.

Concrete adapters inherit from ``BaseHTTPProvider`` and implement the three
data methods declared in ``gaming_hub.core.interfaces.DataProvider``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from gaming_hub.core.exceptions import ProviderError, ProviderRateLimitError
from gaming_hub.core.interfaces import DataProvider

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings
    from gaming_hub.models.dto.provider import ProviderResult
    from gaming_hub.models.dto.request import SearchRequest

logger = logging.getLogger(__name__)


class BaseHTTPProvider(DataProvider):
    """Base class for providers that communicate over HTTP.

    Holds a configured ``httpx.AsyncClient`` and application settings.
    Subclasses set ``name`` and implement the data-fetching methods.
    """

    name: str = "base"

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        """Initialize provider with shared dependencies."""
        self.http_client = http_client
        self.settings = settings
        self.max_retries = settings.http_max_retries

    async def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Dispatch a GET request with error mapping."""
        return await self._request("GET", url, **kwargs)

    async def _post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Dispatch a POST request with error mapping."""
        return await self._request("POST", url, **kwargs)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Core request dispatch with retry and error mapping."""
        attempt = 0
        async for attempt_data in AsyncRetrying(
            stop=stop_after_attempt(self.max_retries or 1),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=5.0),
            retry=retry_if_exception_type(
                (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError),
            ),
            reraise=True,
        ):
            with attempt_data:
                attempt += 1
                try:
                    response = await self.http_client.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response
                except httpx.HTTPStatusError as exc:
                    self._raise_mapped_error(exc, url)
                except (
                    httpx.TimeoutException,
                    httpx.ConnectError,
                    httpx.RemoteProtocolError,
                ) as exc:
                    logger.warning(
                        "provider_retry: %s attempt=%d error=%s",
                        self.name,
                        attempt,
                        exc,
                    )
                    raise
        raise ProviderError(
            f"Request failed after {attempt} attempts",
            provider=self.name,
        )

    def _raise_mapped_error(self, exc: httpx.HTTPStatusError, url: str) -> None:
        """Map HTTP status codes to domain exceptions."""
        status = exc.response.status_code
        details = {"url": url, "status_code": status, "body": exc.response.text[:500]}
        if status == 429:  # noqa: PLR2004
            raise ProviderRateLimitError(
                f"Rate limited by {self.name}",
                provider=self.name,
                status_code=status,
                details=details,
            )
        if 500 <= status < 600:  # noqa: PLR2004
            raise ProviderError(
                f"{self.name} server error: {status}",
                provider=self.name,
                status_code=status,
                details=details,
            )
        raise ProviderError(
            f"{self.name} HTTP {status}",
            provider=self.name,
            status_code=status,
            details=details,
        )

    async def search(self, request: SearchRequest) -> ProviderResult:
        """TODO: Implement per-provider search."""
        raise NotImplementedError

    async def get_free_games(self, *, upcoming: bool = False) -> ProviderResult:
        """TODO: Implement per-provider free game listing."""
        raise NotImplementedError

    async def get_deals(self, *, limit: int = 10) -> ProviderResult:
        """TODO: Implement per-provider deal listing."""
        raise NotImplementedError

    async def healthcheck(self) -> dict[str, Any]:
        """TODO: Implement lightweight provider healthcheck."""
        raise NotImplementedError
