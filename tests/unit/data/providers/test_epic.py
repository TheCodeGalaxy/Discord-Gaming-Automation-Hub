"""Unit tests for EpicProvider."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from gaming_hub.data.providers.epic import EpicProvider
from gaming_hub.models.dto.request import SearchRequest

FIXTURES = Path(__file__).parents[3] / "fixtures" / "epic"


@pytest.fixture()
def mock_client() -> AsyncMock:
    """Return a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture()
def provider(mock_client: AsyncMock, settings) -> EpicProvider:
    """Return an EpicProvider with mocked HTTP client."""
    return EpicProvider(http_client=mock_client, settings=settings)


def _load_fixture(name: str) -> dict:
    path = FIXTURES / name
    with path.open() as f:
        return json.load(f)


@pytest.mark.unit
class TestEpicFreeGames:
    """Tests for EpicProvider.get_free_games()."""

    @pytest.mark.asyncio
    async def test_get_free_games_returns_games(
        self, provider: EpicProvider,
    ) -> None:
        """Verify get_free_games returns games with is_free=True and free_until."""
        data = _load_fixture("free_games_current.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        result = await provider.get_free_games()

        assert len(result.games) == 2  # noqa: PLR2004
        assert result.metadata.returned == 2  # noqa: PLR2004

        game = result.games[0]
        assert game.is_free is True
        assert game.free_until == date(2024, 6, 27)
        assert game.title == "Doki Doki Literature Club"
        assert game.epic_namespace == "clint"
        assert game.cover_url is not None

    @pytest.mark.asyncio
    async def test_get_free_games_upcoming(
        self, provider: EpicProvider,
    ) -> None:
        """Verify get_free_games(upcoming=True) returns upcoming promotions."""
        data = _load_fixture("free_games_upcoming.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        result = await provider.get_free_games(upcoming=True)

        assert len(result.games) == 1
        game = result.games[0]
        assert game.is_free is True
        assert game.free_until == date(2024, 7, 11)
        assert game.title == "Wonder Game"

    @pytest.mark.asyncio
    async def test_get_free_games_no_promotions(
        self, provider: EpicProvider,
    ) -> None:
        """Verify get_free_games returns empty when no promotions exist."""
        empty = {"data": {"Catalog": {"searchStore": {"elements": []}}}}
        mock_resp = MagicMock()
        mock_resp.json.return_value = empty
        provider._get = AsyncMock(return_value=mock_resp)

        result = await provider.get_free_games()

        assert len(result.games) == 0

    @pytest.mark.asyncio
    async def test_get_free_games_cover_url(
        self, provider: EpicProvider,
    ) -> None:
        """Verify Game objects from Epic have cover_url pointing to Epic CDN."""
        data = _load_fixture("free_games_current.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        result = await provider.get_free_games()

        for game in result.games:
            assert game.cover_url is not None
            assert "epicgames.com" in str(game.cover_url)

    @pytest.mark.asyncio
    async def test_get_free_games_returns_error_on_failure(
        self, provider: EpicProvider,
    ) -> None:
        """Verify get_free_games returns ProviderResult with errors on exception."""
        provider._get = AsyncMock(side_effect=httpx.ConnectError("down"))

        result = await provider.get_free_games()

        assert len(result.games) == 0
        assert len(result.metadata.errors) == 1


@pytest.mark.unit
class TestEpicSearch:
    """Tests for EpicProvider.search()."""

    @pytest.mark.asyncio
    async def test_search_returns_catalog_results(
        self, provider: EpicProvider,
    ) -> None:
        """Verify search filters catalog elements by keyword title."""
        data = _load_fixture("catalog_search.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        request = SearchRequest(query="cyberpunk", limit=5)
        result = await provider.search(request)

        assert len(result.games) == 1
        game = result.games[0]
        assert game.epic_namespace == "cbd"
        assert game.title == "Cyberpunk 2077"
        assert game.id == "cyberpunk1"

    @pytest.mark.asyncio
    async def test_search_genres_is_list_of_strings(
        self, provider: EpicProvider,
    ) -> None:
        """Verify search result genres is a list of strings."""
        data = _load_fixture("catalog_search.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        request = SearchRequest(query="cyberpunk", limit=5)
        result = await provider.search(request)

        game = result.games[0]
        assert isinstance(game.genres, list)
        assert len(game.genres) > 0
        assert isinstance(game.genres[0], str)

    @pytest.mark.asyncio
    async def test_search_returns_all_when_keyword_blank(
        self, provider: EpicProvider,
    ) -> None:
        """Verify a blank keyword returns the whole catalog (capped by limit)."""
        data = _load_fixture("catalog_search.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        request = SearchRequest(query="", limit=2)
        result = await provider.search(request)

        assert len(result.games) == 2  # noqa: PLR2004

    @pytest.mark.asyncio
    async def test_search_returns_error_on_failure(
        self, provider: EpicProvider,
    ) -> None:
        """Verify search returns ProviderResult with errors on network failure."""
        provider._get = AsyncMock(side_effect=httpx.ConnectError("network error"))

        request = SearchRequest(query="test")
        result = await provider.search(request)

        assert len(result.games) == 0
        assert len(result.metadata.errors) == 1


@pytest.mark.unit
class TestEpicDeals:
    """Tests for EpicProvider.get_deals()."""

    @pytest.mark.asyncio
    async def test_get_deals_returns_deals(
        self, provider: EpicProvider,
    ) -> None:
        """Verify get_deals returns Deal objects from promotions feed."""
        data = _load_fixture("free_games_current.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        result = await provider.get_deals(limit=5)

        assert len(result.deals) == 2  # noqa: PLR2004
        assert result.metadata.returned == 2  # noqa: PLR2004

        deal = result.deals[0]
        assert deal.title == "Doki Doki Literature Club"
        assert deal.current_price == 0  # free game
        assert deal.is_free is True

    @pytest.mark.asyncio
    async def test_get_deals_limits_results(
        self, provider: EpicProvider,
    ) -> None:
        """Verify get_deals respects the limit parameter."""
        data = _load_fixture("free_games_current.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        result = await provider.get_deals(limit=1)

        assert len(result.deals) == 1

    @pytest.mark.asyncio
    async def test_get_deals_returns_error_on_failure(
        self, provider: EpicProvider,
    ) -> None:
        """Verify get_deals returns ProviderResult with errors on exception."""
        provider._get = AsyncMock(side_effect=httpx.ConnectError("down"))

        result = await provider.get_deals()

        assert len(result.deals) == 0
        assert len(result.metadata.errors) == 1


@pytest.mark.unit
class TestEpicNormalization:
    """Tests for Epic normalization edge cases."""

    def test_normalize_free_game_missing_images(self) -> None:
        """Verify _normalize_free_game handles missing keyImages gracefully."""
        provider = EpicProvider.__new__(EpicProvider)
        promo = {
            "promotionalOffers": [
                {
                    "startDate": "2024-06-20T15:00:00.000Z",
                    "endDate": "2024-06-27T15:00:00.000Z",
                },
            ],
        }
        elem = {
            "id": "test",
            "title": "Test Game",
            "namespace": "testns",
            "offerType": "BASE_GAME",
        }
        game = provider._normalize_free_game(elem, promo)
        assert game.cover_url is None
        assert game.title == "Test Game"
        assert game.is_free is True

    def test_normalize_free_game_no_description(self) -> None:
        """Verify _normalize_free_game handles missing description."""
        provider = EpicProvider.__new__(EpicProvider)
        promo = {
            "promotionalOffers": [
                {
                    "startDate": "2024-06-20T15:00:00.000Z",
                    "endDate": "2024-06-27T15:00:00.000Z",
                },
            ],
        }
        elem = {
            "id": "test2",
            "title": "No Desc Game",
            "namespace": "ndesc",
            "keyImages": [
                {"type": "Thumbnail", "url": "https://cdn.epicgames.com/test.jpg"},
            ],
        }
        game = provider._normalize_free_game(elem, promo)
        assert game.description is None
        assert game.short_description is None

    def test_normalize_free_game_uses_product_name_fallback(self) -> None:
        """Verify title falls back to productName when title is missing."""
        provider = EpicProvider.__new__(EpicProvider)
        promo = {
            "promotionalOffers": [
                {
                    "startDate": "2024-06-20T15:00:00.000Z",
                    "endDate": "2024-06-27T15:00:00.000Z",
                },
            ],
        }
        elem = {
            "id": "test3",
            "productName": "Product Fallback",
            "namespace": "pfb",
        }
        game = provider._normalize_free_game(elem, promo)
        assert game.title == "Product Fallback"

    def test_parse_date_none(self) -> None:
        """Verify _parse_date returns None for None input."""
        assert EpicProvider._parse_date(None) is None

    def test_parse_date_invalid(self) -> None:
        """Verify _parse_date returns None for invalid input."""
        assert EpicProvider._parse_date("not-a-date") is None

    def test_parse_date_valid(self) -> None:
        """Verify _parse_date returns correct date."""
        result = EpicProvider._parse_date("2024-06-27T15:00:00.000Z")
        assert result == date(2024, 6, 27)


@pytest.mark.unit
class TestEpicHealth:
    """Tests for EpicProvider.healthcheck()."""

    @pytest.mark.asyncio
    async def test_healthcheck_returns_status(
        self, provider: EpicProvider,
    ) -> None:
        """Verify healthcheck returns status dict."""
        provider.http_client = AsyncMock(spec=httpx.AsyncClient)
        result = await provider.healthcheck()
        assert "available" in result
        assert "status_code" in result
        assert "response_time_ms" in result
