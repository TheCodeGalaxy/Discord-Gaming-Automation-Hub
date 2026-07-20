"""New releases service — aggregate game releases for /new and #coming-soon.

Uses date-range sliding windows instead of strict calendar-month matching
so that sparse real-world data produces meaningful results.
"""

from __future__ import annotations

import asyncio
import calendar
import logging
import math
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any

from gaming_hub.data.cache.decorator import CachedProviderDecorator
from gaming_hub.models.domain.game import Game
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult
from gaming_hub.models.dto.request import SearchRequest

if TYPE_CHECKING:
    from gaming_hub.core.interfaces import CacheBackend, DataProvider

logger = logging.getLogger(__name__)

AAA_PUBLISHERS = frozenset(
    {
        "Electronic Arts",
        "Ubisoft",
        "Activision",
        "Bethesda Softworks",
        "Square Enix",
        "Bandai Namco Entertainment",
        "Capcom",
        "Sega",
        "2K",
        "Rockstar Games",
        "Nintendo",
        "Sony Interactive Entertainment",
        "Microsoft",
        "Deep Silver",
        "THQ Nordic",
        "Paradox Interactive",
        "Warner Bros.",
        "Embracer Group",
        "Focus Entertainment",
        "Devolver Digital",
        "Team17",
        "Raw Fury",
        "505 Games",
        "Gearbox Publishing",
        "Coffee Stain Studios",
        "Annapurna Interactive",
        "Humble Bundle",
        "Netflix",
    }
)

GENRE_BONUS: dict[str, int] = {
    "Action": 8,
    "RPG": 8,
    "Strategy": 6,
    "Adventure": 5,
    "Simulation": 4,
    "Sports": 4,
    "Racing": 4,
    "Casual": 2,
    "Indie": 1,
    "Free to Play": 3,
    "Massively Multiplayer": 5,
    "Early Access": 2,
}

FROZEN_UPCOMING = frozenset({"cheapshark", "steam_community", "isthereanydeal", "rawg"})
FROZEN_MONTHLY = frozenset({"cheapshark", "steam_community", "epic", "isthereanydeal", "rawg"})


@dataclass
class NewReleasesResult:
    """Aggregated upcoming game releases from all providers."""

    games: list[Game] = field(default_factory=list)
    total: int = 0
    date_range: tuple[date, date] = (date.today(), date.today())
    errors: list[dict[str, Any]] = field(default_factory=list)


