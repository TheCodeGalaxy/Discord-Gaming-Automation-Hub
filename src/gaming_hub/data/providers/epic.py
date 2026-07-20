"""Epic Games Catalog / Store provider adapter.

- Discover current and upcoming free games via the freeGamesPromotions endpoint.
- Search the Epic Games Store catalog via GraphQL.
- Fetch discounted titles from the promotions feed.
- Normalize Epic products into domain models.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import HttpUrl

from gaming_hub.core.exceptions import ProviderError
from gaming_hub.data.providers.base import BaseHTTPProvider
from gaming_hub.models.domain.deal import Deal
from gaming_hub.models.domain.game import Game
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult
from gaming_hub.utils.http import check_provider_health

if TYPE_CHECKING:
    from gaming_hub.models.dto.request import SearchRequest

EPIC_BASE_URL = "https://store-site-backend-static.ak.epicgames.com"
EPIC_GRAPHQL_URL = "https://store.epicgames.com/graphql"
EPIC_CATALOG_URL = f"{EPIC_BASE_URL}/freeGamesPromotions"
PROMOTIONS_URL = f"{EPIC_BASE_URL}/freeGamesPromotions"
PROMOTIONS_PARAMS = {
    "locale": "en-US",
    "country": "US",
    "allowCountries": "US",
}

logger = logging.getLogger(__name__)


class EpicProvider(BaseHTTPProvider):
    """Adapter for the Epic Games Store."""

    name = "epic"

    def __init__(self, http_client: Any, settings: Any) -> None:
        """Initialize with instance-level URLs derived from settings."""
        super().__init__(http_client, settings)
        base = (settings.epic_base_url or EPIC_BASE_URL).rstrip("/")
        self.promotions_url = f"{base}/freeGamesPromotions"
        self.catalog_url = f"{base}/freeGamesPromotions"
        self.graphql_url = settings.epic_graphql_url or EPIC_GRAPHQL_URL

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        """Parse Epic ISO date string to a ``date`` object."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.rstrip("Z")).date()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        """Parse Epic ISO datetime string to a ``datetime`` object."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.rstrip("Z"))
        except (ValueError, TypeError):
            return None

    def _normalize_free_game(self, elem: dict[str, Any], promo: dict[str, Any]) -> Game:
        """Normalize an Epic promotion element into a Game entity."""
        offer = promo.get("promotionalOffers", [{}])[0] if promo.get("promotionalOffers") else {}
        end_date = offer.get("endDate")

        title = elem.get("title") or elem.get("productName", "Unknown Title")

        cover_url: HttpUrl | None = None
        for img in elem.get("keyImages", []):
            if img.get("type") in ("Thumbnail", "DieselStoreFrontWide", "OfferImageWide"):
                url_str = img.get("url")
                if url_str:
                    cover_url = HttpUrl(url_str)
                break

        catalog_id = elem.get("catalogId") or elem.get("namespace", "")
        provider_url: HttpUrl | None = None
        if catalog_id:
            provider_url = HttpUrl(
                f"https://store.epicgames.com/en-US/p/{catalog_id}",
            )

        namespace = elem.get("namespace")

        return Game(
            id=elem.get("id") or (namespace or ""),
            title=title,
            description=elem.get("description"),
            short_description=elem.get("shortDescription"),
            epic_namespace=namespace,
            cover_url=cover_url,
            release_date=self._parse_date(elem.get("releaseDate")),
            coming_soon_date=self._parse_date(end_date) if promo is not None else None,
            is_free=True,
            free_until=self._parse_date(end_date) if end_date else None,
            genres=[g["name"] for g in elem.get("genres", []) if "name" in g],
            tags=[t["name"] for t in elem.get("tags", []) if "name" in t],
            developers=[elem["developer"]] if elem.get("developer") else [],
            publishers=[elem["publisher"]] if elem.get("publisher") else [],
            provider_name=self.name,
            provider_url=provider_url,
            raw_metadata={
                "namespace": namespace,
                "catalogId": elem.get("catalogId"),
                "offerType": elem.get("offerType"),
            },
        )

    def _normalize_catalog_item(self, elem: dict[str, Any]) -> Game:
        """Normalize an Epic catalog search result into a Game entity."""
        title = elem.get("title") or elem.get("productName", "Unknown Title")

        cover_url: HttpUrl | None = None
        for img in elem.get("keyImages", []):
            if img.get("type") in ("Thumbnail", "DieselStoreFrontWide", "OfferImageWide"):
                url_str = img.get("url")
                if url_str:
                    cover_url = HttpUrl(url_str)
                break

        catalog_id = elem.get("catalogId") or elem.get("namespace", "")
        provider_url: HttpUrl | None = None
        if catalog_id:
            provider_url = HttpUrl(
                f"https://store.epicgames.com/en-US/p/{catalog_id}",
            )

        namespace = elem.get("namespace")

        return Game(
            id=elem.get("id") or (namespace or ""),
            title=title,
            description=elem.get("description"),
            short_description=elem.get("shortDescription"),
            epic_namespace=namespace,
            cover_url=cover_url,
            release_date=self._parse_date(elem.get("releaseDate")),
            genres=[g["name"] for g in elem.get("genres", []) if "name" in g],
            tags=[t["name"] for t in elem.get("tags", []) if "name" in t],
            developers=[elem["developer"]] if elem.get("developer") else [],
            publishers=[elem["publisher"]] if elem.get("publisher") else [],
            provider_name=self.name,
            provider_url=provider_url,
            raw_metadata={
                "namespace": namespace,
                "catalogId": elem.get("catalogId"),
                "offerType": elem.get("offerType"),
            },
        )

    async def get_upcoming_releases(
        self, year: int, month: int, *, limit: int = 20,
    ) -> ProviderResult:
        """Return games from the Epic catalog with release dates in a specific month.

        Fetches the store-backend freeGamesPromotions feed (which returns
        the full catalog of offers) with a large page size and filters by
        the requested year/month. Returns Game objects with release_date,
        cover, genres, developer, and publisher metadata.
        """
        start = time.monotonic()
        try:
            response = await self._get(
                self.promotions_url,
                params={
                    "locale": "en-US",
                    "country": "US",
                    "allowCountries": "US",
                    "count": 500,
                },
            )
            raw = response.json()
            elements = (
                raw.get("data", {})
                .get("Catalog", {})
                .get("searchStore", {})
                .get("elements", [])
            )

            games: list[Game] = []
            skip_no_date = 0
            skip_month = 0
            skip_duplicate = 0
            seen_titles: set[str] = set()

            for elem in elements:
                release_str = elem.get("releaseDate")
                parsed = self._parse_date(release_str)
                if parsed is None:
                    skip_no_date += 1
                    continue
                if parsed.year != year or parsed.month != month:
                    skip_month += 1
                    continue

                title = (elem.get("title") or elem.get("productName") or "").strip()
                if not title:
                    skip_no_date += 1
                    continue
                title_key = title.lower().strip()
                if title_key in seen_titles:
                    skip_duplicate += 1
                    continue
                seen_titles.add(title_key)

                cover_url: HttpUrl | None = None
                for img in elem.get("keyImages", []):
                    if img.get("type") in ("Thumbnail", "DieselStoreFrontWide", "OfferImageWide"):
                        url_str = img.get("url")
                        if url_str:
                            cover_url = HttpUrl(url_str)
                        break

                catalog_id = elem.get("catalogId") or elem.get("namespace", "")
                provider_url: HttpUrl | None = None
                if catalog_id:
                    provider_url = HttpUrl(
                        f"https://store.epicgames.com/en-US/p/{catalog_id}",
                    )

                games.append(
                    Game(
                        id=elem.get("id") or (elem.get("namespace") or ""),
                        title=title,
                        description=elem.get("description"),
                        short_description=elem.get("shortDescription"),
                        epic_namespace=elem.get("namespace"),
                        cover_url=cover_url,
                        release_date=parsed,
                        genres=[g["name"] for g in elem.get("genres", []) if "name" in g],
                        tags=[t["name"] for t in elem.get("tags", []) if "name" in t],
                        developers=[elem["developer"]] if elem.get("developer") else [],
                        publishers=[elem["publisher"]] if elem.get("publisher") else [],
                        provider_name=self.name,
                        provider_url=provider_url,
                        raw_metadata={
                            "namespace": elem.get("namespace"),
                            "catalogId": elem.get("catalogId"),
                            "offerType": elem.get("offerType"),
                        },
                    ),
                )

            games = sorted(games, key=lambda g: g.release_date or date.max)[:limit]
            elapsed = time.monotonic() - start
            logger.info(
                "Epic catalog for %04d-%02d: fetched=%d "
                "no_date=%d wrong_month=%d duplicate=%d valid=%d",
                year, month, len(elements), skip_no_date,
                skip_month, skip_duplicate, len(games),
            )
            return ProviderResult(
                games=games,
                metadata=ProviderMetadata(
                    provider=self.name,
                    returned=len(games),
                    total_available=len(games),
                    response_time_ms=round(elapsed * 1000),
                ),
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.warning(
                "Epic upcoming releases failed for %04d-%02d: %s",
                year, month, exc,
            )
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=self.name,
                    returned=0,
                    response_time_ms=round(elapsed * 1000),
                    errors=[{"error": str(exc)}],
                ),
            )

    async def get_free_games(self, *, upcoming: bool = False) -> ProviderResult:
        """Fetch current or upcoming free games from Epic promotions."""
        start = time.monotonic()
        try:
            response = await self._get(self.promotions_url, params=PROMOTIONS_PARAMS)
            raw = response.json()
            elements = (
                raw.get("data", {})
                .get("Catalog", {})
                .get("searchStore", {})
                .get("elements", [])
            )
            games = []
            for elem in elements:
                promotions = elem.get("promotions") or {}
                if upcoming:
                    promos = promotions.get("upcomingPromotionalOffers", [])
                else:
                    promos = promotions.get("promotionalOffers", [])
                if not promos:
                    continue
                game = self._normalize_free_game(elem, promos[0])
                games.append(game)
            elapsed = time.monotonic() - start
            return ProviderResult(
                games=games,
                metadata=ProviderMetadata(
                    provider=self.name,
                    returned=len(games),
                    total_available=len(games),
                    response_time_ms=round(elapsed * 1000),
                ),
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=self.name,
                    returned=0,
                    response_time_ms=round(elapsed * 1000),
                    errors=[{"error": str(exc)}],
                ),
            )

    async def search(self, request: SearchRequest) -> ProviderResult:
        """Search the Epic Games Store catalog.

        Epic retired the public ``graphql.epicgames.com`` endpoint (returns
        410 Gone) and the store-front GraphQL is Cloudflare-protected, so the
        only supported, key-less catalog source is the static store-backend
        ``freeGamesPromotions`` feed. We reuse that feed and filter its
        ``Catalog.searchStore.elements`` by the requested keyword. If Epic
        fails, we return an empty result so other providers (Steam, etc.)
        can still satisfy the search.
        """
        start = time.monotonic()
        data: dict[str, Any] = {}
        try:
            response = await self._get(self.catalog_url, params=PROMOTIONS_PARAMS)
            data = response.json()

            elements = (
                data.get("data", {})
                .get("Catalog", {})
                .get("searchStore", {})
                .get("elements", [])
            )
            keyword = request.query.lower().strip()
            if keyword:
                filtered = [
                    e
                    for e in elements
                    if keyword in (e.get("title") or e.get("productName") or "").lower()
                ]
            else:
                filtered = elements

            games = [
                self._normalize_catalog_item(e)
                for e in filtered[: request.limit]
            ]
            elapsed = time.monotonic() - start
            return ProviderResult(
                games=games,
                metadata=ProviderMetadata(
                    provider=self.name,
                    query=request.query,
                    total_available=len(games),
                    returned=len(games),
                    response_time_ms=round(elapsed * 1000),
                ),
            )
        except ProviderError as exc:
            elapsed = time.monotonic() - start
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=self.name,
                    query=request.query,
                    returned=0,
                    response_time_ms=round(elapsed * 1000),
                    errors=[{"error": str(exc)}],
                ),
            )
        except (httpx.HTTPStatusError, httpx.HTTPError, ValueError) as exc:
            elapsed = time.monotonic() - start
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=self.name,
                    query=request.query,
                    returned=0,
                    response_time_ms=round(elapsed * 1000),
                    errors=[{"error": str(exc)}],
                ),
            )

    async def get_deals(self, *, limit: int = 10) -> ProviderResult:
        """Fetch discounted titles from the Epic promotions feed."""
        start = time.monotonic()
        try:
            response = await self._get(self.promotions_url, params=PROMOTIONS_PARAMS)
            raw = response.json()
            elements = (
                raw.get("data", {})
                .get("Catalog", {})
                .get("searchStore", {})
                .get("elements", [])
            )

            deals: list[Deal] = []
            for elem in elements:
                if len(deals) >= limit:
                    break
                promotions = elem.get("promotions") or {}
                promos = promotions.get("promotionalOffers", [])
                if not promos:
                    continue
                offer = (
                    promos[0].get("promotionalOffers", [{}])[0]
                    if promos[0].get("promotionalOffers")
                    else {}
                )
                price = elem.get("price", {}).get("totalPrice", {})
                original_price_cents = price.get("originalPrice", 0)
                discount_price_cents = price.get("discountPrice", original_price_cents)

                original_price = original_price_cents / 100.0 if original_price_cents else None
                current_price = discount_price_cents / 100.0

                discount_percent = 0.0
                if original_price_cents and original_price_cents > 0:
                    discount_percent = (
                        (original_price_cents - discount_price_cents)
                        / original_price_cents
                        * 100
                    )

                deal = Deal(
                    id=elem.get("id") or "",
                    title=elem.get("title") or elem.get("productName", "Unknown Title"),
                    current_price=current_price,
                    original_price=original_price,
                    discount_percent=round(discount_percent, 2),
                    is_free=current_price == 0,
                    deal_started_at=self._parse_datetime(offer.get("startDate")),
                    deal_ends_at=self._parse_datetime(offer.get("endDate")),
                    provider_names=[self.name],
                )
                deals.append(deal)

            elapsed = time.monotonic() - start
            return ProviderResult(
                deals=deals,
                metadata=ProviderMetadata(
                    provider=self.name,
                    returned=len(deals),
                    total_available=len(deals),
                    response_time_ms=round(elapsed * 1000),
                ),
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=self.name,
                    returned=0,
                    response_time_ms=round(elapsed * 1000),
                    errors=[{"error": str(exc)}],
                ),
            )

    async def healthcheck(self) -> dict[str, Any]:
        """Verify Epic Games promotions endpoint is reachable."""
        return await check_provider_health(
            self.http_client,
            f"{self.promotions_url}?locale=en-US",
        )
