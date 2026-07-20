# Cache Layer

Backends implemented in the roadmap cache phase.

## Planned Backends

- `memory` : Asyncio-safe in-process dict for local/Single-container deployments.
- `sqlite` : Persistent cache table inside the application SQLite database.
- `redis` : Optional external cache for advanced deployments (requires Redis).

## Design

All backends implement `gaming_hub.core.interfaces.CacheBackend`.
The application serializes domain objects with a shared codec and stores raw
bytes. Keys are prefixed with provider or service namespaces to avoid collisions.

## Responsibilities

- Reduce outbound provider requests.
- Protect providers from redundant load.
- Provide stable response times for Discord interactions.
