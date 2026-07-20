"""Steam Community JSON provider adapter.

This adapter uses only free public endpoints such as
``store.steampowered.com/api/appdetails`` and Steam Community HTML pages.
It never uses the official Steam Web API or requires an API key.

- Fetch public app details by Steam App ID.
- Parse trending game data from the Steam Community trending page.
- Detect HTML error pages that Steam sometimes returns as HTTP 200.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from pydantic import HttpUrl

from gaming_hub.core.exceptions import ProviderError
from gaming_hub.data.providers.base import BaseHTTPProvider
from gaming_hub.models.domain.game import Game
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult
from gaming_hub.utils.http import check_provider_health

if TYPE_CHECKING:
    import httpx

    from gaming_hub.models.dto.request import SearchRequest

APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
TRENDING_URL = "https://steamcommunity.com/trending"
FEATURED_URL = "https://store.steampowered.com/api/featuredcategories"

logger = logging.getLogger(__name__)
FEATURED_URL = "https://store.steampowered.com/api/featuredcategories"


class SteamCommunityProvider(BaseHTTPProvider):
    """Adapter for the Steam Community public data endpoints."""

    name = "steam_community"

    def __init__(self, http_client: Any, settings: Any) -> None:
        """Initialize with instance-level URLs derived from settings."""
        super().__init__(http_client, settings)
        store_base = (settings.steam_store_base_url or "https://store.steampowered.com").rstrip("/")
        community_base = (settings.steam_community_base_url or "https://steamcommunity.com").rstrip(
            "/"
        )
        self.appdetails_url = f"{store_base}/api/appdetails"
        self.trending_url = f"{community_base}/trending"

    def _detect_html_error(self, response: httpx.Response) -> bool:
        """Check if Steam returned an HTML error page disguised as 200."""
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            return True
        text = response.text.strip()
        if text.startswith("<!DOCTYPE"):
            return True
        return bool(text.startswith("<html"))

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Override _request with Steam HTML error detection.

        Only applies HTML detection to the appdetails JSON endpoint,
        not to the trending HTML page.
        """
        response = await super()._request(method, url, **kwargs)
        if self.appdetails_url in url and self._detect_html_error(response):
            raise ProviderError(
                "Steam returned an HTML page instead of JSON",
                provider=self.name,
                status_code=response.status_code,
                details={
                    "url": url,
                    "content_type": response.headers.get("content-type", ""),
                },
            )
        return response

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        """Parse Steam date string (various formats) to a ``date`` object."""
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except (ValueError, TypeError):
            pass
        for fmt in ("%d %b, %Y", "%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%d %B %Y", "%b %Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except (ValueError, TypeError):
                continue
        return None

    def _extract_reviews(self, appdata: dict[str, Any]) -> dict[str, Any]:
        """Extract review scores from Steam appdetail ratings data."""
        ratings = appdata.get("ratings", {})
        if not ratings:
            return {"score": None, "count": 0}
        total_positive = 0
        total_negative = 0
        for rating_data in ratings.values():
            if isinstance(rating_data, dict):
                total_positive += rating_data.get("total_positive", 0)
                total_negative += rating_data.get("total_negative", 0)
        total = total_positive + total_negative
        score = round((total_positive / total) * 100) if total > 0 else None
        return {"score": score, "count": total}

    def _normalize_appdetail(self, appdata: dict[str, Any], appid: int) -> Game:
        """Normalize a Steam /api/appdetails response into a Game entity."""
        name = appdata.get("name", "Unknown")

        cover_url: HttpUrl | None = None
        header = appdata.get("header_image")
        if header:
            cover_url = HttpUrl(header)

        provider_url: HttpUrl | None = None
        if appid:
            provider_url = HttpUrl(f"https://store.steampowered.com/app/{appid}")

        reviews = self._extract_reviews(appdata)

        release_date_obj = appdata.get("release_date", {})
        parsed_release = (
            self._parse_date(release_date_obj.get("date"))
            if isinstance(release_date_obj, dict)
            else None
        )

        metacritic_raw = appdata.get("metacritic")
        metacritic_data = metacritic_raw if isinstance(metacritic_raw, dict) else {}

        recommendations_raw = appdata.get("recommendations")
        recommendations = (
            recommendations_raw.get("total") if isinstance(recommendations_raw, dict) else None
        )

        return Game(
            id=str(appid),
            title=name,
            description=appdata.get("short_description", ""),
            steam_app_id=appid,
            cover_url=cover_url,
            release_date=parsed_release,
            genres=[g["description"] for g in appdata.get("genres", []) if "description" in g],
            tags=[t["description"] for t in appdata.get("tags", []) if "description" in t],
            developers=appdata.get("developers", []),
            publishers=appdata.get("publishers", []),
            metacritic_score=metacritic_data.get("score"),
            steam_review_score=reviews["score"],
            steam_review_count=reviews["count"],
            provider_name=self.name,
            provider_url=provider_url,
            raw_metadata={
                "type": appdata.get("type"),
                "is_free": appdata.get("is_free", False),
                "metacritic_score": metacritic_data.get("score"),
                "recommendations": recommendations,
                "review_score": reviews["score"],
                "review_count": reviews["count"],
            },
        )

    async def _resolve_id_from_query(self, query: str) -> int | None:
        """Resolve a text query to a Steam App ID.

        Placeholder — currently returns None. Future phases may integrate
        CheapShark search to resolve titles to Steam App IDs.
        """
        _ = query
        return None

    async def search(self, request: SearchRequest) -> ProviderResult:
        """Lookup a Steam game by App ID or query."""
        start = time.monotonic()
        try:
            if request.steam_app_id is None and not request.query:
                return ProviderResult(
                    metadata=ProviderMetadata(
                        provider=self.name,
                        query=request.query,
                        returned=0,
                        response_time_ms=round((time.monotonic() - start) * 1000),
                        errors=[{"error": "No steam_app_id or query provided"}],
                    ),
                )

            appid: int | None = request.steam_app_id
            if appid is None:
                appid = await self._resolve_id_from_query(request.query)

            if appid is None:
                elapsed = time.monotonic() - start
                return ProviderResult(
                    metadata=ProviderMetadata(
                        provider=self.name,
                        query=request.query,
                        returned=0,
                        response_time_ms=round(elapsed * 1000),
                        errors=[
                            {
                                "error": f"Could not resolve query '{request.query}' "
                                "to a Steam App ID",
                            }
                        ],
                    ),
                )

            response = await self._get(
                self.appdetails_url,
                params={"appids": appid},
            )
            data = response.json()
            game_data = data.get(str(appid), {})
            if not game_data.get("success"):
                elapsed = time.monotonic() - start
                return ProviderResult(
                    metadata=ProviderMetadata(
                        provider=self.name,
                        query=request.query,
                        returned=0,
                        response_time_ms=round(elapsed * 1000),
                        errors=[
                            {
                                "type": "not_found",
                                "detail": f"Steam app {appid} not found",
                            }
                        ],
                    ),
                )

            game = self._normalize_appdetail(game_data["data"], appid)
            elapsed = time.monotonic() - start
            return ProviderResult(
                games=[game],
                metadata=ProviderMetadata(
                    provider=self.name,
                    query=request.query,
                    total_available=1,
                    returned=1,
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

    def _parse_trending_html(self, html: str, limit: int) -> list[Game]:
        """Parse Steam Community trending HTML into Game objects."""
        games: list[Game] = []
        pattern = re.compile(
            r'data-appid="(\d+)".*?trending_item_name[^>]*>(.*?)</div>',
            re.DOTALL,
        )
        matches = pattern.findall(html)[:limit]
        for appid_str, name_html in matches:
            name = re.sub(r"<[^>]+>", "", name_html).strip()
            if not name:
                continue
            appid = int(appid_str)
            provider_url = HttpUrl(f"https://store.steampowered.com/app/{appid}")
            games.append(
                Game(
                    id=str(appid),
                    title=name,
                    steam_app_id=appid,
                    provider_name=self.name,
                    provider_url=provider_url,
                    raw_metadata={"current_players": None},
                ),
            )
        return games

    async def _fetch_app_data(self, app_id: int) -> dict[str, Any] | None:
        """Fetch and parse appdetails for a single Steam App ID.

        Returns the ``data`` dict on success, or ``None`` on any error.
        """
        try:
            response = await self._get(
                self.appdetails_url,
                params={"appids": app_id},
            )
            data = response.json()
            game_data = data.get(str(app_id), {})
            if game_data.get("success"):
                result: dict[str, Any] | None = game_data.get("data")
                return result
            return None
        except Exception:
            return None

    async def get_featured_releases(
        self,
        year: int,
        month: int,
        *,
        limit: int = 20,
    ) -> ProviderResult:
        """Fetch games from Steam featured categories (new_releases, coming_soon).

        Calls ``featuredcategories``, then batch-looks up ``appdetails`` for
        every discovered App ID (to obtain accurate release dates). Returns
        games whose parsed release date matches the requested year/month.
        Concurrent batches of up to 10 to avoid overwhelming Steam.
        """
        start = time.monotonic()
        try:
            appdetails_response = await self._get(
                "https://store.steampowered.com/api/featuredcategories",
            )
            raw = appdetails_response.json()
            seen_ids: set[int] = set()
            app_ids: list[int] = []
            item_lookup: dict[int, dict[str, Any]] = {}

            for section_key in ("new_releases", "coming_soon"):
                section = raw.get(section_key)
                if not section or not isinstance(section, dict):
                    continue
                for item in section.get("items") or []:
                    app_id = item.get("id")
                    if not app_id or app_id in seen_ids:
                        continue
                    seen_ids.add(app_id)
                    app_ids.append(app_id)
                    item_lookup[app_id] = item

            total_fetched = len(app_ids)

            games: list[Game] = []
            appdata_failures = 0
            month_mismatch = 0

            for i in range(0, len(app_ids), 10):
                batch = app_ids[i : i + 10]
                tasks = [self._fetch_app_data(aid) for aid in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for app_id, result in zip(batch, results, strict=False):
                    if not isinstance(result, dict):
                        appdata_failures += 1
                        continue
                    game = self._normalize_appdetail(result, app_id)

                    if not game.release_date:
                        appdata_failures += 1
                        continue
                    if game.release_date.year != year or game.release_date.month != month:
                        month_mismatch += 1
                        continue

                    games.append(game)

            games = sorted(games, key=lambda g: g.release_date or date.max)[:limit]
            elapsed = time.monotonic() - start
            logger.info(
                "Steam featured releases for %04d-%02d: "
                "fetched=%d appdata_failures=%d month_mismatch=%d valid=%d",
                year,
                month,
                total_fetched,
                appdata_failures,
                month_mismatch,
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
                "Steam featured releases failed for %04d-%02d: %s",
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

    async def get_trending(self, *, limit: int = 20) -> ProviderResult:
        """Fetch trending games from the Steam Community trending page."""
        start = time.monotonic()
        try:
            response = await self._get(self.trending_url, params={"l": "english"})
            html = response.text
            games = self._parse_trending_html(html, limit)
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

    async def get_free_games(self, *, upcoming: bool = False) -> ProviderResult:
        """Steam has no free-games endpoint; returns empty."""
        _ = upcoming
        return ProviderResult(
            metadata=ProviderMetadata(provider=self.name, returned=0),
        )

    async def get_search_releases(
        self,
        page_range: tuple[int, int],
        *,
        step: int = 3,
    ) -> ProviderResult:
        """Fetch games from Steam search sorted by release date (descending).

        Paginates through *page_range* (start, end inclusive) at *step*
        intervals to sample games across a date range. Returns Game objects
        **without release dates** — the service enriches via ``appdetails``.
        """
        start = time.monotonic()
        try:
            games: list[Game] = []
            seen_ids: set[int] = set()
            start_page, end_page = page_range
            for page in range(min(start_page, end_page), max(start_page, end_page) + 1, step):
                try:
                    resp = await self._get(
                        "https://store.steampowered.com/search/results/",
                        params={
                            "sort_by": "Released_DESC",
                            "category1": 998,
                            "l": "english",
                            "json": 1,
                            "page": page,
                        },
                    )
                    data = resp.json()
                    for item in data.get("items") or []:
                        logo = item.get("logo", "")
                        m = re.search(r"/apps/(\d+)/", logo)
                        if not m:
                            continue
                        app_id = int(m.group(1))
                        if app_id in seen_ids:
                            continue
                        seen_ids.add(app_id)
                        name = item.get("name", "Unknown")
                        games.append(
                            Game(
                                id=str(app_id),
                                title=name,
                                steam_app_id=app_id,
                                provider_name=self.name,
                                provider_url=HttpUrl(f"https://store.steampowered.com/app/{app_id}"),
                                raw_metadata={"current_players": None},
                            ),
                        )
                except Exception:
                    continue
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

    async def get_deals(self, *, limit: int = 10) -> ProviderResult:
        """Steam has no deals endpoint; returns empty."""
        _ = limit
        return ProviderResult(
            metadata=ProviderMetadata(provider=self.name, returned=0),
        )

    async def healthcheck(self) -> dict[str, Any]:
        """Ping Steam appdetails endpoint and report status."""
        return await check_provider_health(
            self.http_client,
            f"{self.appdetails_url}?appids=1",
        )
