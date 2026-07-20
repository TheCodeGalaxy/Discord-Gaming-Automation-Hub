#!/usr/bin/env bash
# =============================================================================
# Run all linters and formatters.
# Usage: ./scripts/lint.sh [--fix]
# =============================================================================

set -euo pipefail

FIX="${1:-}"

echo "==> Running ruff check..."
if [ "$FIX" = "--fix" ]; then
    ruff check --fix src tests scripts
    ruff format src tests scripts
else
    ruff check src tests scripts
    ruff format --check src tests scripts
fi

echo "==> Running mypy..."
mypy src

echo "==> Lint complete."
