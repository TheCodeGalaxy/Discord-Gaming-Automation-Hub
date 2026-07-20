#!/usr/bin/env bash
# =============================================================================
# Docker development entrypoint.
# Starts the FastAPI server and/or Discord bot depending on configuration.
# =============================================================================

set -euo pipefail

echo "==> GamingHub development entrypoint starting..."
echo "==> Environment: ${ENVIRONMENT:-development}"

# Enable live reload in development
if [ "${ENVIRONMENT:-development}" = "development" ]; then
    echo "==> Starting with live reload..."
    exec uvicorn gaming_hub.api.app:create_app \
        --host "${API_HOST:-0.0.0.0}" \
        --port "${API_PORT:-8000}" \
        --reload \
        --factory
else
    echo "==> Starting production server..."
    exec uvicorn gaming_hub.api.app:create_app \
        --host "${API_HOST:-0.0.0.0}" \
        --port "${API_PORT:-8000}" \
        --factory
fi
