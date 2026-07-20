# API Routers

FastAPI routers compose the internal HTTP surface.

## Existing

- `health.py` : Docker health check and uptime probe.

## Planned

- `n8n.py` : Webhook receiver for automation triggers.
- `commands.py` : REST-style invocation of Discord commands (optional).
- `metrics.py` : Prometheus-compatible metrics (optional).

## Design Notes

- Routers must not contain business logic; they delegate to services.
- n8n webhooks validate signatures and source IPs before dispatch.
