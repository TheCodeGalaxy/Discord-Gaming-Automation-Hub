"""Unit tests for InMemoryCache."""
# ruff: noqa: PLR2004 — test assertions use literal magic values for clarity

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from gaming_hub.data.cache.in_memory import CachedValue, CacheStats, InMemoryCache


@pytest.fixture()
def cache() -> InMemoryCache:
    """Return a fresh InMemoryCache with short TTL."""
    return InMemoryCache(default_ttl=2)


@pytest.mark.unit
class TestInMemoryCacheBasics:
    """Core get/set/delete/clear behavior."""

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing_key(self) -> None:
        """Verify get returns None when key does not exist."""
        cache = InMemoryCache()
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get_round_trip(self, cache: InMemoryCache) -> None:
        """Verify a set value is returned by get."""
        await cache.set("key1", {"hello": "world"})
        result = await cache.get("key1")
        assert result == {"hello": "world"}

    @pytest.mark.asyncio
    async def test_get_returns_none_after_ttl_expiry(self) -> None:
        """Verify get returns None after the TTL has expired."""
        cache = InMemoryCache(default_ttl=1)
        await cache.set("key1", "value")
        await asyncio.sleep(1.1)
        result = await cache.get("key1")
        assert result is None
        await cache.stop()

    @pytest.mark.asyncio
    async def test_set_overwrites_existing_key(self, cache: InMemoryCache) -> None:
        """Verify set replaces an existing value at the same key."""
        await cache.set("key1", "first")
        await cache.set("key1", "second")
        result = await cache.get("key1")
        assert result == "second"

    @pytest.mark.asyncio
    async def test_set_resets_ttl(self) -> None:
        """Verify set resets the TTL for an existing key."""
        cache = InMemoryCache(default_ttl=1)
        await cache.set("key1", "first")
        await asyncio.sleep(0.6)
        await cache.set("key1", "second")
        await asyncio.sleep(0.6)
        result = await cache.get("key1")
        assert result == "second"
        await cache.stop()

    @pytest.mark.asyncio
    async def test_delete_removes_key(self, cache: InMemoryCache) -> None:
        """Verify delete removes a key from the cache."""
        await cache.set("key1", "value")
        await cache.delete("key1")
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_non_existent_key_is_noop(self, cache: InMemoryCache) -> None:
        """Verify delete on a non-existent key does not raise."""
        await cache.delete("nonexistent")
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_clear_empties_store(self, cache: InMemoryCache) -> None:
        """Verify clear removes all keys from the cache."""
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.clear()
        assert await cache.get("a") is None
        assert await cache.get("b") is None


@pytest.mark.unit
class TestInMemoryCacheTTL:
    """Custom TTL per set."""

    @pytest.mark.asyncio
    async def test_custom_ttl_shorter_than_default(self) -> None:
        """Verify custom TTL shorter than default is respected."""
        cache = InMemoryCache(default_ttl=60)
        await cache.set("short", "value", ttl=1)
        await asyncio.sleep(1.1)
        result = await cache.get("short")
        assert result is None
        await cache.stop()

    @pytest.mark.asyncio
    async def test_custom_ttl_longer_than_default(self) -> None:
        """Verify custom TTL longer than default is respected."""
        cache = InMemoryCache(default_ttl=1)
        await cache.set("long", "value", ttl=60)
        await asyncio.sleep(1.1)
        result = await cache.get("long")
        assert result == "value"
        await cache.stop()

    @pytest.mark.asyncio
    async def test_ttl_respected_on_get(self) -> None:
        """Verify get returns None after the configured TTL elapses."""
        cache = InMemoryCache(default_ttl=0.5)
        await cache.set("key1", "value")
        result = await cache.get("key1")
        assert result == "value"
        await asyncio.sleep(0.6)
        result = await cache.get("key1")
        assert result is None
        await cache.stop()

    @pytest.mark.asyncio
    async def test_expired_entries_evicted_on_access(self) -> None:
        """Verify expired entries are lazily evicted on get."""
        cache = InMemoryCache(default_ttl=0.5)
        await cache.set("key1", "value")
        await asyncio.sleep(0.6)
        await cache.get("key1")
        assert "key1" not in cache._store
        await cache.stop()

    @pytest.mark.asyncio
    async def test_cached_value_ttl_remaining(self) -> None:
        """Verify ttl_remaining returns positive time until expiry."""
        cache = InMemoryCache(default_ttl=60)
        await cache.set("key1", "value")
        entry: CachedValue = cache._store["key1"]
        assert entry.ttl_remaining > 55
        await cache.stop()

    @pytest.mark.asyncio
    async def test_cached_value_is_expired(self) -> None:
        """Verify is_expired returns True for past-expiry entries."""
        cache = InMemoryCache(default_ttl=0.01)
        await cache.set("key1", "value")
        await asyncio.sleep(0.02)
        entry: CachedValue = cache._store["key1"]
        assert entry.is_expired
        await cache.stop()


