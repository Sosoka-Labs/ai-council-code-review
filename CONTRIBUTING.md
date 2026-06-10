# Contributing to AI Council Code Review

Thank you for your interest in contributing! This document covers the basics of getting started.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — the project's package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

## Environment Setup

Create a `.env` file in the project root (it is gitignored) with at least one provider API key:

```bash
# .env — NEVER commit this file
GITHUB_TOKEN=ghp_xxxxxxxx        # Required for GitHub API calls
FIREWORKS_API_KEY=fw-xxxxxxxx    # At least one provider key is required
# OPENAI_API_KEY=sk-xxxxxxxx
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
```

For a full list of environment variables and configuration options, see [AGENTS.md](AGENTS.md).

## Getting Started

1. Fork the repository and clone your fork.
2. Install dependencies:
   ```bash
   uv pip install -e ".[dev]"
   ```
3. Run the test suite:
   ```bash
   pytest
   ```
4. Run lint and type check:
   ```bash
   ruff check .
   mypy src/ai_council_review
   ```

## Branching and Commits

- Create a feature branch from `main`:
  ```bash
  git checkout -b feature/my-feature main
  ```
- Use [Conventional Commits](https://www.conventionalcommits.org/):
  - `feat:` — New feature
  - `fix:` — Bug fix
  - `docs:` — Documentation only
  - `refactor:` — Code refactoring
  - `test:` — Adding or fixing tests
  - `chore:` — Build, deps, CI changes
  - `ci:` — CI/CD configuration changes

## Pull Request Process

1. Ensure all tests pass, lint is clean, and type check is green.
2. Update documentation if your change affects user-facing behavior.
3. Fill out the PR template (if applicable).
4. Request review from maintainers.

## Code Style

- **Formatter:** ruff
- **Line length:** 100 characters
- **Type hints:** Required on all public functions
- **Docstrings:** Google style
- **Imports:** Grouped as stdlib, third-party, local; sorted with ruff

## Development Philosophy

- Small, pure functions with single responsibility
- Pydantic for all data models and configuration
- Structured logging with `structlog` instead of `print`
- No business logic in `__main__.py` — keep entry points thin

## Questions?

Open a [GitHub Discussion](https://github.com/Sosoka-Labs/ai-council-code-review/discussions) or reach out via issue.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
