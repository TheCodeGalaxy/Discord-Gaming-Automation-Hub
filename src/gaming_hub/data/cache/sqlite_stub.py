"""SQLite cache backend stub.

TODO: Implement a file-based key-value store using ``sqlite3``
with a ``(key, value, expires_at)`` table. For now all methods
are no-ops that log a warning.
"""

from __future__ import annotations

import logging
from typing import Any

from gaming_hub.core.interfaces import CacheBackend

logger = logging.getLogger(__name__)


class SqliteCache(CacheBackend):
    """Placeholder for the SQLite cache backend."""

    name = "sqlite"

    async def get(self, key: str) -> Any | None:
        """SQLite cache not implemented."""
        logger.warning("SQLite cache get(%s) not implemented", key)
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """SQLite cache not implemented."""
        logger.warning("SQLite cache set(%s) not implemented", key)

    async def delete(self, key: str) -> None:
        """SQLite cache not implemented."""
        logger.warning("SQLite cache delete(%s) not implemented", key)

    async def clear(self) -> None:
        """SQLite cache not implemented."""
        logger.warning("SQLite cache clear() not implemented")

    async def stats(self) -> dict[str, Any]:
        """SQLite cache not implemented."""
        logger.warning("SQLite cache stats() not implemented")
        return {"hit": 0, "miss": 0, "hit_ratio": 0.0, "size": 0, "backend": "sqlite"}
