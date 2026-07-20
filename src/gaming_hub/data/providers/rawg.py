"""RAWG.io provider adapter.

Docs: https://rawg.io/apidocs

- Free tier: 20 000 requests / month, no credit card required.
- Sign up at https://rawg.io/register/developer to get an API key.
- Provides release dates, ratings, and popularity ordering — ideal for
  ``/new`` and ``#coming-soon``.

Requires ``RAWG_API_KEY`` in .env.  When the key is absent every method
returns an empty result (graceful degradation).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from gaming_hub.data.providers.base import BaseHTTPProvider
from gaming_hub.models.domain.game import Game
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult

if TYPE_CHECKING:
    from gaming_hub.models.dto.request import SearchRequest

logger = logging.getLogger(__name__)

BASE_URL = "https://api.rawg.io/api"


class RawgProvider(BaseHTTPProvider):
    """Adapter for the RAWG video game database API."""

    name = "rawg"

    def __init__(self, http_client: Any, settings: Any) -> None:
        """Initialize with RAWG API key from settings."""
        super().__init__(http_client, settings)
        self.api_key: str | None = settings.rawg_api_key
        self.base_url = (settings.rawg_base_url or BASE_URL).rstrip("/")

    # ── Interface: search ─────────────────────────────────────────────────

    async def search(self, request: SearchRequest) -> ProviderResult:
        """Search RAWG game database by title.

        When no query is provided returns popular games — useful for
        surprise-command and top-games pool building.
        """
        if not self.api_key:
            return self._empty("search")

        if not request.query:
            return await self.get_upcoming_releases(
                date.today().year,
                date.today().month,
                limit=request.limit,
            )

        params: dict[str, Any] = {
            "key": self.api_key,
            "search": request.query,
            "page_size": min(request.limit, 40),
            "search_precise": "true" if request.exact else "false",
        }
        if request.steam_app_id:
            params["stores"] = "steam"

        response = await self._get(
            f"{self.base_url}/games",
            params=params,
        )
        data = response.json()
        items = data.get("results", [])
        games = [self._normalize(item) for item in items]

        return ProviderResult(
            games=games,
            metadata=ProviderMetadata(
                provider=self.name,
                query=request.query,
                total_available=data.get("count"),
                returned=len(games),
            ),
        )

    # ── Interface: free games (not supported) ──────────────────────────────

    async def get_free_games(self, *, upcoming: bool = False) -> ProviderResult:
        """RAWG does not offer a free-game feed."""
        return self._empty("free_games")

    # ── Interface: deals (not supported) ───────────────────────────────────

    async def get_deals(self, *, limit: int = 10) -> ProviderResult:
        """RAWG does not offer a deals feed."""
        return self._empty("deals")

    # ── Interface: healthcheck ─────────────────────────────────────────────

    async def healthcheck(self) -> dict[str, Any]:
        """Verify connectivity with a minimal API call."""
        if not self.api_key:
            return {"provider": self.name, "status": "disabled", "detail": "RAWG_API_KEY not set"}
        try:
            response = await self._get(
                f"{self.base_url}/genres",
                params={"key": self.api_key},
            )
            ok = response.status_code == 200
            return {
                "provider": self.name,
                "status": "ok" if ok else "error",
                "status_code": response.status_code,
            }
        except Exception as e:
            return {"provider": self.name, "status": "error", "detail": str(e)}

    # ── #coming-soon: featured / upcoming releases for a specific month ──

    async def get_upcoming_releases(
        self,
        year: int,
        month: int,
        limit: int = 20,
    ) -> ProviderResult:
        """Return the most-popular games releasing in *year*-*month*.

        Uses RAWG's ``-added`` ordering as a proxy for popularity + buzz.
        """
        if not self.api_key:
            return self._empty("upcoming_releases")

        _, last_day = __import__("calendar").monthrange(year, month)
        date_range = f"{year:04d}-{month:02d}-01,{year:04d}-{month:02d}-{last_day:02d}"

        return await self._fetch_games(
            date_range=date_range,
            ordering="-added",
            page_size=min(limit, 40),
            method="upcoming_releases",
        )

    async def get_featured_releases(
        self,
        year: int,
        month: int,
        limit: int = 20,
    ) -> ProviderResult:
        """Alias — delegates to get_upcoming_releases."""
        return await self.get_upcoming_releases(year, month, limit)

    # ── /new: recent popular games (rolling 6-month window) ───────────────

    async def get_new_releases(
        self,
        days_ahead: int = 365,
        limit: int = 20,
    ) -> ProviderResult:
        """Return popular games released in the past 6 months.

        ``days_ahead`` is ignored — RAWG always uses past dates.
        """
        if not self.api_key:
            return self._empty("new_releases")

        end = date.today()
        start = end - timedelta(days=182)  # ~6 months
        date_range = f"{start.isoformat()},{end.isoformat()}"

        return await self._fetch_games(
            date_range=date_range,
            ordering="-added",
            page_size=min(limit, 40),
            method="new_releases",
        )

    async def get_monthly_releases(
        self,
        year: int,
        month: int,
        limit: int = 20,
    ) -> ProviderResult:
        """Sorted by added (popularity) for the full month."""
        return await self.get_upcoming_releases(year, month, limit)

    # ── Trending ──────────────────────────────────────────────────────────

    async def get_trending(self, limit: int = 40) -> ProviderResult:
        """Fetch trending games from RAWG (ordered by -added)."""
        if not self.api_key:
            return self._empty("trending")

        return await self._fetch_games(
            date_range=None,
            ordering="-added",
            page_size=min(limit, 40),
            method="trending",
        )

    # ── Internals ─────────────────────────────────────────────────────────

    async def _fetch_games(
        self,
        date_range: str | None,
        ordering: str,
        page_size: int,
        method: str,
    ) -> ProviderResult:
        """Common paginated fetch from RAWGs /games endpoint."""
        params: dict[str, Any] = {
            "key": self.api_key,
            "ordering": ordering,
            "page_size": page_size,
        }
        if date_range:
            params["dates"] = date_range

        try:
            response = await self._get(
                f"{self.base_url}/games",
                params=params,
            )
            data = response.json()
            items = data.get("results", [])
            games: list[Game] = []
            for item in items:
                try:
                    games.append(self._normalize(item))
                except Exception as e:
                    logger.warning("rawg normalize skipped item: %s", e)

            logger.info(
                "rawg %s: fetched=%d date_range=%s ordering=%s",
                method,
                len(games),
                date_range or "all",
                ordering,
            )

            return ProviderResult(
                games=games,
                metadata=ProviderMetadata(
                    provider=self.name,
                    total_available=data.get("count"),
                    returned=len(games),
                ),
            )
        except Exception as e:
            logger.exception("RAWG %s failed: %s", method, e)
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=self.name,
                    errors=[{"type": method, "detail": str(e)}],
                ),
            )

    def _normalize(self, item: dict[str, Any]) -> Game:
        """Map a RAWG response item to a Game entity."""
        raw_date = item.get("released")
        release_date: date | None = None
        if raw_date:
            try:
                release_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        slug = item.get("slug", "")
        game_id = str(item.get("id", ""))
        platforms: list[str] = []
        raw_platforms = item.get("platforms")
        if isinstance(raw_platforms, list):
            for p in raw_platforms:
                platform = p.get("platform") if isinstance(p, dict) else None
                if platform and isinstance(platform, dict):
                    name = platform.get("name")
                    if name and isinstance(name, str):
                        platforms.append(name)

        genres: list[str] = []
        raw_genres = item.get("genres")
        if isinstance(raw_genres, list):
            for g in raw_genres:
                if isinstance(g, dict) and isinstance(g.get("name"), str):
                    genres.append(g["name"])

        tags: list[str] = []
        raw_tags = item.get("tags")
        if isinstance(raw_tags, list):
            for t in raw_tags:
                if isinstance(t, dict) and isinstance(t.get("name"), str):
                    tags.append(t["name"])

        publishers: list[str] = []
        raw_publishers = item.get("publishers")
        if isinstance(raw_publishers, list):
            for pub in raw_publishers:
                if isinstance(pub, dict) and isinstance(pub.get("name"), str):
                    publishers.append(pub["name"])

        developers: list[str] = []
        raw_developers = item.get("developers")
        if isinstance(raw_developers, list):
            for dev in raw_developers:
                if isinstance(dev, dict) and isinstance(dev.get("name"), str):
                    developers.append(dev["name"])

        metacritic = item.get("metacritic")
        metacritic_score: int | None = None
        if metacritic is not None:
            try:
                metacritic_score = int(metacritic)
            except (ValueError, TypeError):
                pass

        rating = item.get("rating", 0) or 0
        ratings_count = item.get("ratings_count", 0) or 0
        # Map RAWG rating to a 0-100 steam-like review score
        steam_review_score = round(rating * 20, 1) if rating else None
        steam_review_count = ratings_count

        cover_url: str | None = None
        bg = item.get("background_image")
        if bg:
            cover_url = bg

        return Game(
            id=f"rawg-{game_id}",
            title=item.get("name", ""),
            description=item.get("description_raw"),
            release_date=release_date,
            genres=genres,
            tags=tags,
            platforms=platforms,
            developers=developers,
            publishers=publishers,
            metacritic_score=metacritic_score,
            steam_review_score=steam_review_score,
            steam_review_count=steam_review_count,
            cover_url=cover_url,  # type: ignore[arg-type]
            provider_name=self.name,
            raw_metadata={"slug": slug, "rawg_id": game_id},
        )

    @staticmethod
    def _empty(method: str) -> ProviderResult:
        """Return an empty result when the API key is missing."""
        logger.info("rawg %s: skipped (RAWG_API_KEY not set)", method)
        return ProviderResult(
            metadata=ProviderMetadata(provider="rawg", errors=[]),
        )