class NewReleasesService:
    """Orchestrate release-date aggregation across all registered providers."""

    SOURCES_UPCOMING = FROZEN_UPCOMING
    SOURCES_CURRENT_MONTH = FROZEN_MONTHLY

    def __init__(
        self,
        providers: list[DataProvider],
        cache: CacheBackend,
    ) -> None:
        """Wrap each provider with a caching decorator."""
        self._providers = [CachedProviderDecorator(p, cache) for p in providers]

    async def get_upcoming(
        self,
        *,
        days_ahead: int = 0,
        days_prior: int = 0,
        limit: int = 20,
    ) -> NewReleasesResult:
        """Return the most popular releases from the past 6 full calendar months.

        Window: the **6 complete months before the current month**
        (e.g. in July we return Jan+Feb+Mar+Apr+May+June releases). Never
        includes the current month.

        Sorted by popularity score descending — never by insertion order.
        """
        _ = days_ahead, days_prior  # unused; window is calendar-based
        today = date.today()

        # Compute rolling 6-month window: previous 6 full months
        month_offset = today.month
        year = today.year
        months: list[tuple[int, int]] = []
        for off in (1, 2, 3, 4, 5, 6):
            m = month_offset - off
            y = year
            if m <= 0:
                m += 12
                y -= 1
            months.append((y, m))
        # Sort chronologically (oldest first)
        months.reverse()

        first_month = months[0]
        last_month = months[-1]
        _, last_day = calendar.monthrange(last_month[0], last_month[1])
        window_start = date(first_month[0], first_month[1], 1)
        window_end = date(last_month[0], last_month[1], last_day)
        # Never include future games
        window_end = min(window_end, today)

        logger.info(
            "/new: window %s → %s (6 full months before current month)",
            window_start.isoformat(),
            window_end.isoformat(),
        )

        all_games: list[Game] = []
        errors: list[dict[str, Any]] = []
        steam_app_ids: set[int] = set()

        await self._collect_new_releases(
            all_games,
            errors,
            steam_app_ids,
            window_start,
            window_end,
            days_prior=365,
            limit=limit * 3,
        )

        for y, m in months:
            await self._collect_monthly_releases(
                y,
                m,
                all_games,
                errors,
                steam_app_ids,
                window_start,
                window_end,
                self.SOURCES_UPCOMING,
            )
            await self._collect_featured_releases(
                y,
                m,
                all_games,
                errors,
                steam_app_ids,
                window_start,
                window_end,
                self.SOURCES_UPCOMING,
            )
            await self._collect_itad_releases(
                y,
                m,
                all_games,
                errors,
                steam_app_ids,
            )
            await self._collect_epic_catalog_releases(
                y,
                m,
                all_games,
                errors,
                window_start,
                window_end,
            )

        await self._collect_trending_releases(
            all_games,
            errors,
            steam_app_ids,
        )

        await self._enrich_from_steam(all_games, steam_app_ids, errors)

        # Post-enrichment window filter: games that arrived without release
        # dates (e.g. Steam trending) now have them and may fall outside the
        # rolling 6-month window.
        pre_filter = len(all_games)
        all_games = [
            g for g in all_games if g.release_date and window_start <= g.release_date <= window_end
        ]
        logger.info(
            "/new: post-enrichment window filter: %d → %d games removed=%d",
            pre_filter,
            len(all_games),
            pre_filter - len(all_games),
        )

        merged = self._merge_upcoming(all_games)
        merged.sort(key=self._significance_score, reverse=True)

        logger.info(
            "/new: %d/%d games after merge (limit %d)",
            min(len(merged), limit),
            len(merged),
            limit,
        )
        return NewReleasesResult(
            games=merged[:limit],
            total=len(merged),
            errors=errors,
        )

    async def get_year_releases(
        self,
        year: int,
        *,
        limit: int = 200,
    ) -> NewReleasesResult:
        """Return the most popular releases for **all 12 months** of *year*.

        Collects each month independently and merges all results.
        Primarily used by the Google Calendar sync service.
        """
        all_games: list[Game] = []
        all_errors: list[dict[str, Any]] = []

        for month in range(1, 13):
            _, last_day = calendar.monthrange(year, month)
            ws = date(year, month, 1)
            we = date(year, month, last_day)
            # Skip months that have already ended entirely
            if we < date.today():
                continue

            games, errors = await self._collect_month(
                year, month, ws, we, limit // 12 + 10,
            )
            all_games.extend(games)
            all_errors.extend(errors)

        merged = self._merge_upcoming(all_games)
        merged.sort(key=self._significance_score, reverse=True)

        return NewReleasesResult(
            games=merged[:limit],
            total=len(merged),
            errors=all_errors,
        )

    async def _collect_month(
        self,
        year: int,
        month: int,
        window_start: date,
        window_end: date,
        limit: int,
    ) -> tuple[list[Game], list[dict[str, Any]]]:
        """Collect release data for a single (*year*, *month*).

        Returns ``(games, errors)`` — raw, unmerged, pre-cap games that
        fall within *window_start* .. *window_end*.

        Shared by ``get_current_month`` and ``get_year_releases``.
        """
        games: list[Game] = []
        errors: list[dict[str, Any]] = []
        steam_app_ids: set[int] = set()

        await self._collect_new_releases(
            games, errors, steam_app_ids,
            window_start, window_end,
            days_prior=365, limit=limit,
        )
        await self._collect_monthly_releases(
            year, month, games, errors, steam_app_ids,
            window_start, window_end,
            self.SOURCES_CURRENT_MONTH,
        )
        await self._collect_featured_releases(
            year, month, games, errors, steam_app_ids,
            window_start, window_end,
            self.SOURCES_CURRENT_MONTH,
        )
        await self._collect_epic_catalog_releases(
            year, month, games, errors,
            window_start, window_end,
        )
        await self._collect_free_games_releases(
            year, month, games, errors,
            window_start, window_end,
        )
        await self._collect_itad_releases(
            year, month, games, errors, steam_app_ids,
        )
        await self._collect_trending_releases(
            games, errors, steam_app_ids,
        )

        if year == date.today().year and month == date.today().month:
            today = date.today()
            await self._collect_steam_search_month(
                today, games, errors, steam_app_ids,
            )

        await self._enrich_from_steam(games, steam_app_ids, errors)

        pre_filter = len(games)
        games = [
            g for g in games
            if g.release_date and window_start <= g.release_date <= window_end
        ]

        return games, errors

    async def get_current_month(self, *, limit: int = 20) -> NewReleasesResult:
        """Return games releasing in the **current calendar month only**."""
        today = date.today()
        window_start = date(today.year, today.month, 1)
        _, last_day = calendar.monthrange(today.year, today.month)
        window_end = date(today.year, today.month, last_day)
        logger.info(
            "#coming-soon: current month %s (%s → %s)",
            today.strftime("%B %Y"),
            window_start.isoformat(),
            window_end.isoformat(),
        )

        all_games, errors = await self._collect_month(
            today.year, today.month, window_start, window_end, limit=60,
        )

        merged = self._merge_upcoming(all_games)
        merged.sort(key=self._significance_score, reverse=True)

        # Per-day cap: at most 4 games per calendar day
        CAPPED = 4
        per_day: dict[str, int] = {}
        spread: list[Game] = []
        for g in merged:
            key = str(g.release_date) if g.release_date else "none"
            count = per_day.get(key, 0)
            if count < CAPPED:
                spread.append(g)
                per_day[key] = count + 1
        merged = spread

        result = merged[:limit]

        logger.info(
            "#coming-soon: %d/%d games after merge and spread, %d returned (limit %d)",
            len(merged),
            len(all_games),
            len(result),
            limit,
        )
        return NewReleasesResult(
            games=result,
            total=len(merged),
            errors=errors,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _months_in_range(start: date, end: date) -> list[tuple[int, int]]:
        """Return all (year, month) tuples between *start* and *end* inclusive."""
        seen: set[tuple[int, int]] = set()
        d = start.replace(day=1)
        while d <= end:
            seen.add((d.year, d.month))
            m = d.month + 1
            y = d.year
            if m > 12:  # noqa: PLR2004
                m = 1
                y += 1
            d = d.replace(year=y, month=m)
        return sorted(seen)

    # ── Collection helpers ──────────────────────────────────────────────────

    async def _collect_new_releases(
        self,
        all_games: list[Game],
        errors: list[dict[str, Any]],
        steam_app_ids: set[int],
        window_start: date | None = None,
        window_end: date | None = None,
        days_prior: int = 365,
        limit: int = 40,
    ) -> None:
        """CheapShark ``get_new_releases`` — past-year release data."""
        for provider in self._providers:
            if provider.name not in self.SOURCES_UPCOMING:
                continue
            if not hasattr(provider, "get_new_releases"):
                continue
            try:
                result = await provider.get_new_releases(
                    days_ahead=days_prior,
                    limit=limit,
                )
                fetched = len(result.games or [])
                accepted = 0
                rejected = 0
                for game in result.games or []:
                    if game.release_date and (
                        window_start is not None
                        and window_end is not None
                        and not (window_start <= game.release_date <= window_end)
                    ):
                        rejected += 1
                        continue
                    all_games.append(game)
                    accepted += 1
                    if game.steam_app_id:
                        steam_app_ids.add(game.steam_app_id)
                logger.info(
                    "%s get_new_releases: fetched=%d accepted=%d rejected=%d",
                    provider.name,
                    fetched,
                    accepted,
                    rejected,
                )
                if result.metadata.errors:
                    errors.extend(result.metadata.errors)
            except Exception as exc:
                logger.warning("get_new_releases failed for %s: %s", provider.name, exc)
                errors.append(
                    {
                        "provider": provider.name,
                        "method": "get_new_releases",
                        "error": str(exc),
                    }
                )

    async def _collect_monthly_releases(
        self,
        year: int,
        month: int,
        all_games: list[Game],
        errors: list[dict[str, Any]],
        steam_app_ids: set[int],
        window_start: date,
        window_end: date,
        source_filter: frozenset[str] | None = None,
    ) -> None:
        for provider in self._providers:
            if source_filter and provider.name not in source_filter:
                continue
            if not hasattr(provider, "get_monthly_releases"):
                continue
            result = await self._safe_get_monthly(provider, year, month)
            self._ingest(
                provider,
                "get_monthly_releases",
                result,
                window_start,
                window_end,
                all_games,
                steam_app_ids,
                errors,
            )

    async def _collect_featured_releases(
        self,
        year: int,
        month: int,
        all_games: list[Game],
        errors: list[dict[str, Any]],
        steam_app_ids: set[int],
        window_start: date,
        window_end: date,
        source_filter: frozenset[str] | None = None,
    ) -> None:
        for provider in self._providers:
            if source_filter and provider.name not in source_filter:
                continue
            if not hasattr(provider, "get_featured_releases"):
                continue
            result = await self._safe_get_featured(provider, year, month)
            self._ingest(
                provider,
                "get_featured_releases",
                result,
                window_start,
                window_end,
                all_games,
                steam_app_ids,
                errors,
            )

    async def _collect_epic_catalog_releases(
        self,
        year: int,
        month: int,
        all_games: list[Game],
        errors: list[dict[str, Any]],
        window_start: date,
        window_end: date,
    ) -> None:
        for provider in self._providers:
            if provider.name != "epic":
                continue
            if not hasattr(provider, "get_upcoming_releases"):
                continue
            result = await self._safe_get_upcoming(provider, year, month)
            self._ingest(
                provider,
                "get_upcoming_releases",
                result,
                window_start,
                window_end,
                all_games,
                set(),
                errors,
            )

    async def _collect_free_games_releases(
        self,
        year: int,
        month: int,
        all_games: list[Game],
        errors: list[dict[str, Any]],
        window_start: date,
        window_end: date,
    ) -> None:
        for provider in self._providers:
            if provider.name != "epic":
                continue
            if not hasattr(provider, "get_free_games"):
                continue
            try:
                result = await provider.get_free_games(upcoming=False)
                self._ingest(
                    provider,
                    "get_free_games",
                    result,
                    window_start,
                    window_end,
                    all_games,
                    set(),
                    errors,
                )
            except Exception as exc:
                logger.warning("Provider %s get_free_games failed: %s", provider.name, exc)
                errors.append(
                    {
                        "provider": provider.name,
                        "method": "get_free_games",
                        "error": str(exc),
                    }
                )

    async def _collect_itad_releases(
        self,
        year: int,
        month: int,
        all_games: list[Game],
        errors: list[dict[str, Any]],
        steam_app_ids: set[int],
    ) -> None:
        """Attempt release discovery from IsThereAnyDeal (limited API)."""
        for provider in self._providers:
            if provider.name != "isthereanydeal":
                continue
            if not hasattr(provider, "search"):
                continue
            try:
                search_prompts = ["the", "of", "2026", "2025"]
                seen_ids: set[str] = set()
                contributed = 0
                for query in search_prompts:
                    search_result = await provider.search(
                        SearchRequest(query=query, limit=10),
                    )
                    for game in search_result.games or []:
                        if not game.release_date:
                            continue
                        key = game.id or game.title.lower().strip()
                        if key in seen_ids:
                            continue
                        seen_ids.add(key)
                        all_games.append(game)
                        contributed += 1
                        if game.steam_app_id:
                            steam_app_ids.add(game.steam_app_id)
                logger.info(
                    "isthereanydeal search: contributed=%d (ITAD has no bulk-release API)",
                    contributed,
                )
            except Exception as exc:
                logger.warning("ITAD collection failed: %s", exc)
                errors.append(
                    {
                        "provider": provider.name,
                        "method": "_collect_itad_releases",
                        "error": str(exc),
                    }
                )

    def _ingest(
        self,
        provider: Any,
        method: str,
        result: ProviderResult,
        window_start: date,
        window_end: date,
        all_games: list[Game],
        steam_app_ids: set[int],
        errors: list[dict[str, Any]],
    ) -> None:
        """Validate games fall within *window_start* … *window_end*."""
        fetched = len(result.games or [])
        valid = 0
        rejected = 0
        reasons: dict[str, int] = {}
        for game in result.games or []:
            if self._in_window(game, window_start, window_end):
                all_games.append(game)
                valid += 1
                if game.steam_app_id:
                    steam_app_ids.add(game.steam_app_id)
            else:
                reason = self._reject_reason(game, window_start, window_end)
                reasons[reason] = reasons.get(reason, 0) + 1
                rejected += 1
        if result.metadata.errors:
            errors.extend(result.metadata.errors)
        r_str = "; ".join(f"{k}={v}" for k, v in sorted(reasons.items(), key=lambda x: -x[1]))
        logger.info(
            "%s %s: fetched=%d accepted=%d rejected=%d [%s]",
            provider.name,
            method,
            fetched,
            valid,
            rejected,
            r_str or "none",
        )

    # ── Validation ───────────────────────────────────────────────────────────

    @staticmethod
    def _in_window(game: Game, start: date, end: date) -> bool:
        if not game.release_date:
            return True
        return start <= game.release_date <= end

    @staticmethod
    def _reject_reason(game: Game, start: date, end: date) -> str:
        if not game.release_date:
            return "invalid_date"
        if game.release_date < start:
            return "too_old"
        if game.release_date > end:
            return "too_future"
        return "unknown"

    async def _collect_trending_releases(
        self,
        all_games: list[Game],
        errors: list[dict[str, Any]],
        steam_app_ids: set[int],
    ) -> None:
        """Steam Community trending games — supplementary source for /new.

        Trending games arrive without release dates. Enrichment (appdetails)
        adds dates, and the post-enrichment window filter removes games that
        fall outside the rolling 6-month window.
        """
        for provider in self._providers:
            if provider.name != "steam_community":
                continue
            if not hasattr(provider, "get_trending"):
                continue
            try:
                result = await provider.get_trending(limit=80)
                fetched = len(result.games or [])
                accepted = 0
                for game in result.games or []:
                    all_games.append(game)
                    accepted += 1
                    if game.steam_app_id:
                        steam_app_ids.add(game.steam_app_id)
                logger.info(
                    "%s get_trending: fetched=%d accepted=%d (dates set during enrichment)",
                    provider.name,
                    fetched,
                    accepted,
                )
            except Exception as exc:
                logger.warning("Steam trending failed: %s", exc)
                errors.append(
                    {
                        "provider": provider.name,
                        "method": "get_trending",
                        "error": str(exc),
                    }
                )

    async def _collect_steam_search_month(
        self,
        today: date,
        all_games: list[Game],
        errors: list[dict[str, Any]],
        steam_app_ids: set[int],
    ) -> None:
        """Steam search pagination — pull candidates from across the full month."""
        for provider in self._providers:
            if provider.name != "steam_community":
                continue
            if not hasattr(provider, "get_search_releases"):
                continue
            try:
                end_page = max(5, today.day * 3 + 5)
                result = await provider.get_search_releases((1, end_page), step=3)
                fetched = len(result.games or [])
                accepted = 0
                for game in result.games or []:
                    all_games.append(game)
                    accepted += 1
                    if game.steam_app_id:
                        steam_app_ids.add(game.steam_app_id)
                logger.info(
                    "steam_community get_search_releases: fetched=%d accepted=%d (pages 1-%d step=3)",
                    fetched,
                    accepted,
                    end_page,
                )
            except Exception as exc:
                logger.warning("Steam search month failed: %s", exc)
                errors.append(
                    {
                        "provider": provider.name,
                        "method": "get_search_releases",
                        "error": str(exc),
                    }
                )

    # ── Steam enrichment ────────────────────────────────────────────────────

    async def _enrich_from_steam(
        self,
        all_games: list[Game],
        steam_app_ids: set[int],
        errors: list[dict[str, Any]],
    ) -> None:
        steam_provider = next(
            (p for p in self._providers if p.name == "steam_community"),
            None,
        )
        if not (steam_provider and hasattr(steam_provider, "search") and steam_app_ids):
            return
        logger.info("Enriching %d games from Steam appdetails", len(steam_app_ids))

        async def _enrich_one(app_id: int) -> Game | None:
            try:
                result = await steam_provider.search(
                    SearchRequest(steam_app_id=app_id),
                )
                if result.games:
                    return result.games[0]
            except Exception:
                logger.debug("Steam enrichment failed for app %d", app_id)
            return None

        app_ids_list = list(steam_app_ids)
        for i in range(0, len(app_ids_list), 10):
            batch = app_ids_list[i : i + 10]
            tasks = [_enrich_one(aid) for aid in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for app_id, rich in zip(batch, results, strict=False):
                if not isinstance(rich, Game):
                    continue
                for game in all_games:
                    if game.steam_app_id == app_id:
                        self._merge_metadata(game, rich)

    @staticmethod
    def _merge_metadata(target: Game, source: Game) -> None:  # noqa: PLR0912
        if source.description and not target.description:
            target.description = source.description
        if source.short_description and not target.short_description:
            target.short_description = source.short_description
        if source.platforms and not target.platforms:
            target.platforms = source.platforms
        if source.genres and not target.genres:
            target.genres = source.genres
        if source.developers and not target.developers:
            target.developers = source.developers
        if source.publishers and not target.publishers:
            target.publishers = source.publishers
        if source.cover_url and not target.cover_url:
            target.cover_url = source.cover_url
        if source.provider_url and not target.provider_url:
            target.provider_url = source.provider_url
        if source.steam_review_count and not target.steam_review_count:
            target.steam_review_count = source.steam_review_count
        if source.steam_review_score and not target.steam_review_score:
            target.steam_review_score = source.steam_review_score
        if source.metacritic_score and not target.metacritic_score:
            target.metacritic_score = source.metacritic_score
        if source.is_free and not target.is_free:
            target.is_free = source.is_free
        if source.raw_metadata:
            if target.raw_metadata:
                target.raw_metadata.update(source.raw_metadata)
            else:
                target.raw_metadata = source.raw_metadata

    # ── Safe caller wrappers ────────────────────────────────────────────────

    @staticmethod
    async def _safe_get_monthly(provider: Any, year: int, month: int) -> ProviderResult:
        try:
            if hasattr(provider, "get_monthly_releases"):
                result = await provider.get_monthly_releases(year, month, limit=20)
                return result  # type: ignore[no-any-return]
            return ProviderResult(metadata=ProviderMetadata(provider=provider.name))
        except Exception as e:
            logger.exception("Monthly releases error from %s", provider.name)
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=provider.name,
                    errors=[
                        {
                            "type": "monthly_releases",
                            "provider": provider.name,
                            "detail": str(e),
                        }
                    ],
                ),
            )

    @staticmethod
    async def _safe_get_featured(provider: Any, year: int, month: int) -> ProviderResult:
        try:
            if hasattr(provider, "get_featured_releases"):
                result = await provider.get_featured_releases(year, month, limit=20)
                return result  # type: ignore[no-any-return]
            return ProviderResult(metadata=ProviderMetadata(provider=provider.name))
        except Exception as e:
            logger.exception("Featured releases error from %s", provider.name)
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=provider.name,
                    errors=[
                        {
                            "type": "featured_releases",
                            "provider": provider.name,
                            "detail": str(e),
                        }
                    ],
                ),
            )

    @staticmethod
    async def _safe_get_upcoming(provider: Any, year: int, month: int) -> ProviderResult:
        try:
            if hasattr(provider, "get_upcoming_releases"):
                result = await provider.get_upcoming_releases(year, month, limit=20)
                return result  # type: ignore[no-any-return]
            return ProviderResult(metadata=ProviderMetadata(provider=provider.name))
        except Exception as e:
            logger.exception("Upcoming releases error from %s", provider.name)
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=provider.name,
                    errors=[
                        {
                            "type": "upcoming_releases",
                            "provider": provider.name,
                            "detail": str(e),
                        }
                    ],
                ),
            )

    # ── Month spreading ───────────────────────────────────────────────────

    @staticmethod
    def _spread_across_month(games: list[Game], limit: int) -> list[Game]:
        """Select games spread across the month, preferring diverse dates.

        Sorts all candidates by global popularity, then greedily picks
        one per week per pass. This ensures the strongest games are
        selected while still distributing release dates across the month.
        """
        if not games or limit <= 0:
            return []

        sorted_games = sorted(
            games,
            key=NewReleasesService._significance_score,
            reverse=True,
        )

        week_of: dict[int, int] = {}
        for g in sorted_games:
            if g.release_date:
                week_of[id(g)] = (g.release_date.day - 1) // 7

        if not week_of:
            return sorted_games[:limit]

        result: list[Game] = []
        taken: set[int] = set()
        used_weeks: set[int] = set()

        while len(result) < limit and len(taken) < len(sorted_games):
            used_weeks.clear()
            for g in sorted_games:
                if id(g) in taken:
                    continue
                w = week_of.get(id(g))
                if w is not None and w in used_weeks:
                    continue
                result.append(g)
                taken.add(id(g))
                if w is not None:
                    used_weeks.add(w)
                if len(result) >= limit:
                    return result

        return result[:limit]

    # ── Dedup helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _merge_upcoming(games: list[Game]) -> list[Game]:
        seen: dict[str, Game] = {}
        for game in games:
            if not game.provider_names:
                game.provider_names = [game.provider_name]
            key = str(game.steam_app_id or game.id or game.title.lower().strip())
            if key in seen:
                existing = seen[key]
                if NewReleasesService._richness(game) > NewReleasesService._richness(existing):
                    game.provider_names = list(
                        set(existing.provider_names + game.provider_names),
                    )
                    if existing.release_date and game.release_date:
                        game.release_date = min(existing.release_date, game.release_date)
                    seen[key] = game
                else:
                    existing.provider_names = list(
                        set(existing.provider_names + game.provider_names),
                    )
            else:
                seen[key] = game
        return list(seen.values())

    @staticmethod
    def _richness(game: Game) -> int:
        score = 0
        if game.cover_url:
            score += 1
        if game.description:
            score += 1
        if game.genres:
            score += 1
        if game.developers:
            score += 1
        return score

    @staticmethod
    def _significance_score(game: Game) -> float:  # noqa: PLR0912
        score: float = 0.0

        # ── 1. Review volume (log-scaled, strongest signal) ────────────
        if game.steam_review_count and game.steam_review_count > 0:
            score += int(math.log10(game.steam_review_count + 1)) * 30

        rm = game.raw_metadata or {}
        recom = rm.get("recommendations")
        if isinstance(recom, (int, float)) and recom > 0:
            score += int(math.log10(recom + 1)) * 30

        # ── 2. Review / critic scores ────────────────────────────────
        if game.steam_review_score:
            score += int(game.steam_review_score)
        if game.metacritic_score:
            score += int(game.metacritic_score)

        mc_from_raw = rm.get("metacritic_score")
        if isinstance(mc_from_raw, (int, float)) and not game.metacritic_score:
            score += int(mc_from_raw)

        # ── 3. Publisher reputation ──────────────────────────────────
        if game.publishers:
            for pub in game.publishers:
                if pub in AAA_PUBLISHERS:
                    score += 50
            score += 5

        if game.developers:
            score += 3

        # ── 4. Genre popularity ──────────────────────────────────────
        if game.genres:
            for g in game.genres:
                score += GENRE_BONUS.get(g, 1)
            score += 3

        # ── 5. Provider diversity ────────────────────────────────────
        unique_sources = len(
            {game.provider_name} | set(game.provider_names or []),
        )
        score += unique_sources * 10

        # ── 6. Free game boost ────────────────────────────────────────
        if game.is_free:
            score += 25
        if rm.get("is_free"):
            score += 25

        # ── 7. Metadata completeness ───────────────────────────────────
        if game.cover_url:
            score += 5
        if game.description:
            score += 3

        # ── 8. Game type preference ───────────────────────────────────
        game_type = rm.get("type")
        if game_type == "game":
            score += 5
        elif game_type == "dlc":
            score -= 5

        # ── 9. Deterministic tiebreaker ───────────────────────────────
        tiebreaker = (abs(game.steam_app_id or hash(game.title))) % 1000
        score += tiebreaker / 1_000_000.0

        return max(score, 0.0)
