# =============================================================================
# Discord Gaming Automation Hub — Developer Makefile
# =============================================================================
# This file is intentionally simple. Every target is self-documenting.
# Run `make help` to see available commands.
# =============================================================================

.PHONY: help install install-dev bootstrap lint format test test-unit test-integration cov check security build image up down logs clean docs

PYTHON := python
PIP := pip
VENV := .venv

help:  ## Show this help message.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

bootstrap:  ## Create virtual environment and install all dependencies.
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/$(PIP) install --upgrade pip setuptools wheel
	$(VENV)/bin/$(PIP) install -e ".[dev]"

install:  ## Install production dependencies (editable).
	$(PIP) install -e "."

install-dev:  ## Install development dependencies (editable).
	$(PIP) install -e ".[dev]"

lint:  ## Run ruff linter across the codebase.
	ruff check src tests scripts

format:  ## Format code with ruff.
	ruff format src tests scripts

format-check:  ## Check formatting without modifying files.
	ruff format --check src tests scripts

typecheck:  ## Run static type checking with mypy.
	mypy src

test:  ## Run the full test suite with coverage.
	pytest

test-unit:  ## Run only fast unit tests.
	pytest -m unit

test-integration:  ## Run integration tests.
	pytest -m integration

cov:  ## Open HTML coverage report (after running tests).
	python -m webbrowser htmlcov/index.html

check: lint format-check typecheck test  ## Run the complete quality gate.

security:  ## Run bandit security scan.
	bandit -r src

build:  ## Build the wheel package.
	$(PIP) install build
	$(PYTHON) -m build

image:  ## Build the production Docker image.
	docker build --target runtime -t gaming-hub:latest .

up:  ## Start the full Docker Compose stack.
	docker compose up --build -d

down:  ## Stop the Docker Compose stack.
	docker compose down

logs:  ## Tail logs of the gaming-hub container.
	docker compose logs -f gaming-hub

clean:  ## Remove generated artifacts.
	rm -rf .venv build dist *.egg-info .pytest_cache .mypy_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

docs:  ## Serve documentation locally (requires mkdocs; optional).
	mkdocs serve
