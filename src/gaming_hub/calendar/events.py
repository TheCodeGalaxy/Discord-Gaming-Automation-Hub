"""Seasonal gaming events with approximate annual date ranges.

These events follow recurring calendar patterns (e.g. "third week of June")
and are defined once per year.  The callers pass a year and receive
concrete ``date`` ranges for that year's events.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, order=True)
class SeasonalEvent:
    """A single major gaming event with computed dates for a given year."""

    slug: str
    title: str
    description: str
    url: str
    color_id: int
    approximate_start_month: int
    approximate_start_day: int
    approximate_end_month: int
    approximate_end_day: int
    year: int

    @classmethod
    def from_pattern(  # noqa: PLR0913
        cls,
        slug: str,
        title: str,
        description: str,
        url: str,
        color_id: int,
        *,
        year: int,
        start_month: int,
        start_day: int,
        end_month: int,
        end_day: int,
    ) -> SeasonalEvent:
        """Create a seasonal event with explicit date components for *year*."""
        return cls(
            slug=slug,
            title=title,
            description=description,
            url=url,
            color_id=color_id,
            approximate_start_month=start_month,
            approximate_start_day=start_day,
            approximate_end_month=end_month,
            approximate_end_day=end_day,
            year=year,
        )

    @property
    def start_date(self) -> date:
        """Return the event's start date for this year."""
        try:
            return date(self.year, self.approximate_start_month, self.approximate_start_day)
        except ValueError:
            return date(self.year, self.approximate_start_month, 1)

    @property
    def end_date(self) -> date:
        """Return the event's end date for this year."""
        try:
            return date(self.year, self.approximate_end_month, self.approximate_end_day)
        except ValueError:
            _, last = calendar.monthrange(self.year, self.approximate_end_month)
            return date(self.year, self.approximate_end_month, last)

    @property
    def external_id(self) -> str:
        """Return a stable unique identifier for this event and year."""
        return f"seasonal-{self.slug}-{self.year}"


# ── Event definitions (annual patterns) ──────────────────────────────────────


