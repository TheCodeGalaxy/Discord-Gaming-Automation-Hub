"""Unit tests for make_cache_key."""
# ruff: noqa: PLR2004 — test assertions use literal magic values for clarity

from __future__ import annotations

import pytest

from gaming_hub.data.cache.key import make_cache_key


@pytest.mark.unit
class TestMakeCacheKey:
    """Cache key generation consistency and determinism."""

    def test_basic_key_format(self) -> None:
        """Verify the key has provider:method:hash format with 12-char hash."""
        key = make_cache_key("cheapshark", "search", query="hades", limit=10)
        assert key.startswith("cheapshark:search:")
        parts = key.split(":")
        assert len(parts) == 3
        assert len(parts[2]) == 12

    def test_deterministic_output(self) -> None:
        """Verify same inputs produce identical keys."""
        k1 = make_cache_key("p", "m", a=1, b=2)
        k2 = make_cache_key("p", "m", a=1, b=2)
        assert k1 == k2

    def test_different_params_different_key(self) -> None:
        """Verify different param values produce different keys."""
        k1 = make_cache_key("p", "m", query="cyberpunk")
        k2 = make_cache_key("p", "m", query="hades")
        assert k1 != k2

    def test_param_order_irrelevant(self) -> None:
        """Verify keys are order-independent for param dicts."""
        k1 = make_cache_key("provider", "method", a=1, b=2, c=3)
        k2 = make_cache_key("provider", "method", c=3, a=1, b=2)
        assert k1 == k2

    def test_none_params_excluded(self) -> None:
        """Verify None-valued params are excluded from hash."""
        k1 = make_cache_key("p", "m", a=1, b=None, c=2)
        k2 = make_cache_key("p", "m", a=1, c=2)
        assert k1 == k2

    def test_key_with_string_int_bool(self) -> None:
        """Verify keys handle mixed string, int, and bool params."""
        key = make_cache_key(
            "epic", "free_games",
            upcoming=True,
            limit=5,
            locale="en-US",
        )
        assert key.startswith("epic:free_games:")
        parts = key.split(":")
        assert len(parts[2]) == 12

    def test_different_provider_different_key(self) -> None:
        """Verify different provider names produce different keys."""
        k1 = make_cache_key("cheapshark", "deals", limit=10)
        k2 = make_cache_key("epic", "deals", limit=10)
        assert k1 != k2

    def test_different_method_different_key(self) -> None:
        """Verify different method names produce different keys."""
        k1 = make_cache_key("steam", "search", appids=730)
        k2 = make_cache_key("steam", "trending", appids=730)
        assert k1 != k2

    def test_key_length_bounded(self) -> None:
        """Verify keys remain bounded even with very large param values."""
        long_value = "x" * 10000
        key = make_cache_key("p", "m", value=long_value)
        parts = key.split(":")
        assert len(parts[2]) == 12
        assert len(key) < 50

    def test_all_none_params(self) -> None:
        """Verify all-None params still produces a valid key."""
        key = make_cache_key("p", "m", a=None, b=None)
        parts = key.split(":")
        assert len(parts[2]) == 12

    def test_empty_params(self) -> None:
        """Verify no params still produces a valid key."""
        key = make_cache_key("provider", "method")
        assert key.startswith("provider:method:")
        assert len(key) == len("provider:method:") + 12
