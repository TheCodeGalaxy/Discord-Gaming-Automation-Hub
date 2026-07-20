"""Small pure validation helpers used across layers."""

from __future__ import annotations


def clamp(value: int, min_value: int, max_value: int) -> int:
    """Return ``value`` limited to the inclusive [min, max] range."""
    return max(min_value, min(value, max_value))


def sanitize_query(query: str, max_length: int = 200) -> str:
    """Trim and strip a free-text search query.

    Args:
        query: Raw user query.
        max_length: Maximum allowed length.

    Returns:
        Cleaned query string.
    """
    return query.strip()[:max_length]
