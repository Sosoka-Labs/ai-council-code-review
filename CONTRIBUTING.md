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
2. Check out the `develop` branch — this is the integration branch where all work lands:
   ```bash
   git checkout develop
   ```
3. Install dependencies:
   ```bash
   uv pip install -e ".[dev]"
   ```
4. Run the test suite:
   ```bash
   pytest
   ```
5. Run lint and type check:
   ```bash
   ruff check .
   mypy src/ai_council_review
   ```

## Branching and Commits

This project uses a **Gitflow-lite** model: `develop` is the integration branch, `main` is release-only.

- Create a feature branch from `develop`:
  ```bash
  git checkout -b feature/my-feature develop
  ```
- Open your pull request targeting **`develop`**, not `main`.
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
2. Open the PR against **`develop`** (not `main`). CI runs on `develop` PRs.
3. Update documentation if your change affects user-facing behavior.
4. Fill out the PR template (if applicable).
5. Request review from maintainers.

> **Note on `main`:** `main` is the release branch and is only updated when a new version is cut. Direct pushes to `main` are not accepted. Releases are tagged from `main` and handled by the maintainers.

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

## Skills

Skills (`.ai-council/skills/<name>/SKILL.md`) are a feature for downstream *consumers* of AI Council, not a requirement for contributing to the tool itself. Contributors do not need to create or maintain skills. The example skill at `.ai-council/skills/oauth-pitfalls/` lives in this repository as a dogfood demo — it is reviewed by the security agent when AI Council reviews its own PRs, and it serves as a concrete template for users adding their own project-specific skills.

## Questions?

Open a [GitHub Discussion](https://github.com/Sosoka-Labs/ai-council-code-review/discussions) or reach out via issue.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
