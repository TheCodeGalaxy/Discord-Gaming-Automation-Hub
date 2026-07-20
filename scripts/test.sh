#!/usr/bin/env bash
# =============================================================================
# Run the full test suite with coverage.
# Usage: ./scripts/test.sh [pytest-args]
# =============================================================================

set -euo pipefail

echo "==> Running test suite..."
python -m pytest "$@"
