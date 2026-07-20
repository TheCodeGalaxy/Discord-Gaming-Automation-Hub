# n8n Workflows for Gaming Hub

This directory contains [n8n](https://n8n.io/) workflow JSON exports for
calendar synchronisation. The five poster channels are now scheduled
**internally** by the bot's `ChannelScheduler` — no n8n cron workflows are
needed for them.

## Workflow Overview

| File | Schedule | Action | Consumer |
|------|----------|--------|----------|
| `calendar-sync.json` | Daily 03:00 UTC | `calendar_sync` | Google Calendar |
| `calendar-reminders.json` | Every hour | `calendar_reminders` | Google Calendar |

## Import Instructions

1. Open your n8n web UI.
2. Go to **Workflows** → **Import from File**.
3. Select one of the JSON files above.
4. Activate the workflow.

## Testing

To test the full pipeline run the bot in test mode:

```env
TEST_MODE=true
```

This publishes every poster channel exactly once on startup regardless
of schedule. See `.env.example` for details.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Calendar workflow fails with 401 | HMAC secret mismatch | Run `docker compose exec n8n node -e "console.log(process.env.N8N_WEBHOOK_SECRET)"` and compare with `settings.n8n_webhook_secret` in the backend logs |
| Poster not showing | `ChannelScheduler` evaluated the period as already published | Check `data/scheduler.db` via `sqlite3 data/scheduler.db "SELECT * FROM publication_history;"` |
