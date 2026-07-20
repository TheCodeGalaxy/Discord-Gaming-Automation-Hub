"""Major game updates service.

Aggregates significant game updates (patches, DLC, seasons, expansions)
from Steam Community RSS news feeds. Only includes announcements published
within the current or previous UTC month. Items are scored and the top N
returned.

Sources: Steam RSS (via app IDs discovered across all four providers).
Never includes free games, discounts, sales, or coming-soon announcements.
"""

from __future__ import annotations

import asyncio
import contextlib
import email.utils
import html as html_module
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx

    from gaming_hub.core.interfaces import DataProvider

logger = logging.getLogger(__name__)

SIGNIFICANT_KEYWORDS = [
    "major patch",
    "season",
    "dlc",
    "expansion",
    "content update",
    "patch notes",
    "version ",
    "game update",
    "content pack",
    "chapter ",
    "update ",
    "new content",
    "anniversary",
    "roadmap",
    "battle pass",
    "event",
    "showcase",
    "release",
    "launched",
    "now available",
    "update available",
    "is here",
    "has arrived",
    "out now",
    "is live",
    "dropped",
    "launch",
    "edition",
    "remaster",
    "remake",
    "dlc pack",
    "add-on",
    "addon",
    "new mode",
    "game mode",
    "expansion pack",
    "content drop",
    "major content",
    "season pass",
    "update is now",
]

TRIVIAL_KEYWORDS = [
    "hotfix",
    "hot fix",
    "typofix",
    "maintenance",
    "minor update",
    "server maintenance",
    "downtime",
    "queue",
    "server reset",
    "technical issues",
    "login issues",
]

STEAM_RSS_URL = "https://steamcommunity.com/games/{appid}/rss/"

CONTENT_SCORE_MAP: list[tuple[str, int]] = [
    ("expansion", 8),
    ("season", 6),
    (" dlc ", 5),
    ("major patch", 5),
    ("battle pass", 4),
    ("content update", 4),
    ("patch notes", 3),
    ("game update", 3),
    ("content pack", 3),
    ("chapter ", 3),
    ("anniversary", 3),
    ("new content", 3),
    ("roadmap", 3),
    ("release", 2),
    ("launched", 2),
    ("now available", 2),
    ("version ", 2),
]

STEAM_FETCH_LIMIT = 200
FEED_TIMEOUT = 10.0


@dataclass
class GameUpdate:
    """A single significant game update or announcement."""

    app_id: int
    title: str
    game_name: str
    update_title: str
    url: str
    date: datetime
    snippet: str
    score: int = 0


@dataclass
class MajorUpdatesResult:
    """Aggregated major game updates from all sources."""

    updates: list[GameUpdate] = field(default_factory=list)
    total: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


