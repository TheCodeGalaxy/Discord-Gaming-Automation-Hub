# Discord Bot Layer

Bridge between Discord interactions and application services.

## Structure

- `bot.py` : Client lifecycle and command registration.
- `commands/` : Slash command definitions (`/help`, `/search`, `/free`, etc.).
- `events/` : Discord event handlers.
- `ui/` : Embeds, views, and reusable components.

## Design Rules

- Bot code never calls providers directly.
- Commands validate input, invoke services, and render responses.
- Error handlers translate service exceptions into user-friendly messages.
- Automatic channel posters reuse command/service results.
