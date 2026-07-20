# Database Layer

SQLite-backed persistence via SQLAlchemy 2.0 (async engine).

## Why SQLite?

- **Zero cost**: No separate database container.
- **Zero configuration**: File-based storage inside `./data`.
- **Sufficient workload**: The hub is single-tenant and read-heavy.

## Migrations

Alembic will manage schema changes. Migration files live in `alembic/` at the
project root once the database phase begins.

## Tables (Planned)

| Table | Responsibility |
|-------|--------------|
| `games` | Cached normalized game records |
| `deals` | Cached deal snapshots |
| `sales` | Seasonal sales and calendar events |
| `user_preferences` | Per-Discord-user overrides |
| `suggestion_history` | `/surprise` rotation state |
| `automation_log` | Audit trail of scheduled posts |

## Notes

- The `database_url` setting supports `sqlite+aiosqlite:///...` for async usage.
- Heavy write concurrency is not expected; SQLite WAL mode will be enabled for
  better read concurrency.
