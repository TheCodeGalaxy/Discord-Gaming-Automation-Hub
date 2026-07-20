# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **RAWG provider** (`data/providers/rawg.py`): New provider adapter for
  `rawg.io` — the largest open video game database. Provides release dates,
  ratings, and popularity-based ordering for `/new` and `#coming-soon`.
  Requires a free API key (`RAWG_API_KEY` in `.env`). Without the key every
  method returns an empty result (graceful degradation). Free tier: 20 000
  requests/month. Sign up at https://rawg.io/register/developer.
- **Steam trending** (`steam.py` → `get_trending`): Now collected by `NewReleasesService`
  for both `/new` and `#coming-soon`. Trending games gain release dates through
  appdetails enrichment; the post-enrichment window filter removes out-of-window
  games. Source: `steamcommunity.com/trending` HTML page.
- **Epic catalog** (`epic.py` → `get_upcoming_releases`): Now collected by
  `get_upcoming()` for the `/new` rolling 3-month window (previously only
  `get_current_month()` used it).
- **Post-enrichment window filter**: Both `get_upcoming()` and `get_current_month()`
  now re-filter all collected games after Steam enrichment, catching games that
  arrived without release dates (trending, ITAD) and were enriched with dates
  outside the target window.
- **`GameUpdate.update_title`**: New field storing the update title portion (after
  game name prefix extraction). Used as the embed title in `#major-updates`.

### Changed
- **CheapShark** (`cheapshark.py`): `get_new_releases` and `get_monthly_releases`
  pages increased from 2 to 5 (120 → 300 deals per call). Sleep increased from
  1.5s to 2.0s to reduce rate-limit risk.
- **`_merge_metadata`**: `raw_metadata` merge logic changed from replace-only
  (`if source.raw_metadata and not target.raw_metadata`) to merge/update
  (`if source.raw_metadata: target.raw_metadata.update(...)`). Fixes a bug where
  pre-populated raw_metadata (e.g. Steam trending) blocked appdetails enrichment.
- **Coming Soon** (`get_current_month`): No longer uses `_spread_across_month`.
  Now sorts by `_significance_score` descending and returns top `limit` games.
  Removes week-based date spreading so ranking is purely by popularity.
- **Major Updates** (`major_updates.py`): Embed title changed from full RSS title
  (`"Game Name — Update Title"`) to extracted update title (`"Update Title"`)
  via `GameUpdate.update_title`. The game name is still shown in the "Game" field.
- **`.env`**: `MONTHLY_FORCE_REFRESH` set to `false` (was `true`), preventing
  force-republish of monthly channels on every startup.

### Logging Added
- Per-provider `fetched/accepted/rejected` counts in every collection method.
- Rejection reason breakdowns (`invalid_date`, `too_old`, `too_future`) via
  `_ingest()`.
- Post-enrichment window filter: `"pre_filter → post_filter games removed=N"`.

- **ChannelScheduler** (`discord_bot/scheduler/channel_scheduler.py`): startup-based
  scheduler that checks SQLite publication history and publishes overdue channels
  immediately. Replaces n8n cron for the five poster channels.
- **PublicationRepository**: aiosqlite-backed storage for publication history
  with weekly (`2026-W29`) and monthly (`2026-07`) period tracking.
- **`TEST_MODE`** env var: publishes every channel exactly once on startup for
  testing without waiting for scheduled dates.
- **`Settings.test_mode`** and **`Settings.database_dir`** config fields.

### Changed
- **Poster scheduling**: 5 poster channels now run on bot startup via
  `ChannelScheduler` instead of n8n cron workflows + HMAC webhooks.
- **`bot.py`**: `setup_hook()` runs `ChannelScheduler.run()` after poster init;
  `_init_scheduler()` no longer accepts `poster_registry`.
- **`JobScheduler`**: removed 5 poster handlers (`_dispatch_poster` and
  related wiring). Only calendar actions remain (`calendar_sync`,
  `calendar_reminders`).
- **`.env.example`**: added `TEST_MODE`, removed quotes from `N8N_WEBHOOK_SECRET`.
- **`.env`**: removed quotes from `N8N_WEBHOOK_SECRET` value.

### Removed
- 5 n8n poster workflow JSON files (`free-this-week.json`, `crazy-discounts.json`,
  `top-this-week.json`, `major-updates.json`, `coming-soon.json`).
- n8n dependency for poster scheduling — posters are now triggered by the
  bot-internal `ChannelScheduler` with SQLite-based period tracking.

