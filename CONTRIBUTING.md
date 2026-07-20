# Contributing

Thank you for your interest in contributing to the Discord Gaming Automation Hub!

## Code of Conduct

This project follows common open-source etiquette. Be respectful, constructive, and inclusive.

## Getting Started

1. Fork the repository.
2. Clone your fork.
3. Run `make bootstrap` to set up the development environment.
4. Create a feature branch: `git checkout -b feat/your-feature-name`.

## Development Workflow

```bash
# Install dev dependencies
make install-dev

# Run tests
make test

# Run linter
make lint

# Format code
make format

# Run type checker
make typecheck

# Run full quality gate
make check
```

## Guidelines

- Read `AGENTS.md` for architectural rules.
- Read the relevant `docs/roadmap/` phase before starting implementation.
- Write tests for every new module.
- Update `CHANGELOG.md` under `[Unreleased]`.
- Update `docs/architecture/` if your change affects the design.
- Update `.env.example` if you add new configuration.

## Commit Messages

Use conventional commits:

- `feat: add search autocomplete endpoint`
- `fix: handle CheapShark 429 rate limit response`
- `docs: update database phase roadmap`
- `refactor: extract price formatting to utils`
- `test: add discount service unit tests`
- `chore: update ruff configuration`

## Pull Request Process

1. Ensure `make check` passes.
2. Update documentation if needed.
3. Add a changelog entry.
4. Open the PR with a clear description of the change.
