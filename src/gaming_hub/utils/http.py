"""Shared HTTP client factory.

Provides a single ``httpx.AsyncClient`` instance wired with retries, timeouts,
and headers. This avoids scattering HTTP configuration throughout providers.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings

USER_AGENT = "GamingHub/0.1.0 (+https://github.com/abdullah/discord-gaming-automation-hub)"


def create_http_client(settings: Settings) -> httpx.AsyncClient:
    """Create and return a configured async HTTP client.

    Args:
        settings: Application settings.

    Returns:
        Configured ``httpx.AsyncClient`` instance.
    """
    limits = httpx.Limits(
        max_keepalive_connections=10,
        max_connections=50,
        keepalive_expiry=30.0,
    )
    timeout = httpx.Timeout(
        settings.http_timeout,
        connect=10.0,
        read=settings.http_timeout,
        write=10.0,
        pool=10.0,
    )
    client = httpx.AsyncClient(
        limits=limits,
        timeout=timeout,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        },
        follow_redirects=True,
    )
    return client


async def close_http_client(client: httpx.AsyncClient | None) -> None:
    """Gracefully close the HTTP client and its underlying connection pool."""
    if client is not None:
        await client.aclose()


async def check_provider_health(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    """Ping a provider endpoint and return status metadata.

    Args:
        client: The shared HTTP client.
        url: The provider health-check URL.

    Returns:
        A dict with ``available``, ``status_code``, ``response_time_ms``,
        and optionally ``error``.
    """
    start = time.monotonic()
    try:
        response = await client.get(url, timeout=5.0)
        elapsed = time.monotonic() - start
        response.raise_for_status()
        return {
            "available": True,
            "status_code": response.status_code,
            "response_time_ms": round(elapsed * 1000),
        }
    except Exception as exc:
        elapsed = time.monotonic() - start
        return {
            "available": False,
            "error": str(exc),
            "response_time_ms": round(elapsed * 1000),
        }
