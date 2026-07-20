# Discord UI Components

Centralized builders for Discord embeds, views, and components.

## Why Centralized?

- **Consistent branding**: All commands and automatic channels share colors,
  footer styles, and formatting.
- **Reusability**: A deal embed used by `/search` is reused by `#crazy-discounts`.
- **Easier iteration**: Visual tweaks happen in one place.

## Planned Components

- `embeds.py` : GameEmbed, DealEmbed, SaleEmbed, HelpEmbed.
- `views.py` : PaginatorView, DealDetailsView, FilterSelectView.
