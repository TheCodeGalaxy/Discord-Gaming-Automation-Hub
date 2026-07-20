# Automation Layer

Thin orchestration layer that speaks to n8n and any future schedulers.

## Why Separate Automation?

- **Single responsibility**: Python owns business logic; n8n owns timing and wiring.
- **Testability**: Jobs can be triggered via HTTP during development without waiting for cron.
- **Flexibility**: Replacing n8n with another scheduler only requires changing this adapter.

## Jobs (Planned)

| Job | Trigger | Channel / Consumer |
|-----|---------|-------------------|
| `post_free_this_week` | Weekly cron | #free-this-week |
| `post_crazy_discounts` | Hourly cron | #crazy-discounts |
| `post_top_this_week` | Weekly cron | #top-this-week |
| `post_major_updates` | Daily cron | #major-updates |
| `post_coming_soon` | Daily cron | #coming-soon |
| `calendar_sync` | Daily cron | Google Calendar + Discord |

## Security

Webhook endpoints validate ``N8N_WEBHOOK_SECRET`` via HMAC signature and restrict
source IPs to ``API_TRUSTED_HOSTS``.
