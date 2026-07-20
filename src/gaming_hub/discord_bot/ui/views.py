"""Discord UI views (pagination, buttons, select menus).

Views are independent of business logic and only carry interaction state.
"""

# TODO: Cross-reference roadmap phase 19 (Discord Slash Commands)

from __future__ import annotations


def build_pagination_view(*, current_page: int, total_pages: int) -> None:
    """TODO: Build a pagination view for long result lists."""
    raise NotImplementedError("Pagination view is defined in the implementation roadmap.")