@pytest.mark.unit
class TestInMemoryCacheConcurrency:
    """Concurrent access safety."""

    @pytest.mark.asyncio
    async def test_concurrent_get_set(self) -> None:
        """Verify concurrent get/set operations are safe."""
        cache = InMemoryCache()

        async def worker(i: int) -> None:
            await cache.set(f"key{i}", i)
            val = await cache.get(f"key{i}")
            assert val == i

        tasks = [worker(i) for i in range(10)]
        await asyncio.gather(*tasks)
        await cache.stop()

    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self) -> None:
        """Verify concurrent read/write operations do not corrupt state."""
        cache = InMemoryCache()

        async def writer(key: str, value: Any) -> None:
            for _ in range(5):
                await cache.set(key, value)
                await asyncio.sleep(0.01)

        async def reader(key: str) -> None:
            for _ in range(5):
                await cache.get(key)
                await asyncio.sleep(0.01)

        tasks = [
            writer("a", 1),
            writer("b", 2),
            reader("a"),
            reader("b"),
            writer("c", 3),
            reader("c"),
        ]
        await asyncio.gather(*tasks)
        await cache.stop()


@pytest.mark.unit
class TestInMemoryCacheStats:
    """Cache statistics accuracy."""

    @pytest.mark.asyncio
    async def test_stats_initial_state(self) -> None:
        """Verify stats start at zero for a fresh cache."""
        cache = InMemoryCache()
        s = await cache.stats()
        assert s["hit"] == 0
        assert s["miss"] == 0
        assert s["hit_ratio"] == 0.0
        assert s["size"] == 0

    @pytest.mark.asyncio
    async def test_miss_increments_on_get_nonexistent(self, cache: InMemoryCache) -> None:
        """Verify a miss increments the miss counter."""
        await cache.get("no_key")
        s = await cache.stats()
        assert s["miss"] == 1
        assert s["hit"] == 0

    @pytest.mark.asyncio
    async def test_hit_increments_on_get_existing(self, cache: InMemoryCache) -> None:
        """Verify a hit increments the hit counter."""
        await cache.set("k", "v")
        await cache.get("k")
        s = await cache.stats()
        assert s["hit"] == 1
        assert s["miss"] == 0

    @pytest.mark.asyncio
    async def test_hit_multiple_accesses(self, cache: InMemoryCache) -> None:
        """Verify multiple hits increment the hit counter each time."""
        await cache.set("k", "v")
        await cache.get("k")
        await cache.get("k")
        s = await cache.stats()
        assert s["hit"] == 2
        assert s["miss"] == 0

    @pytest.mark.asyncio
    async def test_hit_ratio_calculation(self, cache: InMemoryCache) -> None:
        """Verify hit_ratio reflects hit/(hit+miss) correctly."""
        await cache.set("k", "v")
        await cache.get("k")
        await cache.get("k")
        await cache.get("missing")
        s = await cache.stats()
        assert s["hit"] == 2
        assert s["miss"] == 1
        assert s["hit_ratio"] >= 0.6666

    @pytest.mark.asyncio
    async def test_size_reflects_store(self, cache: InMemoryCache) -> None:
        """Verify size matches the number of cached entries."""
        await cache.set("a", 1)
        s = await cache.stats()
        assert s["size"] == 1
        await cache.set("b", 2)
        s = await cache.stats()
        assert s["size"] == 2

    @pytest.mark.asyncio
    async def test_clear_resets_stats(self, cache: InMemoryCache) -> None:
        """Verify clear zeros all stats counters."""
        await cache.set("k", "v")
        await cache.get("k")
        await cache.get("missing")
        await cache.clear()
        s = await cache.stats()
        assert s["hit"] == 0
        assert s["miss"] == 0
        assert s["size"] == 0


