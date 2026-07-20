"""Health check endpoint used by Docker and monitoring."""

# TODO: Cross-reference roadmap phase 22 (Web API)

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from gaming_hub import __version__

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, Any]:
    """Return a simple health status payload."""
    return {
        "status": "ok",
        "version": __version__,
    }
