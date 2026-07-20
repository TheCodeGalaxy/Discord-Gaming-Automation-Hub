#!/usr/bin/env bash
# =============================================================================
# Bootstrap script — Full project setup for local development.
# Usage: ./scripts/bootstrap.sh
# =============================================================================

set -euo pipefail

echo "==> Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "==> Upgrading pip..."
pip install --upgrade pip setuptools wheel

echo "==> Installing project with dev dependencies..."
pip install -e ".[dev]"

echo "==> Installing pre-commit hooks..."
pre-commit install

echo "==> Copying .env.example to .env (if not exists)..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "==> !!! Edit .env with your Discord bot token and other settings."
else
    echo "==> .env already exists, skipping."
fi

echo "==> Creating data directories..."
mkdir -p data logs n8n/workflows n8n/credentials

echo "==> Bootstrap complete. Run 'source .venv/bin/activate' to start."
echo "==> Then run 'python -m gaming_hub' or 'make test' to verify."