### Fixed
- **`/search` command**: Changed empty-result check from `result.deals` to `result.games` — providers return games from `search()`, not deals. Added `build_game_search_embeds()` for game-centric embed rendering.
- **`/surprise` command**: `_safe_fetch` now falls back to `get_deals()` when `search()` returns no games, giving CheapShark/Epic data a chance to populate the surprise pool.
- **`/new` command**: Added `get_new_releases()` to CheapShark provider, which parses `releaseDate` from the deals endpoint and filters by a configurable future window.
- **ITAD provider**: The public IsThereAnyDeal API (`api.isthereanydeal.com`) has been fully deprecated (all endpoints return 404). Provider gracefully returns empty results. See `docs/roadmap/10-isthereanydeal.md`.

### Changed
- All 4 providers now read API base URLs from settings (e.g. `cheapshark_base_url`,
  `epic_base_url`) instead of hardcoded module-level constants. Module-level
  constants retained as fallback defaults for test compatibility.
- `core/constants.py`: Renamed `PROVIDER_CheapShark` to `PROVIDER_CHEAPSHARK`
  for consistent naming.
- `utils/http.py`: Removed unused `provider_retry()` decorator and
  `PROVIDER_RETRYABLE_EXCEPTIONS` tuple (retry logic is in
  `BaseHTTPProvider._request()` via `AsyncRetrying`).
- `data/providers/isthereanydeal.py`: Fixed `get_free_games()` timer to measure
  the actual work; `get_lowest_price()` now logs errors instead of silently
  returning `None`; removed `_build_query_string()` (inline query params in
  `healthcheck()`).

### Fixed
- Removed `# ruff: noqa: D102` / `D103` suppressions from cache test files;
  all test methods now have proper Google-style docstrings.
- Added `# TODO: Cross-reference roadmap phase` comments to 17 placeholder
  modules for developer navigation.
- Removed redundant `data/cache/base.py` and `data/cache/memory.py`
  (re-exports that added unnecessary indirection).

### Documentation
- Updated `docs/roadmap/07-cheapshark.md`, `08-epic.md`, `09-steam.md`,
  `10-isthereanydeal.md`, `11-cache.md` to reflect settings-driven URLs
  and interface changes.
- Updated `docs/architecture/09-scalability.md` to document in-memory cache
  stores Python objects (`Any`) rather than serialized bytes.

### Added

- **Phase 20 — Discord Automatic Channels**: 5 n8n-triggered poster modules
- **Phase 21 — n8n Automation Integration**: HMAC webhook auth
  (``automation/webhooks.py``), ``JobScheduler`` dispatching 7 actions
  (``automation/scheduler.py``), 7 n8n workflow JSON exports
  (``n8n/workflows/*.json``), ``n8n/README.md`` with import instructions,
  HMAC-integrated webhook router (``api/routers/webhooks.py``), and API
  startup wiring in ``bot.py``.
- **Phase 20 — Discord Automatic Channels**: 5 n8n-triggered poster modules
  (`#free-this-week`, `#crazy-discounts`, `#top-this-week`, `#major-updates`,
  `#coming-soon`) with ``BasePoster`` abstract class, ``PosterRegistry``,
  ``PosterResult`` dataclass, factory wiring, and n8n webhook endpoint.
  See `docs/roadmap/20-discord-automatic-channels.md`.
- Project bootstrap, architecture documentation, and implementation roadmap.
- Clean Architecture folder structure with `src/gaming_hub/` package.
- Configuration system via pydantic-settings (60+ typed settings).
- Domain models (Game, Deal, Sale, UserPreferences) and DTOs.
- Core interfaces (DataProvider, CacheBackend, UnitOfWork, DiscordAdapter, CalendarAdapter, Scheduler).
- Provider abstraction layer with registry and base class.
- Provider placeholders for CheapShark, Epic, Steam Community, IsThereAnyDeal.
- Logging bootstrap with colored/JSON output and file rotation.
- FastAPI health check endpoint.
- Docker Compose stack (gaming-hub + n8n).
- Multi-stage Dockerfile (development + runtime targets).
- Full test infrastructure (pytest, fixtures, conftest).
- Developer tooling (Makefile, ruff, mypy, pre-commit, scripts).
- 26-phase implementation roadmap covering all features.
- Comprehensive architecture documentation (10 documents).
- Software Requirements Specification (SRS).