def seasonal_events_for_year(year: int) -> list[SeasonalEvent]:
    """Return all known seasonal gaming events for *year*.

    Dates are approximate based on historical patterns.  Official dates
    may shift slightly year to year.
    """
    return [
        # Steam seasonal sales
        SeasonalEvent.from_pattern(
            slug="steam-spring-sale",
            title="Steam Spring Sale",
            description=(
                "Steam's annual spring sales event with discounts across "
                "thousands of games. Typically runs for one week in March."
            ),
            url="https://store.steampowered.com",
            color_id=9,
            year=year,
            start_month=3, start_day=14,
            end_month=3, end_day=21,
        ),
        SeasonalEvent.from_pattern(
            slug="steam-summer-sale",
            title="Steam Summer Sale",
            description=(
                "Steam's biggest annual sales event. Thousands of games "
                "discounted across every genre. Runs for approximately "
                "two weeks starting in late June."
            ),
            url="https://store.steampowered.com",
            color_id=9,
            year=year,
            start_month=6, start_day=27,
            end_month=7, end_day=11,
        ),
        SeasonalEvent.from_pattern(
            slug="steam-autumn-sale",
            title="Steam Autumn Sale",
            description=(
                "Steam's autumn sales event running for one week in "
                "late November. Also includes the Steam Awards voting "
                "period."
            ),
            url="https://store.steampowered.com",
            color_id=9,
            year=year,
            start_month=11, start_day=27,
            end_month=12, end_day=4,
        ),
        SeasonalEvent.from_pattern(
            slug="steam-winter-sale",
            title="Steam Winter Sale",
            description=(
                "Steam's year-end sales event. Runs for approximately "
                "two weeks starting in late December. The largest sale "
                "of the year alongside the Summer Sale."
            ),
            url="https://store.steampowered.com",
            color_id=9,
            year=year,
            start_month=12, start_day=21,
            end_month=1, end_day=4,
        ),
        SeasonalEvent.from_pattern(
            slug="steam-next-fest-june",
            title="Steam Next Fest (June)",
            description=(
                "A multi-day celebration where gamers can try hundreds "
                "of upcoming game demos for free. Held three times per year; "
                "this is the June edition."
            ),
            url="https://store.steampowered.com/sale/nextfest",
            color_id=10,
            year=year,
            start_month=6, start_day=16,
            end_month=6, end_day=23,
        ),
        SeasonalEvent.from_pattern(
            slug="steam-next-fest-october",
            title="Steam Next Fest (October)",
            description=(
                "October edition of Steam's demo-festival. Try upcoming "
                "games, watch developer livestreams, and add titles to "
                "your wishlist."
            ),
            url="https://store.steampowered.com/sale/nextfest",
            color_id=10,
            year=year,
            start_month=10, start_day=14,
            end_month=10, end_day=21,
        ),
        SeasonalEvent.from_pattern(
            slug="steam-next-fest-february",
            title="Steam Next Fest (February)",
            description=(
                "February edition of Steam's demo-festival. The first "
                "Next Fest of the year featuring hundreds of playable demos."
            ),
            url="https://store.steampowered.com/sale/nextfest",
            color_id=10,
            year=year,
            start_month=2, start_day=24,
            end_month=3, end_day=3,
        ),
        # Epic Games Store sales
        SeasonalEvent.from_pattern(
            slug="epic-mega-sale",
            title="Epic Mega Sale",
            description=(
                "Epic Games Store's largest sales event. Features "
                "discounts on thousands of games plus an additional "
                "coupon on eligible purchases. Typically runs May-June."
            ),
            url="https://store.epicgames.com",
            color_id=5,
            year=year,
            start_month=5, start_day=16,
            end_month=6, end_day=13,
        ),
        SeasonalEvent.from_pattern(
            slug="epic-holiday-sale",
            title="Epic Holiday Sale",
            description=(
                "Epic Games Store's holiday sales event. Runs "
                "from mid-December through early January with daily "
                "free game giveaways."
            ),
            url="https://store.epicgames.com",
            color_id=5,
            year=year,
            start_month=12, start_day=12,
            end_month=1, end_day=2,
        ),
        # Industry events
        SeasonalEvent.from_pattern(
            slug="summer-game-fest",
            title="Summer Game Fest",
            description=(
                "A digital festival showcasing upcoming video games "
                "with livestream presentations from major publishers "
                "and developers. Kicks off in early June."
            ),
            url="https://www.summergamefest.com",
            color_id=3,
            year=year,
            start_month=6, start_day=7,
            end_month=6, end_day=13,
        ),
        SeasonalEvent.from_pattern(
            slug="gamescom",
            title="Gamescom",
            description=(
                "Europe's largest gaming event held annually in Cologne, "
                "Germany. Features major announcements, playable demos, "
                "and industry presentations."
            ),
            url="https://www.gamescom.global",
            color_id=3,
            year=year,
            start_month=8, start_day=20,
            end_month=8, end_day=25,
        ),
        SeasonalEvent.from_pattern(
            slug="tokyo-game-show",
            title="Tokyo Game Show",
            description=(
                "One of the largest video game trade shows in the world, "
                "held annually in Chiba, Japan. Features new game "
                "announcements, playable demos, and industry showcases."
            ),
            url="https://www.tokyogameshow.jp",
            color_id=3,
            year=year,
            start_month=9, start_day=26,
            end_month=9, end_day=29,
        ),
        SeasonalEvent.from_pattern(
            slug="the-game-awards",
            title="The Game Awards",
            description=(
                "Annual awards ceremony celebrating achievements in "
                "the video game industry. Features world premieres, "
                "new game announcements, and musical performances."
            ),
            url="https://thegameawards.com",
            color_id=3,
            year=year,
            start_month=12, start_day=12,
            end_month=12, end_day=12,
        ),
    ]