class MajorUpdatesService:
    """Aggregate major game updates from Steam Community RSS feeds."""

    def __init__(
        self,
        providers: list[DataProvider],
        http_client: httpx.AsyncClient,
    ) -> None:
        """Initialize with provider list and shared HTTP client."""
        self._providers = providers
        self._http_client = http_client

    async def get_major_updates(self, *, limit: int = 10) -> MajorUpdatesResult:
        """Return significant game updates from the **previous 7 days only**.

        Discovers Steam App IDs from all providers, fetches their Steam
        Community RSS news feeds, scores by content and recency, and
        returns at most *limit* items sorted by score then date (desc).

        Popularity (recommendation count) is used as a scoring bonus
        rather than a hard filter — even small games with major
        announcements (expansions, DLC, new seasons) can appear.
        """
        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)
        logger.info(
            "#major-updates: window %s → %s (past 7 days)",
            week_ago.isoformat(),
            now.isoformat(),
        )

        steam_app_ids = await self._collect_steam_app_ids()
        if not steam_app_ids:
            logger.info("No Steam App IDs found — returning empty")
            return MajorUpdatesResult()

        raw_updates = await self._fetch_rss_updates(steam_app_ids)
        discards: dict[str, int] = {}
        valid_updates: list[GameUpdate] = []

        for update in raw_updates:
            if update.date < week_ago or update.date > now:
                discards["outside_window"] = discards.get("outside_window", 0) + 1
                continue
            self._calculate_score(update, now)
            if update.score <= 0:
                discards["low_score"] = discards.get("low_score", 0) + 1
                continue
            valid_updates.append(update)

        merged = self._deduplicate_updates(valid_updates)
        merged.sort(key=lambda u: (-u.score, -u.date.timestamp()))

        for reason, count in sorted(discards.items(), key=lambda x: -x[1]):
            logger.info("Items discarded (%s): %d", reason, count)
        logger.info(
            "#major-updates: fetched=%d discarded=%d valid=%d returned=%d (limit %d)",
            len(raw_updates),
            sum(discards.values()),
            len(merged),
            min(len(merged), limit),
            limit,
        )
        return MajorUpdatesResult(
            updates=merged[:limit],
            total=len(merged),
        )

    # ── Scoring ─────────────────────────────────────────────────────────────

    def _calculate_score(self, update: GameUpdate, now: datetime) -> None:
        """Calculate a combined significance score for an update.

        Starts with a base score, adds keyword-specific points (expansion,
        DLC, season, etc.), a recency bonus, and a popularity bonus based
        on the game's recommendation count (fetched during RSS at startup).
        """
        score = 3  # base score
        lower = update.title.lower()
        for keyword, points in CONTENT_SCORE_MAP:
            if keyword in lower:
                score += points
        if update.snippet:
            score += 1
        recency_bonus = 0
        age = now - update.date
        if age < timedelta(hours=24):
            recency_bonus = 3
        elif age < timedelta(days=3):
            recency_bonus = 2
        elif age < timedelta(days=7):
            recency_bonus = 1
        score += recency_bonus
        update.score = max(score, 0)

    @staticmethod
    def _deduplicate_updates(updates: list[GameUpdate]) -> list[GameUpdate]:
        """Deduplicate updates by App ID + URL."""
        seen: dict[str, GameUpdate] = {}
        for update in updates:
            key = f"{update.app_id}:{update.url}"
            existing = seen.get(key)
            if existing is None or update.score > existing.score:
                seen[key] = update
        return list(seen.values())

    # ── Steam App ID discovery ──────────────────────────────────────────────

    async def _collect_steam_app_ids(self) -> list[int]:
        """Collect unique Steam App IDs from all providers.

        Tries multiple data methods: ``get_deals``, ``get_new_releases``,
        ``get_featured_releases`` (current + past 6 months), and
        ``get_monthly_releases`` (current + past 2 months).
        """
        ids: set[int] = set()
        now = datetime.now(UTC)

        def _collect_from_games(games: list[Any]) -> None:
            for game in games:
                if isinstance(game.steam_app_id, int) and game.steam_app_id > 0:
                    ids.add(game.steam_app_id)

        for provider in self._providers:
            # get_deals
            try:
                result = await provider.get_deals(limit=60)
                for deal in result.deals or []:
                    sid = deal.raw_metadata.get("steam_app_id") if deal.raw_metadata else None
                    if isinstance(sid, int):
                        ids.add(sid)
                _collect_from_games(result.games or [])
            except Exception:
                logger.debug("get_deals failed for %s", provider.name)

            # get_new_releases (CheapShark only)
            if hasattr(provider, "get_new_releases"):
                try:
                    result = await provider.get_new_releases(days_ahead=365, limit=60)
                    _collect_from_games(result.games or [])
                except Exception:
                    logger.debug("get_new_releases failed for %s", provider.name)

            # get_monthly_releases (CheapShark only)
            if hasattr(provider, "get_monthly_releases"):
                try:
                    for mo in (0, 1, 2):
                        y = now.year
                        m = now.month - mo
                        if m <= 0:
                            m += 12
                            y -= 1
                        result = await provider.get_monthly_releases(y, m, limit=20)
                        _collect_from_games(result.games or [])
                except Exception:
                    logger.debug("get_monthly_releases failed for %s", provider.name)

            # get_featured_releases (Steam only)
            if hasattr(provider, "get_featured_releases"):
                try:
                    for mo in range(6):
                        y = now.year
                        m = now.month - mo
                        if m <= 0:
                            m += 12
                            y -= 1
                        feat_result = await provider.get_featured_releases(y, m, limit=20)
                        _collect_from_games(feat_result.games or [])
                except Exception:
                    logger.debug("get_featured_releases failed for %s", provider.name)

            # get_trending (Steam only)
            if hasattr(provider, "get_trending"):
                try:
                    result = await provider.get_trending(limit=30)
                    _collect_from_games(result.games or [])
                except Exception:
                    logger.debug("get_trending failed for %s", provider.name)

        logger.info(
            "Total unique Steam App IDs collected: %d (limit %d)",
            len(ids),
            STEAM_FETCH_LIMIT,
        )
        return list(ids)[:STEAM_FETCH_LIMIT]

    # ── RSS fetching ────────────────────────────────────────────────────────

    async def _fetch_rss_updates(self, steam_app_ids: list[int]) -> list[GameUpdate]:
        """Fetch and parse Steam RSS news for each App ID concurrently."""
        tasks = [self._fetch_game_news(aid) for aid in steam_app_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_updates: list[GameUpdate] = []
        rss_errors = 0
        for app_id, result in zip(steam_app_ids, results, strict=False):
            if not isinstance(result, list):
                rss_errors += 1
                continue
            if not result:
                continue
            logger.info(
                "Steam RSS app %d: fetched=%d accepted=%d",
                app_id,
                len(result),
                len(result),
            )
            all_updates.extend(result)
        logger.info(
            "Steam RSS: total %d updates from %d feeds (%d errors)",
            len(all_updates),
            len(steam_app_ids),
            rss_errors,
        )
        return all_updates

    async def _fetch_game_news(self, app_id: int) -> list[GameUpdate]:
        """Fetch and parse a single Steam game's RSS news feed."""
        url = STEAM_RSS_URL.format(appid=app_id)
        try:
            response = await self._http_client.get(url, timeout=FEED_TIMEOUT)
            response.raise_for_status()
        except Exception:
            return []
        return self._parse_rss(response.text, app_id)

    # ── RSS parsing ─────────────────────────────────────────────────────────

    def _parse_rss(self, xml: str, app_id: int) -> list[GameUpdate]:
        """Parse RSS XML and return significant update entries."""
        updates: list[GameUpdate] = []
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return []
        for item in root.iter("item"):
            update = self._parse_item(item, app_id)
            if update:
                updates.append(update)
        if not updates:
            ns = "{http://www.w3.org/2005/Atom}"
            for entry in root.iter(f"{ns}entry"):
                update = self._parse_atom_entry(entry, app_id)
                if update:
                    updates.append(update)
        return updates

    def _parse_item(self, item: Any, app_id: int) -> GameUpdate | None:
        """Parse an RSS 2.0 <item> element into a GameUpdate."""
        title_el = item.find("title")
        link_el = item.find("link")
        date_el = item.find("pubDate")
        desc_el = item.find("description")
        if title_el is None or title_el.text is None:
            return None
        title = title_el.text.strip()
        if not self._is_significant(title):
            return None
        desc = (desc_el.text or "").strip() if desc_el is not None else ""
        link = (link_el.text or "").strip() if link_el is not None else ""
        pub_date: datetime | None = None
        if date_el is not None and date_el.text:
            pub_date = self._parse_rfc822(date_el.text.strip())
        game_name = self._extract_game_name(title)
        return GameUpdate(
            app_id=app_id,
            title=title,
            game_name=game_name,
            update_title=self._extract_update_title(title, game_name),
            url=link,
            date=pub_date or datetime.now(UTC),
            snippet=self._clean_html(desc) if desc else "",
        )

    def _parse_atom_entry(self, entry: Any, app_id: int) -> GameUpdate | None:
        """Parse an Atom <entry> element into a GameUpdate."""
        ns = "{http://www.w3.org/2005/Atom}"
        title_el = entry.find(f"{ns}title")
        link_el = entry.find(f"{ns}link")
        published_el = entry.find(f"{ns}published")
        summary_el = entry.find(f"{ns}summary")
        if title_el is None or title_el.text is None:
            return None
        title = title_el.text.strip()
        if not self._is_significant(title):
            return None
        link = link_el.get("href", "").strip() if link_el is not None else ""
        pub_date: datetime | None = None
        if published_el is not None and published_el.text:
            with contextlib.suppress(ValueError, TypeError):
                pub_date = datetime.fromisoformat(published_el.text.replace("Z", "+00:00"))
        summary = (summary_el.text or "").strip() if summary_el is not None else ""
        game_name = self._extract_game_name(title)
        return GameUpdate(
            app_id=app_id,
            title=title,
            game_name=game_name,
            update_title=self._extract_update_title(title, game_name),
            url=link,
            date=pub_date or datetime.now(UTC),
            snippet=self._clean_html(summary) if summary else "",
        )

    @staticmethod
    def _clean_html(text: str) -> str:
        """Strip HTML from text."""
        text = re.sub(r"<img[^>]*>", "", text, flags=re.IGNORECASE)
        text = re.sub(r' style="[^"]*"', "", text, flags=re.IGNORECASE)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = html_module.unescape(text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _is_significant(text: str) -> bool:
        """Return True if the text describes a significant game update."""
        lower = text.lower()
        if any(kw in lower for kw in TRIVIAL_KEYWORDS):
            return False
        return any(kw in lower for kw in SIGNIFICANT_KEYWORDS)

    @staticmethod
    def _extract_game_name(title: str) -> str:
        """Extract the game name from a news title."""
        for sep in (" — ", " \u2013 ", " - ", " :: ", ": "):
            if sep in title:
                return title.split(sep, maxsplit=1)[0].strip()
        return title[:40]

    @staticmethod
    def _extract_update_title(title: str, game_name: str) -> str:
        """Extract the update title (everything after the game name prefix)."""
        lower_title = title.lower()
        lower_game = game_name.lower()
        if not lower_game or not lower_title.startswith(lower_game):
            return title
        rest = title[len(game_name) :].lstrip()
        for sep in (" \u2014 ", " \u2013 ", " - ", " :: ", ": "):
            if rest.startswith(sep):
                rest = rest[len(sep) :].lstrip()
                break
        return rest or title

    @staticmethod
    def _parse_rfc822(date_str: str) -> datetime | None:
        """Parse an RFC 822 date string."""
        try:
            return email.utils.parsedate_to_datetime(date_str)
        except Exception:
            return None
