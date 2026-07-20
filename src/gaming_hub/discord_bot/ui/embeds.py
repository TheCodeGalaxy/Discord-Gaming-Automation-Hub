"""Discord embed builders.

Each public function accepts domain objects and returns a ``discord.Embed``.
Builders live here so the bot and automatic channels share visual styles.
"""

# TODO: Cross-reference roadmap phase 19 (Discord Slash Commands)

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from discord import Embed

    from gaming_hub.models.domain.deal import Deal
    from gaming_hub.models.domain.game import Game
    from gaming_hub.models.domain.sale import Sale


def build_game_embed(game: Game) -> Embed:
    """TODO: Build a rich embed from a Game."""
    raise NotImplementedError("Embed builder is defined in the implementation roadmap.")


def build_deal_embed(deal: Deal) -> Embed:
    """TODO: Build a rich embed from a Deal."""
    raise NotImplementedError("Embed builder is defined in the implementation roadmap.")


def build_sale_embed(sale: Sale) -> Embed:
    """TODO: Build a rich embed from a Sale."""
    raise NotImplementedError("Embed builder is defined in the implementation roadmap.")
