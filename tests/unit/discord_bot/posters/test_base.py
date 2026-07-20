"""Tests for BasePoster and PosterResult."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from gaming_hub.discord_bot.posters.base import BasePoster, PosterResult


class _SimplePoster(BasePoster):
    """Concrete poster for testing."""
    CHANNEL = "#test"

    async def _build_content(self, job_data: dict) -> list:
        return [MagicMock(title="Test Embed")]


@pytest.mark.unit
class TestBasePoster:
    """BasePoster execute() behavior."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_success(self) -> None:
        """Dry-run mode logs and returns success without sending."""
        bot = MagicMock()
        poster = _SimplePoster(bot, 12345)
        poster.dry_run = True
        result = await poster.execute()
        assert result.success is True
        assert result.dry_run is True
        assert result.embed_count == 1
        bot.get_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_content_returns_zero_embeds(self) -> None:
        """No content produces a successful zero-embed result."""
        bot = MagicMock()

        class _EmptyPoster(BasePoster):
            CHANNEL = "#empty"
            async def _build_content(self, job_data: dict) -> list:
                return []

        poster = _EmptyPoster(bot, 12345)
        result = await poster.execute()
        assert result.success is True
        assert result.embed_count == 0

    @pytest.mark.asyncio
    async def test_live_mode_sends_to_channel(self) -> None:
        """Live mode fetches the channel and sends embeds."""
        bot = MagicMock()
        channel = AsyncMock()
        bot.get_channel.return_value = channel

        poster = _SimplePoster(bot, 12345)
        result = await poster.execute()
        assert result.success is True
        assert result.embed_count == 1
        channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exception_returns_error_result(self) -> None:
        """An exception inside _build_content returns an error result."""
        bot = MagicMock()

        class _BrokenPoster(BasePoster):
            CHANNEL = "#broken"
            async def _build_content(self, job_data: dict) -> list:
                raise RuntimeError("boom")

        poster = _BrokenPoster(bot, 12345)
        result = await poster.execute()
        assert result.success is False
        assert "boom" in (result.error or "")


@pytest.mark.unit
class TestPosterResult:
    """PosterResult dataclass behavior."""

    def test_defaults(self) -> None:
        """Verify default values."""
        r = PosterResult()
        assert r.success is False
        assert r.embed_count == 0
        assert r.message_ids == []
        assert r.dry_run is False
        assert r.error is None
