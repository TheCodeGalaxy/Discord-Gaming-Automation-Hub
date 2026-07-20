"""In-memory cache backend.

Stores arbitrary Python objects with TTL-based expiration.
Thread-safe via asyncio.Lock. Includes periodic cleanup.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from gaming_hub.core.interfaces import CacheBackend

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class CachedValue:
    """A single cache entry with TTL tracking."""

    value: Any
    expires_at: float
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Return True if the entry has passed its TTL."""
        return time.monotonic() >= self.expires_at

    @property
    def ttl_remaining(self) -> float:
        """Return seconds until expiration (0 if already expired)."""
        return max(0.0, self.expires_at - time.monotonic())


@dataclass
class CacheStats:
    """Aggregate cache hit/miss statistics."""

    hit: int = 0
    miss: int = 0
    size: int = 0

    @property
    def hit_ratio(self) -> float:
        """Return the fraction of hits among total accesses."""
        total = self.hit + self.miss
        return self.hit / total if total > 0 else 0.0


class InMemoryCache(CacheBackend):
    """Dict-based cache with TTL eviction and asyncio safety."""

    name = "memory"

    def __init__(self, default_ttl: int = 300) -> None:
        """Initialize cache store, stats, lock, and cleanup task reference."""
        self._store: dict[str, CachedValue] = {}
        self._default_ttl = default_ttl
        self._stats = CacheStats()
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None

    async def start(self, cleanup_interval: int = 60) -> None:
        """Start the periodic cleanup background task."""
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(cleanup_interval),
        )

    async def stop(self) -> None:
        """Cancel the periodic cleanup task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None

    async def get(self, key: str) -> Any | None:
        """Retrieve a cached value, returning None on miss or expiration."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._stats.miss += 1
                return None
            if entry.is_expired:
                del self._store[key]
                self._stats.miss += 1
                return None
            self._stats.hit += 1
            entry.hit_count += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store a value with optional TTL (defaults to instance default)."""
        async with self._lock:
            self._store[key] = CachedValue(
                value=value,
                expires_at=time.monotonic() + (ttl if ttl is not None else self._default_ttl),
                hit_count=0,
            )

    async def delete(self, key: str) -> None:
        """Remove a cache entry by key (no-op if missing)."""
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        """Remove all cached values and reset stats."""
        async with self._lock:
            self._store.clear()
            self._stats = CacheStats()

    async def stats(self) -> dict[str, Any]:
        """Return current cache statistics."""
        async with self._lock:
            self._stats.size = len(self._store)
            return {
                "hit": self._stats.hit,
                "miss": self._stats.miss,
                "hit_ratio": round(self._stats.hit_ratio, 4),
                "size": self._stats.size,
            }

    async def _cleanup_loop(self, interval: int) -> None:
        """Periodically evict expired entries."""
        while True:
            await asyncio.sleep(interval)
            await self._evict_expired()

    async def _evict_expired(self) -> int:
        """Remove all expired entries. Return count of evicted keys."""
        async with self._lock:
            expired_keys = [k for k, v in self._store.items() if v.is_expired]
            for k in expired_keys:
                del self._store[k]
            return len(expired_keys)

    @property
    def size(self) -> int:
        """Return approximate number of entries in the store."""
        return len(self._store)

    def set_on_evict(self, callback: Callable[[str, CachedValue], None]) -> None:
        """Register a callback invoked when an entry is evicted.

        Useful for logging or cleanup of external resources.
        """
        self._on_evict = callback
