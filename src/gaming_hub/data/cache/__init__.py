"""Caching backends and shared cache utilities."""

from gaming_hub.core.interfaces import CacheBackend
from gaming_hub.data.cache.decorator import CachedProviderDecorator
from gaming_hub.data.cache.in_memory import InMemoryCache
from gaming_hub.data.cache.key import make_cache_key

__all__ = [
    "CacheBackend",
    "CachedProviderDecorator",
    "InMemoryCache",
    "make_cache_key",
]
