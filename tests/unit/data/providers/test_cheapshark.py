"""Unit tests for CheapSharkProvider."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import HttpUrl

from gaming_hub.core.enums import StoreName
from gaming_hub.data.providers.cheapshark import STORE_ID_MAP, CheapSharkProvider
from gaming_hub.models.dto.request import SearchRequest

FIXTURES = Path(__file__).parents[3] / "fixtures" / "cheapshark"


@pytest.fixture()
def mock_client() -> AsyncMock:
    """Return a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture()
def provider(mock_client: AsyncMock, settings) -> CheapSharkProvider:
    """Return a CheapSharkProvider with mocked HTTP client."""
    return CheapSharkProvider(http_client=mock_client, settings=settings)


@pytest.fixture()
def mock_response() -> MagicMock:
    """Return a mock httpx.Response with .json() returning fixture data."""
    response = MagicMock(spec=httpx.Response)
    response.json.return_value = []
    return response


def _load_fixture(name: str) -> list[dict]:
    """Load a CheapShark JSON fixture file."""
    path = FIXTURES / name
    with path.open() as f:
        return json.load(f)


@pytest.mark.unit
class TestCheapSharkSearch:
    """Tests for CheapSharkProvider.search()."""

    @pytest.mark.asyncio
    async def test_search_returns_games(
        self, provider: CheapSharkProvider,
    ) -> None:
        """Verify search returns Game objects with correct fields."""
        data = _load_fixture("games_search.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        request = SearchRequest(query="cyberpunk", limit=10)
        result = await provider.search(request)

        assert len(result.games) == 2  # noqa: PLR2004
        assert result.metadata.returned == 2  # noqa: PLR2004
        assert result.metadata.query == "cyberpunk"

        game = result.games[0]
        assert game.id == "612"
        assert game.title == "Cyberpunk 2077"
        assert game.steam_app_id == 1091500  # noqa: PLR2004
        assert game.cover_url == HttpUrl("https://cdn.cheapshark.com/thumb/cyberpunk.jpg")
        assert game.provider_name == "cheapshark"

    @pytest.mark.asyncio
    async def test_search_no_steam_app_id(
        self, provider: CheapSharkProvider,
    ) -> None:
        """Verify search handles missing steamAppID gracefully."""
        data = _load_fixture("games_search.json")
        data[1].pop("steamAppID")
        mock_resp = MagicMock()
        mock_resp.json.return_value = [data[1]]
        provider._get = AsyncMock(return_value=mock_resp)

        request = SearchRequest(query="phantom")
        result = await provider.search(request)

        assert len(result.games) == 1
        assert result.games[0].steam_app_id is None

    @pytest.mark.asyncio
    async def test_search_with_exact(
        self, provider: CheapSharkProvider,
    ) -> None:
        """Verify exact=1 is sent when request.exact is True."""
        data = _load_fixture("games_search.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data[:1]
        provider._get = AsyncMock(return_value=mock_resp)

        request = SearchRequest(query="Cyberpunk 2077", exact=True)
        await provider.search(request)

        provider._get.assert_awaited_once()
        _call_params = provider._get.call_args[1]["params"]
        assert _call_params["exact"] == "1"

    @pytest.mark.asyncio
    async def test_search_returns_provider_result_on_error(
        self, provider: CheapSharkProvider,
    ) -> None:
        """Verify search returns ProviderResult with errors on exception."""
        provider._get = AsyncMock(side_effect=httpx.ConnectError("connection failed"))

        request = SearchRequest(query="cyberpunk")
        result = await provider.search(request)

        assert len(result.games) == 0
        assert len(result.metadata.errors) == 1
        assert "connection failed" in result.metadata.errors[0]["error"]

    @pytest.mark.asyncio
    async def test_search_passes_params_correctly(
        self, provider: CheapSharkProvider,
    ) -> None:
        """Verify search sends the correct query params."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        provider._get = AsyncMock(return_value=mock_resp)

        request = SearchRequest(query="hades", limit=5)
        await provider.search(request)

        provider._get.assert_awaited_once()
        call_kwargs = provider._get.call_args[1]
        assert call_kwargs["params"]["title"] == "hades"
        assert call_kwargs["params"]["limit"] == 5  # noqa: PLR2004


@pytest.mark.unit
class TestCheapSharkDeals:
    """Tests for CheapSharkProvider.get_deals()."""

    @pytest.mark.asyncio
    async def test_get_deals_returns_deals(
        self, provider: CheapSharkProvider,
    ) -> None:
        """Verify get_deals returns Deal objects with correct pricing."""
        data = _load_fixture("deals.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        result = await provider.get_deals(limit=3)

        assert len(result.deals) == 3  # noqa: PLR2004
        assert result.metadata.returned == 3  # noqa: PLR2004

        hades = result.deals[0]
        assert hades.title == "Hades"
        assert hades.current_price == 12.49  # noqa: PLR2004
        assert hades.original_price == 24.99  # noqa: PLR2004
        assert hades.discount_percent == 50.02  # noqa: PLR2004
        assert hades.store == StoreName.Steam
        assert hades.is_free is False

    @pytest.mark.asyncio
    async def test_get_deals_discount_non_negative(
        self, provider: CheapSharkProvider,
    ) -> None:
        """Verify all deals have discount_percent >= 0."""
        data = _load_fixture("deals.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        result = await provider.get_deals(limit=3)

        for deal in result.deals:
            assert deal.discount_percent >= 0

    @pytest.mark.asyncio
    async def test_get_deals_returns_error_on_failure(
        self, provider: CheapSharkProvider,
    ) -> None:
        """Verify get_deals returns ProviderResult with errors on exception."""
        provider._get = AsyncMock(side_effect=httpx.ConnectError("down"))

        result = await provider.get_deals()

        assert len(result.deals) == 0
        assert len(result.metadata.errors) == 1


@pytest.mark.unit
class TestCheapSharkFreeGames:
    """Tests for CheapSharkProvider.get_free_games()."""

    @pytest.mark.asyncio
    async def test_get_free_games_returns_only_free(
        self, provider: CheapSharkProvider,
    ) -> None:
        """Verify get_free_games returns only deals where is_free is True."""
        data = _load_fixture("deals.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        result = await provider.get_free_games()

        assert len(result.deals) == 1
        assert result.deals[0].is_free is True
        assert result.deals[0].current_price == 0

    @pytest.mark.asyncio
    async def test_get_free_games_empty_when_no_free(
        self, provider: CheapSharkProvider,
    ) -> None:
        """Verify get_free_games returns empty when no free deals."""
        data = _load_fixture("deals.json")
        data = [d for d in data if float(d.get("salePrice", "1")) != 0]
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        result = await provider.get_free_games()

        assert len(result.deals) == 0


@pytest.mark.unit
class TestCheapSharkStoreResolution:
    """Tests for CheapSharkProvider._resolve_store()."""

    def test_known_store_ids_map_correctly(self) -> None:
        """Verify known store IDs map to the correct StoreName."""
        provider = CheapSharkProvider.__new__(CheapSharkProvider)
        assert provider._resolve_store(1) == StoreName.Steam
        assert provider._resolve_store(3) == StoreName.Epic
        assert provider._resolve_store(4) == StoreName.GOG
        assert provider._resolve_store(5) == StoreName.GreenManGaming

    def test_unknown_store_id_returns_unknown(self) -> None:
        """Verify unknown store ID maps to StoreName.Unknown."""
        provider = CheapSharkProvider.__new__(CheapSharkProvider)
        assert provider._resolve_store(999) == StoreName.Unknown

    def test_store_id_map_has_known_ids(self) -> None:
        """Verify STORE_ID_MAP covers the IDs used in the roadmap."""
        assert 1 in STORE_ID_MAP
        assert 3 in STORE_ID_MAP  # noqa: PLR2004
        assert 4 in STORE_ID_MAP  # noqa: PLR2004
        assert 5 in STORE_ID_MAP  # noqa: PLR2004
        assert 7 in STORE_ID_MAP  # noqa: PLR2004
        assert 8 in STORE_ID_MAP  # noqa: PLR2004


@pytest.mark.unit
class TestCheapSharkNormalization:
    """Tests for CheapSharkProvider normalization edge cases."""

    def test_normalize_search_missing_thumb(self) -> None:
        """Verify _normalize_search_result handles missing thumb."""
        provider = CheapSharkProvider.__new__(CheapSharkProvider)
        item = {"gameID": "1", "external": "Test Game", "cheapest": "0"}
        game = provider._normalize_search_result(item)
        assert game.cover_url is None
        assert game.id == "1"
        assert game.title == "Test Game"

    def test_normalize_search_missing_deal_id(self) -> None:
        """Verify _normalize_search_result handles missing cheapestDealID."""
        provider = CheapSharkProvider.__new__(CheapSharkProvider)
        item = {"gameID": "2", "external": "No Deal", "thumb": "https://example.com/img.jpg"}
        game = provider._normalize_search_result(item)
        assert game.provider_url is None

    def test_normalize_deal_missing_normal_price(self) -> None:
        """Verify _normalize_deal handles missing normalPrice."""
        provider = CheapSharkProvider.__new__(CheapSharkProvider)
        item = {
            "dealID": "deal1",
            "title": "No Normal Price",
            "salePrice": "9.99",
            "storeID": "1",
            "savings": "0",
        }
        deal = provider._normalize_deal(item)
        assert deal.original_price is None
        assert deal.current_price == 9.99  # noqa: PLR2004

    def test_normalize_deal_epic_store(self) -> None:
        """Verify _normalize_deal maps storeID=3 to Epic."""
        provider = CheapSharkProvider.__new__(CheapSharkProvider)
        item = {
            "dealID": "deal2",
            "title": "Epic Deal",
            "salePrice": "0",
            "storeID": "3",
            "savings": "100",
        }
        deal = provider._normalize_deal(item)
        assert deal.store == StoreName.Epic
        assert deal.is_free is True


@pytest.mark.unit
class TestCheapSharkHealth:
    """Tests for CheapSharkProvider.healthcheck()."""

    @pytest.mark.asyncio
    async def test_healthcheck_calls_check_provider_health(
        self, provider: CheapSharkProvider,
    ) -> None:
        """Verify healthcheck delegates to check_provider_health."""
        provider.http_client = AsyncMock(spec=httpx.AsyncClient)
        result = await provider.healthcheck()
        assert "available" in result
        assert "status_code" in result
        assert "response_time_ms" in result
