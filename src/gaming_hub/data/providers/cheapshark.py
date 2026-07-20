"""CheapShark provider adapter.

Docs: https://www.cheapshark.com/api/1.0/

- Search games by title.
- Fetch current deals.
- Map Steam App IDs to CheapShark game IDs.
- Normalize payloads into domain models.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import HttpUrl

from gaming_hub.core.enums import StoreName
from gaming_hub.data.providers.base import BaseHTTPProvider
from gaming_hub.models.domain.deal import Deal
from gaming_hub.models.domain.game import Game
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult
from gaming_hub.utils.http import check_provider_health

if TYPE_CHECKING:
    from gaming_hub.models.dto.request import SearchRequest

BASE_URL = "https://www.cheapshark.com/api/1.0"
LOOKUP_URL = f"{BASE_URL}/games"
DEALS_URL = f"{BASE_URL}/deals"

STORE_ID_MAP: dict[int, StoreName] = {
    1: StoreName.Steam,
    3: StoreName.Epic,
    4: StoreName.GOG,
    5: StoreName.GreenManGaming,
    7: StoreName.Fanatical,
    8: StoreName.Humble,
    13: StoreName.Itch,
}


class CheapSharkProvider(BaseHTTPProvider):
    """Adapter for the CheapShark game-deals API."""

    name = "cheapshark"

    _store_id_map: ClassVar[dict[int, StoreName]] = STORE_ID_MAP

    def __init__(self, http_client: Any, settings: Any) -> None:
        """Initialize with instance-level URLs derived from settings."""
        super().__init__(http_client, settings)
        base = (settings.cheapshark_base_url or BASE_URL).rstrip("/")
        self.lookup_url = f"{base}/games"
        self.deals_url = f"{base}/deals"

    def _resolve_store(self, store_id: int) -> StoreName:
        """Map CheapShark integer store IDs to StoreName enum."""
        return self._store_id_map.get(store_id, StoreName.Unknown)

    def _normalize_search_result(self, item: dict[str, Any]) -> Game:
        """Normalize a CheapShark /games response item into a Game entity."""
        steam_app_id: int | None = None
        raw = item.get("steamAppID")
        if raw:
            with contextlib.suppress(ValueError, TypeError):
                steam_app_id = int(raw)

        cover_url: HttpUrl | None = None
        thumb = item.get("thumb")
        if thumb:
            cover_url = HttpUrl(thumb)

        provider_url: HttpUrl | None = None
        cheapest_deal_id = item.get("cheapestDealID")
        if cheapest_deal_id:
            provider_url = HttpUrl(
                f"https://www.cheapshark.com/redirect?dealID={cheapest_deal_id}",
            )

        return Game(
            id=str(item["gameID"]),
            title=item["external"],
            steam_app_id=steam_app_id,
            cover_url=cover_url,
            provider_name=self.name,
            provider_url=provider_url,
            raw_metadata={
                "cheapshark_id": item["gameID"],
                "cheapest_price": item.get("cheapest"),
            },
        )

    def _normalize_deal(self, item: dict[str, Any]) -> Deal:
        """Normalize a CheapShark /deals response item into a Deal entity."""
        deal_id = str(item["dealID"])
        store_url = HttpUrl(
            f"https://www.cheapshark.com/redirect?dealID={deal_id}",
        )

        sale_price = float(item.get("salePrice", "0"))
        normal_price_str = item.get("normalPrice")

        steam_app_id_raw = item.get("steamAppID")
        steam_app_id = int(steam_app_id_raw) if steam_app_id_raw else None

        return Deal(
            id=deal_id,
            title=item["title"],
            store=self._resolve_store(int(item.get("storeID", 0))),
            store_url=store_url,
            current_price=sale_price,
            original_price=float(normal_price_str) if normal_price_str else None,
            discount_percent=float(item.get("savings", "0")),
            is_free=sale_price == 0,
            provider_names=[self.name],
            raw_metadata={
                "cheapshark_deal_id": deal_id,
                "steam_app_id": steam_app_id,
            },
        )

    async def search(self, request: SearchRequest) -> ProviderResult:
        """Search games by title via CheapShark /games endpoint."""
        start = time.monotonic()
        try:
            params: dict[str, Any] = {
                "title": request.query,
                "limit": min(request.limit, 60),
            }
            if request.exact:
                params["exact"] = "1"
            response = await self._get(self.lookup_url, params=params)
            data = response.json()
            games = [self._normalize_search_result(item) for item in data]
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
        except Exception as exc:
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
        """Fetch current deals from CheapShark /deals endpoint."""
        start = time.monotonic()
        try:
            params: dict[str, Any] = {
                "pageSize": min(limit, 60),
                "sortBy": "Savings",
            }
            response = await self._get(self.deals_url, params=params)
            data = response.json()
            deals = [self._normalize_deal(item) for item in data]
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

    async def get_free_games(self, *, upcoming: bool = False) -> ProviderResult:
        """Identify free-to-claim games from CheapShark deal data.

        CheapShark has no dedicated free endpoint; free games appear as
        deals with ``salePrice=0``. The ``upcoming`` parameter is accepted
        for interface compatibility but ignored.
        """
        _ = upcoming
        result = await self.get_deals(limit=60)
        free_deals = [d for d in result.deals if d.is_free]
        start = time.monotonic()
        try:
            elapsed = time.monotonic() - start
            return ProviderResult(
                deals=free_deals,
                metadata=ProviderMetadata(
                    provider=self.name,
                    returned=len(free_deals),
                    total_available=len(free_deals),
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

    async def get_new_releases(self, *, days_ahead: int = 365, limit: int = 20) -> ProviderResult:
        """Fetch recently-added deals from CheapShark as new-release suggestions.

        CheapShark's ``/deals`` endpoint includes ``releaseDate`` on each
        deal. We fetch deals sorted by two sort orders (Recent and Savings)
        to maximise the candidate pool, parse the release date, and return
        games with a non-zero release date within the past *days_ahead*
        days, sorted newest first.
        """
        start = time.monotonic()
        try:
            today = date.today()
            all_deals: list[dict[str, Any]] = []
            for sort_by in ("Recent", "Savings"):
                for page in range(5):
                    resp = await self._get(
                        self.deals_url,
                        params={"pageSize": 60, "sortBy": sort_by, "pageNumber": page},
                    )
                    chunk = resp.json()
                    if not isinstance(chunk, list) or not chunk:
                        break
                    all_deals.extend(chunk)
                    await asyncio.sleep(2.0)

            games: list[Game] = []
            seen_titles: set[str] = set()
            deferred: list[Game] = []
            for item in all_deals:
                raw_release = item.get("releaseDate")
                if not raw_release or int(raw_release) == 0:
                    steam_app_id_raw = item.get("steamAppID")
                    steam_app_id = int(steam_app_id_raw) if steam_app_id_raw else None
                    if steam_app_id:
                        title = item.get("title", "Unknown")
                        title_key = title.lower().strip()
                        if title_key not in seen_titles:
                            seen_titles.add(title_key)
                            cover_url: HttpUrl | None = None
                            thumb = item.get("thumb")
                            if thumb:
                                cover_url = HttpUrl(thumb)
                            deferred.append(
                                Game(
                                    id=str(item.get("dealID", "")),
                                    title=title,
                                    steam_app_id=steam_app_id,
                                    cover_url=cover_url,
                                    release_date=None,
                                    provider_name=self.name,
                                ),
                            )
                    continue
                try:
                    raw_ts = int(raw_release)
                    release = datetime.fromtimestamp(raw_ts, tz=UTC).date()
                except (ValueError, TypeError, OSError):
                    continue
                if not (today - timedelta(days=days_ahead) <= release <= today):
                    continue
                title = item.get("title", "Unknown")
                title_key = title.lower().strip()
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)
                steam_app_id_raw = item.get("steamAppID")
                steam_app_id = int(steam_app_id_raw) if steam_app_id_raw else None
                cover_url = None
                thumb = item.get("thumb")
                if thumb:
                    cover_url = HttpUrl(thumb)
                games.append(
                    Game(
                        id=str(item.get("dealID", "")),
                        title=title,
                        steam_app_id=steam_app_id,
                        cover_url=cover_url,
                        release_date=release,
                        provider_name=self.name,
                    ),
                )
            games.extend(deferred)
            games = sorted(games, key=lambda g: g.release_date or date.min, reverse=True)[:limit]
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

    async def get_monthly_releases(
        self,
        year: int,
        month: int,
        *,
        limit: int = 10,
    ) -> ProviderResult:
        """Return games with release dates in a specific calendar month.

        Fetches deals sorted by two sort orders (Recent and Savings) to
        maximise the candidate pool while keeping total pages manageable.
        Merges results, deduplicates by Steam App ID, and returns at most
        *limit* games sorted by release date ascending.
        """
        start = time.monotonic()
        logger = logging.getLogger(__name__)
        try:
            all_deals: list[dict[str, Any]] = []
            for sort_by in ("Recent", "Savings"):
                for page in range(5):
                    try:
                        resp = await self._get(
                            self.deals_url,
                            params={"pageSize": 60, "sortBy": sort_by, "pageNumber": page},
                        )
                        chunk = resp.json()
                        if not isinstance(chunk, list) or not chunk:
                            break
                        all_deals.extend(chunk)
                        await asyncio.sleep(2.0)
                    except Exception:
                        break

            seen_ids: set[int] = set()
            games: list[Game] = []
            total_fetched = len(all_deals)
            invalid_date = 0
            wrong_month = 0
            duplicates = 0
            deferred: list[Game] = []

            for item in all_deals:
                raw_release = item.get("releaseDate")
                if not raw_release or int(raw_release) == 0:
                    steam_app_id_raw = item.get("steamAppID")
                    steam_app_id = int(steam_app_id_raw) if steam_app_id_raw else None
                    if steam_app_id and steam_app_id not in seen_ids:
                        seen_ids.add(steam_app_id)
                        cover_url = None
                        thumb = item.get("thumb")
                        if thumb:
                            cover_url = HttpUrl(thumb)
                        deferred.append(
                            Game(
                                id=str(item.get("dealID", "")),
                                title=item.get("title", "Unknown"),
                                steam_app_id=steam_app_id,
                                cover_url=cover_url,
                                release_date=None,
                                provider_name=self.name,
                            ),
                        )
                    invalid_date += 1
                    continue
                try:
                    raw_ts = int(raw_release)
                    release = datetime.fromtimestamp(raw_ts, tz=UTC).date()
                except (ValueError, TypeError, OSError):
                    invalid_date += 1
                    continue
                if not (release.year == year and release.month == month):
                    wrong_month += 1
                    continue
                steam_app_id_raw = item.get("steamAppID")
                steam_app_id = int(steam_app_id_raw) if steam_app_id_raw else None
                if steam_app_id and steam_app_id in seen_ids:
                    duplicates += 1
                    continue
                if steam_app_id:
                    seen_ids.add(steam_app_id)
                cover_url: HttpUrl | None = None
                thumb = item.get("thumb")
                if thumb:
                    cover_url = HttpUrl(thumb)
                games.append(
                    Game(
                        id=str(item.get("dealID", "")),
                        title=item.get("title", "Unknown"),
                        steam_app_id=steam_app_id,
                        cover_url=cover_url,
                        release_date=release,
                        provider_name=self.name,
                    ),
                )
            games.extend(deferred)

            games = sorted(games, key=lambda g: g.release_date or date.max)[:limit]
            elapsed = time.monotonic() - start
            logger.info(
                "CheapShark monthly releases for %04d-%02d: "
                "fetched=%d invalid_date=%d wrong_month=%d "
                "duplicates=%d valid=%d returned=%d",
                year,
                month,
                total_fetched,
                invalid_date,
                wrong_month,
                duplicates,
                len(games),
                len(games),
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
                "CheapShark monthly releases failed for %04d-%02d: %s",
                year,
                month,
                exc,
            )
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=self.name,
                    returned=0,
                    response_time_ms=round(elapsed * 1000),
                    errors=[{"error": str(exc)}],
                ),
            )

    async def healthcheck(self) -> dict[str, Any]:
        """Ping CheapShark API and report availability."""
        return await check_provider_health(self.http_client, f"{self.deals_url}?limit=1")
