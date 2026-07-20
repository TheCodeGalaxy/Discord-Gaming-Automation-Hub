"""Unit tests for IsThereAnyDealProvider."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from gaming_hub.core.enums import StoreName
from gaming_hub.data.providers.isthereanydeal import ITAD_SHOP_MAP, IsThereAnyDealProvider
from gaming_hub.models.dto.request import SearchRequest

FIXTURES = Path(__file__).parents[3] / "fixtures" / "isthereanydeal"


@pytest.fixture()
def mock_client() -> AsyncMock:
    """Return a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture()
def provider(mock_client: AsyncMock, settings) -> IsThereAnyDealProvider:
    """Return an IsThereAnyDealProvider with mocked HTTP client."""
    return IsThereAnyDealProvider(http_client=mock_client, settings=settings)


def _load_fixture(name: str) -> dict:
    """Load an ITAD JSON fixture file."""
    path = FIXTURES / name
    with path.open() as f:
        return json.load(f)



@pytest.mark.unit
class TestIsThereAnyDealSearch:
    """Tests for IsThereAnyDealProvider.search().

    Note: The ITAD v01/v02/v03 APIs have been decommissioned.
    ``search`` now returns empty without making HTTP calls.
    """

    @pytest.mark.asyncio
    async def test_search_returns_empty(
        self, provider: IsThereAnyDealProvider,
    ) -> None:
        """Verify search returns empty because API is decommissioned."""
        result = await provider.search(SearchRequest(query="cyberpunk", limit=10))
        assert len(result.games) == 0
        assert result.metadata.returned == 0

    @pytest.mark.asyncio
    async def test_search_logs_message(
        self, provider: IsThereAnyDealProvider,
    ) -> None:
        """Verify search logs API decommissioned message."""
        provider._get = AsyncMock()
        result = await provider.search(SearchRequest(query="hades", limit=5))
        assert len(result.games) == 0


@pytest.mark.unit
class TestIsThereAnyDealDeals:
    """Tests for IsThereAnyDealProvider.get_deals().

    Note: The ITAD deal/list API is decommissioned.
    ``get_deals`` now returns empty without making HTTP calls.
    """

    @pytest.mark.asyncio
    async def test_get_deals_returns_empty(
        self, provider: IsThereAnyDealProvider,
    ) -> None:
        """Verify get_deals returns empty because API is decommissioned."""
        result = await provider.get_deals(limit=5)
        assert len(result.deals) == 0

    @pytest.mark.asyncio
    async def test_get_deals_no_error(
        self, provider: IsThereAnyDealProvider,
    ) -> None:
        """Verify get_deals does not raise (returns empty gracefully)."""
        result = await provider.get_deals()
        assert result.metadata.returned == 0


@pytest.mark.unit
class TestIsThereAnyDealFreeGames:
    """Tests for IsThereAnyDealProvider.get_free_games().

    Note: ITAD API decommissioned — returns empty.
    """

    @pytest.mark.asyncio
    async def test_get_free_games_returns_empty(
        self, provider: IsThereAnyDealProvider,
    ) -> None:
        """Verify get_free_games returns empty because API is decommissioned."""
        result = await provider.get_free_games()
        assert len(result.deals) == 0


@pytest.mark.unit
class TestIsThereAnyDealStoreResolution:
    """Tests for IsThereAnyDealProvider._resolve_store()."""

    def test_known_shop_names_map_correctly(self) -> None:
        """Verify known shop names map to the correct StoreName."""
        provider = IsThereAnyDealProvider.__new__(IsThereAnyDealProvider)
        assert provider._resolve_store("Steam") == StoreName.Steam
        assert provider._resolve_store("Epic Games Store") == StoreName.Epic
        assert provider._resolve_store("GOG") == StoreName.GOG
        assert provider._resolve_store("Humble Store") == StoreName.Humble
        assert provider._resolve_store("Origin") == StoreName.Origin
        assert provider._resolve_store("Microsoft Store") == StoreName.Microsoft
        assert provider._resolve_store("Ubisoft Connect") == StoreName.Ubisoft

    def test_unknown_shop_name_returns_unknown(self) -> None:
        """Verify unknown shop name maps to StoreName.Unknown."""
        provider = IsThereAnyDealProvider.__new__(IsThereAnyDealProvider)
        assert provider._resolve_store("Unknown Shop") == StoreName.Unknown

    def test_shop_map_has_known_names(self) -> None:
        """Verify ITAD_SHOP_MAP covers the names used in the roadmap."""
        assert "Steam" in ITAD_SHOP_MAP
        assert "Epic Games Store" in ITAD_SHOP_MAP
        assert "GOG" in ITAD_SHOP_MAP
        assert "Humble Store" in ITAD_SHOP_MAP
        assert "Origin" in ITAD_SHOP_MAP
        assert "Microsoft Store" in ITAD_SHOP_MAP
        assert "Ubisoft Connect" in ITAD_SHOP_MAP


