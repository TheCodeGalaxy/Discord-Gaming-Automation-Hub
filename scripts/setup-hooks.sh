#!/usr/bin/env bash
# =============================================================================
# Install pre-commit hooks for the project.
# Usage: ./scripts/setup-hooks.sh
# =============================================================================

set -euo pipefail

echo "==> Installing pre-commit hooks..."
pre-commit install --hook-type pre-commit --hook-type pre-push
echo "==> Hooks installed successfully."
echo "==> Run 'pre-commit run --all-files' to check everything manually."