@pytest.mark.unit
class TestInMemoryCacheCleanup:
    """Periodic cleanup behavior."""

    @pytest.mark.asyncio
    async def test_cleanup_evicts_expired_entries(self) -> None:
        """Verify _evict_expired removes all expired entries."""
        cache = InMemoryCache(default_ttl=0.5)
        await cache.set("k1", "v1")
        await cache.set("k2", "v2")
        await asyncio.sleep(0.6)
        evicted = await cache._evict_expired()
        assert evicted == 2
        assert cache.size == 0
        await cache.stop()

    @pytest.mark.asyncio
    async def test_cleanup_only_evicts_expired(self) -> None:
        """Verify _evict_expired only removes expired entries."""
        cache = InMemoryCache(default_ttl=60)
        await cache.set("fresh", "v")
        await cache.set("stale", "old", ttl=0.1)
        await asyncio.sleep(0.15)
        evicted = await cache._evict_expired()
        assert evicted == 1
        assert cache.size == 1
        assert await cache.get("fresh") == "v"
        await cache.stop()

    @pytest.mark.asyncio
    async def test_background_cleanup_runs(self) -> None:
        """Verify the background cleanup task evicts expired entries."""
        cache = InMemoryCache(default_ttl=0.3)
        await cache.set("k", "v")
        await cache.start(cleanup_interval=1)
        await asyncio.sleep(0.5)
        evicted = await cache._evict_expired()
        assert evicted == 1
        await cache.stop()


@pytest.mark.unit
class TestCachedValueDataclass:
    """CachedValue property correctness."""

    def test_is_expired_false_when_not_expired(self) -> None:
        """Verify is_expired is False for future expiry times."""
        cv = CachedValue(value="x", expires_at=time.monotonic() + 60)
        assert not cv.is_expired

    def test_is_expired_true_when_past_expiry(self) -> None:
        """Verify is_expired is True for past expiry times."""
        cv = CachedValue(value="x", expires_at=time.monotonic() - 1)
        assert cv.is_expired

    def test_ttl_remaining_positive(self) -> None:
        """Verify ttl_remaining is positive for future expiry."""
        cv = CachedValue(value="x", expires_at=time.monotonic() + 30)
        assert 25 < cv.ttl_remaining <= 30

    def test_ttl_remaining_non_negative(self) -> None:
        """Verify ttl_remaining is 0 for past expiry."""
        cv = CachedValue(value="x", expires_at=time.monotonic() - 5)
        assert cv.ttl_remaining == 0.0


@pytest.mark.unit
class TestCacheStatsDataclass:
    """CacheStats property correctness."""

    def test_hit_ratio_zero_when_no_accesses(self) -> None:
        """Verify hit_ratio is 0 when there are no accesses."""
        s = CacheStats()
        assert s.hit_ratio == 0.0

    def test_hit_ratio_partial(self) -> None:
        """Verify hit_ratio is 2/3 with 2 hits and 1 miss."""
        s = CacheStats(hit=2, miss=1)
        assert 0.666 < s.hit_ratio < 0.667

    def test_hit_ratio_perfect(self) -> None:
        """Verify hit_ratio is 1.0 with no misses."""
        s = CacheStats(hit=5, miss=0)
        assert s.hit_ratio == 1.0

    def test_hit_ratio_zero(self) -> None:
        """Verify hit_ratio is 0 with no hits."""
        s = CacheStats(hit=0, miss=3)
        assert s.hit_ratio == 0.0