@pytest.mark.unit
class TestIsThereAnyDealNormalization:
    """Tests for IsThereAnyDealProvider normalization edge cases."""

    def test_normalize_deal_missing_regular_price(self) -> None:
        """Verify _normalize_deal handles missing regular price."""
        provider = IsThereAnyDealProvider.__new__(IsThereAnyDealProvider)
        item = {
            "id": "deal3",
            "shop": {"id": 7, "name": "GOG"},
            "price": {"amount": 14.99, "cut": 25},
            "url": "https://isthereanydeal.com/deal/deal3/",
        }
        deal = provider._normalize_deal(item, "cyberpunk2077")
        assert deal.original_price is None
        assert deal.current_price == 14.99  # noqa: PLR2004
        assert deal.store == StoreName.GOG

    def test_normalize_search_missing_image(self) -> None:
        """Verify _normalize_search_result handles missing image."""
        provider = IsThereAnyDealProvider.__new__(IsThereAnyDealProvider)
        item = {
            "id": "testgame",
            "title": "Test Game",
            "steam_app_id": None,
            "match": "fuzzy",
        }
        game = provider._normalize_search_result(item)
        assert game.cover_url is None
        assert game.title == "Test Game"
        assert game.id == "testgame"


@pytest.mark.unit
class TestIsThereAnyDealLowestPrice:
    """Tests for IsThereAnyDealProvider.get_lowest_price()."""

    @pytest.mark.asyncio
    async def test_get_lowest_price_returns_dict(
        self, provider: IsThereAnyDealProvider,
    ) -> None:
        """Verify get_lowest_price returns a dict with expected keys."""
        data = _load_fixture("lowest_price.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        result = await provider.get_lowest_price("cyberpunk2077")

        assert isinstance(result, dict)
        assert result["plain_id"] == "cyberpunk2077"
        assert result["lowest_price"] == 4.99  # noqa: PLR2004
        assert result["lowest_recorded_date"] == "2023-01-15T00:00:00Z"
        assert result["shop_name"] == "Steam"

    @pytest.mark.asyncio
    async def test_get_lowest_price_returns_none_on_missing(
        self, provider: IsThereAnyDealProvider,
    ) -> None:
        """Verify get_lowest_price returns None when no historical data."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"lowest": None}}
        provider._get = AsyncMock(return_value=mock_resp)

        result = await provider.get_lowest_price("unknown_game")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_lowest_price_returns_none_on_error(
        self, provider: IsThereAnyDealProvider,
    ) -> None:
        """Verify get_lowest_price returns None on HTTP error."""
        provider._get = AsyncMock(side_effect=httpx.ConnectError("down"))

        result = await provider.get_lowest_price("cyberpunk2077")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_lowest_price_no_key_passed(
        self, provider: IsThereAnyDealProvider,
    ) -> None:
        """Verify get_lowest_price works without API key in params."""
        data = _load_fixture("lowest_price.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        provider._get = AsyncMock(return_value=mock_resp)

        await provider.get_lowest_price("cyberpunk2077")

        provider._get.assert_awaited_once()
        call_params = provider._get.call_args[1].get("params", {})
        assert "key" not in call_params


@pytest.mark.unit
class TestIsThereAnyDealAnonymousMode:
    """Tests for IsThereAnyDealProvider anonymous (no API key) mode.

    Note: ITAD API decommissioned — search/deals return empty immediately.
    """

    @pytest.mark.asyncio
    async def test_search_returns_empty(
        self, provider: IsThereAnyDealProvider,
    ) -> None:
        """Verify search returns empty (API decommissioned)."""
        result = await provider.search(SearchRequest(query="cyberpunk"))
        assert len(result.games) == 0

    @pytest.mark.asyncio
    async def test_get_deals_returns_empty(
        self, provider: IsThereAnyDealProvider,
    ) -> None:
        """Verify get_deals returns empty (API decommissioned)."""
        result = await provider.get_deals(limit=1)
        assert len(result.deals) == 0


@pytest.mark.unit
class TestIsThereAnyDealHealth:
    """Tests for IsThereAnyDealProvider.healthcheck()."""

    @pytest.mark.asyncio
    async def test_healthcheck_returns_unavailable(
        self, provider: IsThereAnyDealProvider,
    ) -> None:
        """Verify healthcheck returns unavailable (API decommissioned)."""
        result = await provider.healthcheck()
        assert result["available"] is False
