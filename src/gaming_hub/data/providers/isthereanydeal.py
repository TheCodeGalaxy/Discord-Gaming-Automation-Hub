"""IsThereAnyDeal provider adapter.

Queries IsThereAnyDeal (ITAD) for game search, price comparison,
deal listings, and historical low prices.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, ClassVar

import httpx
from pydantic import HttpUrl

from gaming_hub.core.enums import StoreName
from gaming_hub.data.providers.base import BaseHTTPProvider
from gaming_hub.models.domain.deal import Deal
from gaming_hub.models.domain.game import Game
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult

if TYPE_CHECKING:
    from gaming_hub.models.dto.request import SearchRequest

logger = logging.getLogger(__name__)

ITAD_BASE_URL = "https://api.isthereanydeal.com"
SEARCH_URL = f"{ITAD_BASE_URL}/v01/search/games"
DEAL_LIST_URL = f"{ITAD_BASE_URL}/v01/deal/list"
LOWEST_URL = f"{ITAD_BASE_URL}/v02/deal/lowest"

ITAD_SHOP_MAP: dict[str, StoreName] = {
    "Steam": StoreName.Steam,
    "Epic Games Store": StoreName.Epic,
    "GOG": StoreName.GOG,
    "Humble Store": StoreName.Humble,
    "Origin": StoreName.Origin,
    "Microsoft Store": StoreName.Microsoft,
    "Ubisoft Connect": StoreName.Ubisoft,
}


class IsThereAnyDealProvider(BaseHTTPProvider):
    """Adapter for the IsThereAnyDeal API."""

    name = "isthereanydeal"

    _shop_map: ClassVar[dict[str, StoreName]] = ITAD_SHOP_MAP

    def __init__(self, http_client: Any, settings: Any) -> None:
        """Initialize provider with instance URLs and optional API key logging."""
        super().__init__(http_client, settings)
        base = (settings.isthereanydeal_base_url or ITAD_BASE_URL).rstrip("/")
        self.search_url = f"{base}/v01/search/games"
        self.deal_list_url = f"{base}/v01/deal/list"
        self.lowest_url = f"{base}/v02/deal/lowest"
        if not self.api_key:
            logger.debug("ITAD API key not configured — operating in anonymous mode")

    @property
    def api_key(self) -> str | None:
        """Return the ITAD API key or None for anonymous mode."""
        return self.settings.isthereanydeal_api_key or None

    def _resolve_store(self, shop_name: str) -> StoreName:
        """Map ITAD shop name strings to StoreName enum values."""
        return self._shop_map.get(shop_name, StoreName.Unknown)

    def _normalize_search_result(self, item: dict[str, Any]) -> Game:
        """Normalize an ITAD /v01/search/games result into a Game entity."""
        cover_url: HttpUrl | None = None
        image = item.get("image")
        if image:
            cover_url = HttpUrl(image)

        release_date: date | None = None
        raw_date = item.get("release_date")
        if raw_date:
            with contextlib.suppress(ValueError, TypeError):
                release_date = datetime.fromisoformat(raw_date).date()

        plain_id = item.get("id", "")
        provider_url = HttpUrl(
            f"https://isthereanydeal.com/game/{plain_id}/info/",
        )

        return Game(
            id=plain_id,
            title=item.get("title", "Unknown"),
            steam_app_id=item.get("steam_app_id"),
            cover_url=cover_url,
            release_date=release_date,
            provider_name=self.name,
            provider_url=provider_url,
            raw_metadata={
                "itad_plain_id": plain_id,
                "match_grade": item.get("match"),
            },
        )

    def _normalize_deal(self, item: dict[str, Any], plain_id: str) -> Deal:
        """Normalize an ITAD /v01/deal/list item into a Deal entity."""
        price_data = item.get("price", {})
        shop = item.get("shop", {})

        store_url: HttpUrl | None = None
        url_str = item.get("url")
        if url_str:
            store_url = HttpUrl(url_str)

        regular = price_data.get("regular")
        original_price = regular.get("amount", 0.0) if isinstance(regular, dict) else None

        current_price = price_data.get("amount", 0.0)

        return Deal(
            id=item.get("id", f"{plain_id}-{shop.get('id', '0')}"),
            title=item.get("id", ""),
            current_price=current_price,
            original_price=original_price,
            discount_percent=price_data.get("cut", 0.0),
            store=self._resolve_store(shop.get("name", "")),
            store_url=store_url,
            is_free=current_price == 0,
            provider_names=[self.name],
            raw_metadata={"itad_plain_id": plain_id},
        )

    def _get_known_game_ids(self, limit: int) -> list[str]:
        """Return known ITAD plain IDs for deal polling.

        For v1, uses a small hard-coded set of popular game plain IDs.
        A future phase may maintain this list in a database or cache.
        """
        known = [
            "cyberpunk2077",
            "hades",
            "baldursgate3",
            "eldenring",
            "hogwartslegacy",
            "stardewvalley",
            "reddeadredemption2",
            "thewitcher3",
            "godofwar",
            "spidermanremastered",
        ]
        return known[:limit]

    async def search(self, request: SearchRequest) -> ProviderResult:
        """Search games via ITAD API.

        Note: The ITAD v01/v02/v03 public APIs have been decommissioned.
        Search returns empty with a logged informational message.
        """
        logger.info("ITAD search unavailable: API v01/v02/v03 decommissioned")
        return ProviderResult(
            metadata=ProviderMetadata(
                provider=self.name,
                query=request.query,
                returned=0,
            ),
        )

    async def get_deals(self, *, limit: int = 20) -> ProviderResult:
        """Fetch current deals from ITAD.

        Note: The ITAD v01/v02/v03 deal/list endpoints have been
        decommissioned. Returns empty with a logged informational message.
        """
        logger.info("ITAD deals unavailable: API v01/v02/v03 decommissioned")
        return ProviderResult(
            metadata=ProviderMetadata(
                provider=self.name,
                returned=0,
            ),
        )

    async def get_free_games(self, *, upcoming: bool = False) -> ProviderResult:
        """Detect free-to-claim games from ITAD deal data.

        Note: ITAD deal API is decommissioned; returns empty.
        """
        _ = upcoming
        return ProviderResult(
            metadata=ProviderMetadata(
                provider=self.name,
                returned=0,
            ),
        )

    async def get_lowest_price(self, plain_id: str) -> dict[str, Any] | None:
        """Fetch historical lowest price via ITAD /v02/deal/lowest.

        Returns the lowest recorded price dict, or None when no data is
        available for the given plain ID. Unexpected errors are logged.
        """
        try:
            params: dict[str, Any] = {"id": plain_id}
            if self.api_key:
                params["key"] = self.api_key
            response = await self._get(self.lowest_url, params=params)
            data = response.json()
            lowest = data.get("data", {}).get("lowest")
            if not lowest:
                logger.debug("No lowest price data for %s", plain_id)
                return None
            return {
                "plain_id": plain_id,
                "lowest_price": lowest.get("amount"),
                "lowest_recorded_date": lowest.get("date"),
                "shop_name": lowest.get("shop", {}).get("name"),
            }
        except httpx.HTTPStatusError:
            logger.warning("HTTP error fetching lowest price for %s", plain_id)
            return None
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            logger.warning("Network error fetching lowest price for %s: %s", plain_id, exc)
            return None
        except Exception as exc:
            logger.error("Unexpected error fetching lowest price for %s: %s", plain_id, exc)
            return None

    async def healthcheck(self) -> dict[str, Any]:
        """Report ITAD API status (decommissioned — always unavailable)."""
        return {"available": False, "status_code": 410, "error": "ITAD API decommissioned"}
