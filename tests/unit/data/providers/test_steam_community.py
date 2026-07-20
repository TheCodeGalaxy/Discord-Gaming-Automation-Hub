"""Unit tests for SteamCommunityProvider."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from gaming_hub.data.providers.steam import SteamCommunityProvider
from gaming_hub.models.dto.request import SearchRequest

FIXTURES = Path(__file__).parents[3] / "fixtures" / "steam"


@pytest.fixture()
def mock_client() -> AsyncMock:
    """Return a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture()
def provider(mock_client: AsyncMock, settings) -> SteamCommunityProvider:
    """Return a SteamCommunityProvider with mocked HTTP client."""
    return SteamCommunityProvider(http_client=mock_client, settings=settings)


def _load_json(name: str) -> dict:
    with (FIXTURES / name).open() as f:
        return json.load(f)


def _load_html(name: str) -> str:
    return (FIXTURES / name).read_text()


@pytest.mark.unit
class TestSteamSearch:
    """Tests for SteamCommunityProvider.search()."""

    @pytest.mark.asyncio
    async def test_search_by_app_id(
        self, provider: SteamCommunityProvider,
    ) -> None:
        """Verify search(steam_app_id=730) returns a Game with correct title."""
        data = _load_json("appdetails_730.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        request = SearchRequest(steam_app_id=730)
        result = await provider.search(request)

        assert len(result.games) == 1
        game = result.games[0]
        assert game.title == "Counter-Strike 2"
        assert game.steam_app_id == 730  # noqa: PLR2004

    @pytest.mark.asyncio
    async def test_search_populates_genres_and_tags(
        self, provider: SteamCommunityProvider,
    ) -> None:
        """Verify search populates genres, tags, developers, publishers."""
        data = _load_json("appdetails_730.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        request = SearchRequest(steam_app_id=730)
        result = await provider.search(request)

        game = result.games[0]
        assert len(game.genres) > 0
        assert "Action" in game.genres
        assert len(game.tags) > 0
        assert "FPS" in game.tags
        assert "Valve" in game.developers
        assert "Valve" in game.publishers

    @pytest.mark.asyncio
    async def test_search_has_review_metadata(
        self, provider: SteamCommunityProvider,
    ) -> None:
        """Verify search populates review scores and metacritic."""
        data = _load_json("appdetails_730.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        request = SearchRequest(steam_app_id=730)
        result = await provider.search(request)

        game = result.games[0]
        assert game.metacritic_score == 88  # noqa: PLR2004
        assert game.steam_review_score is not None
        assert game.steam_review_count is not None

    @pytest.mark.asyncio
    async def test_search_not_found_returns_empty(
        self, provider: SteamCommunityProvider,
    ) -> None:
        """Verify search returns empty when app is not found."""
        data = _load_json("appdetails_not_found.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        request = SearchRequest(steam_app_id=999999)
        result = await provider.search(request)

        assert len(result.games) == 0
        assert len(result.metadata.errors) == 1

    @pytest.mark.asyncio
    async def test_search_no_id_no_query(
        self, provider: SteamCommunityProvider,
    ) -> None:
        """Verify search returns empty when no steam_app_id or query."""
        request = SearchRequest()
        result = await provider.search(request)

        assert len(result.games) == 0
        assert len(result.metadata.errors) == 1

    @pytest.mark.asyncio
    async def test_search_returns_error_on_failure(
        self, provider: SteamCommunityProvider,
    ) -> None:
        """Verify search returns ProviderResult with errors on exception."""
        provider._get = AsyncMock(side_effect=httpx.ConnectError("down"))

        request = SearchRequest(steam_app_id=730)
        result = await provider.search(request)

        assert len(result.games) == 0
        assert len(result.metadata.errors) == 1


@pytest.mark.unit
class TestSteamHtmlDetection:
    """Tests for SteamCommunityProvider HTML error detection."""

    def test_detect_html_via_content_type(self) -> None:
        """Verify HTML detected via Content-Type header."""
        provider = SteamCommunityProvider.__new__(SteamCommunityProvider)
        response = MagicMock(spec=httpx.Response)
        response.headers = {"content-type": "text/html; charset=utf-8"}
        response.text = "not relevant"
        assert provider._detect_html_error(response) is True

    def test_detect_html_via_doctype(self) -> None:
        """Verify HTML detected via DOCTYPE prefix."""
        provider = SteamCommunityProvider.__new__(SteamCommunityProvider)
        response = MagicMock(spec=httpx.Response)
        response.headers = {"content-type": "application/json"}
        response.text = "<!DOCTYPE html>\n<html>..."
        assert provider._detect_html_error(response) is True

    def test_detect_html_via_html_tag(self) -> None:
        """Verify HTML detected via <html> prefix."""
        provider = SteamCommunityProvider.__new__(SteamCommunityProvider)
        response = MagicMock(spec=httpx.Response)
        response.headers = {"content-type": "text/plain"}
        response.text = "<html><body>error</body></html>"
        assert provider._detect_html_error(response) is True

    def test_detect_html_returns_false_for_json(self) -> None:
        """Verify JSON response is NOT detected as HTML."""
        provider = SteamCommunityProvider.__new__(SteamCommunityProvider)
        response = MagicMock(spec=httpx.Response)
        response.headers = {"content-type": "application/json"}
        response.text = '{"success": true}'
        assert provider._detect_html_error(response) is False

    def test_detect_html_empty_content_type(self) -> None:
        """Verify empty Content-Type is not flagged as HTML."""
        provider = SteamCommunityProvider.__new__(SteamCommunityProvider)
        response = MagicMock(spec=httpx.Response)
        response.headers = {}
        response.text = '{"foo": "bar"}'
        assert provider._detect_html_error(response) is False


@pytest.mark.unit
class TestSteamTrending:
    """Tests for SteamCommunityProvider.get_trending()."""

    @pytest.mark.asyncio
    async def test_get_trending_returns_games(
        self, provider: SteamCommunityProvider,
    ) -> None:
        """Verify get_trending returns Game objects with steam_app_id."""
        html = _load_html("trending_page.html")
        mock_resp = MagicMock()
        mock_resp.text = html
        provider._get = AsyncMock(return_value=mock_resp)

        result = await provider.get_trending(limit=10)

        assert len(result.games) == 4  # noqa: PLR2004
        assert result.games[0].steam_app_id == 730  # noqa: PLR2004
        assert result.games[0].title == "Counter-Strike 2"

    @pytest.mark.asyncio
    async def test_get_trending_respects_limit(
        self, provider: SteamCommunityProvider,
    ) -> None:
        """Verify get_trending respects the limit parameter."""
        html = _load_html("trending_page.html")
        mock_resp = MagicMock()
        mock_resp.text = html
        provider._get = AsyncMock(return_value=mock_resp)

        result = await provider.get_trending(limit=2)

        assert len(result.games) == 2  # noqa: PLR2004

    @pytest.mark.asyncio
    async def test_get_trending_returns_error_on_failure(
        self, provider: SteamCommunityProvider,
    ) -> None:
        """Verify get_trending returns error on HTTP failure."""
        provider._get = AsyncMock(side_effect=httpx.ConnectError("down"))

        result = await provider.get_trending()

        assert len(result.games) == 0
        assert len(result.metadata.errors) == 1


@pytest.mark.unit
class TestSteamNormalization:
    """Tests for Steam normalization edge cases."""

    def test_parse_date_none(self) -> None:
        """Verify _parse_date returns None for None input."""
        assert SteamCommunityProvider._parse_date(None) is None

    def test_parse_date_iso(self) -> None:
        """Verify _parse_date handles ISO format."""
        result = SteamCommunityProvider._parse_date("2020-09-23")
        assert result == date(2020, 9, 23)

    def test_parse_date_human_readable(self) -> None:
        """Verify _parse_date handles 'DD Mon YYYY' format."""
        result = SteamCommunityProvider._parse_date("21 Aug 2012")
        assert result == date(2012, 8, 21)

    def test_parse_date_invalid(self) -> None:
        """Verify _parse_date returns None for invalid input."""
        assert SteamCommunityProvider._parse_date("not a date") is None

    def test_extract_reviews_empty(self) -> None:
        """Verify _extract_reviews handles empty ratings."""
        provider = SteamCommunityProvider.__new__(SteamCommunityProvider)
        result = provider._extract_reviews({})
        assert result["score"] is None
        assert result["count"] == 0

    def test_normalize_appdetail_minimal(self) -> None:
        """Verify _normalize_appdetail handles minimal data without KeyError."""
        provider = SteamCommunityProvider.__new__(SteamCommunityProvider)
        minimal = {"name": "Minimal Game"}
        game = provider._normalize_appdetail(minimal, 1)
        assert game.title == "Minimal Game"
        assert game.steam_app_id == 1
        assert game.cover_url is None
        assert len(game.genres) == 0
        assert len(game.developers) == 0


@pytest.mark.unit
class TestSteamEmptyMethods:
    """Tests for SteamCommunityProvider empty default methods."""

    @pytest.mark.asyncio
    async def test_get_free_games_returns_empty(
        self, provider: SteamCommunityProvider,
    ) -> None:
        """Verify get_free_games returns empty ProviderResult."""
        result = await provider.get_free_games()
        assert len(result.games) == 0
        assert len(result.metadata.errors) == 0

    @pytest.mark.asyncio
    async def test_get_deals_returns_empty(
        self, provider: SteamCommunityProvider,
    ) -> None:
        """Verify get_deals returns empty ProviderResult."""
        result = await provider.get_deals()
        assert len(result.deals) == 0
        assert len(result.metadata.errors) == 0


@pytest.mark.unit
class TestSteamHealth:
    """Tests for SteamCommunityProvider.healthcheck()."""

    @pytest.mark.asyncio
    async def test_healthcheck_returns_status(
        self, provider: SteamCommunityProvider,
    ) -> None:
        """Verify healthcheck returns status dict."""
        provider.http_client = AsyncMock(spec=httpx.AsyncClient)
        result = await provider.healthcheck()
        assert "available" in result
        assert "status_code" in result
        assert "response_time_ms" in result
