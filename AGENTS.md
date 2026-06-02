# AGENTS.md — AI Council Code Review Project

> **Purpose:** This document contains the conventions, workflows, and context that coding agents need to work effectively on this repository. This is the agent-focused companion to `README.md`.

---

## 1. Project Overview

**AI Council Code Review** is a configurable, multi-agent AI code review system for GitHub Actions. It runs specialized LangGraph/LangChain agents to review pull requests, with the key differentiator being **cross-file awareness**: agents can browse the repository in real-time to check unchanged files for consistency.

**Key Constraints:**
- v1 is **stateless** — no persistence layer, no vector store, no graph DB
- **Language-agnostic** — works with any programming language
- **Multi-provider** — Fireworks.ai default, with OpenAI and Anthropic as first-class options
- **Cost-controlled** — configurable $5.00 per-PR budget, skip on forks by default

---

## 2. Technology Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.11+ |
| **Orchestration** | LangGraph |
| **LLM Interface** | LangChain |
| **Providers** | Fireworks.ai (default), OpenAI, Anthropic |
| **Package Manager** | **uv** (fast, modern — replaces pip/poetry) |
| **GitHub API** | PyGithub + raw REST |
| **Config** | Pydantic + YAML |
| **Testing** | pytest + pytest-asyncio |
| **Linting** | ruff |
| **Type Checking** | mypy |
| **Logging** | structlog |

---

## 3. Development Setup

### 3.1 Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed

### 3.2 Install Dependencies

```bash
# Clone and enter the repo
git clone <repo-url>
cd ai-council-code-review

# Install project + dev dependencies using uv
uv pip install -e ".[dev]"

# Or install into a virtual environment
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### 3.3 Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/ai_council_review --cov-report=term-missing

# Run specific test file
pytest tests/test_config.py -v
```

### 3.4 Lint & Type Check

```bash
# Lint with ruff
ruff check .
ruff format .

# Type check with mypy
mypy src/ai_council_review
```

---

## 4. Git Workflow & Branching Strategy

### 4.1 Branch Model: GitHub Flow (Simplified)

We use a **two-branch model** with short-lived feature branches:

```
main        ← Production-ready, protected, requires PR review
  │
  ├── feature/the-feature    ← Feature branches from main
  ├── bugfix/the-bugfix      ← Bugfix branches from main
  ├── hotfix/urgent-fix      ← Hotfix branches (rare)
  └── docs/readme-update     ← Documentation branches
```

**Key Rules:**
- `main` is the **only long-lived branch** and is always deployable
- All work happens on short-lived feature/bugfix branches
- No `develop` branch — we keep it simple with trunk-based development
- All changes to `main` go through **Pull Request + review**
- Branch names follow the pattern: `type/descriptive-name`

### 4.2 Branch Naming Conventions

| Prefix | Use Case | Example |
|--------|----------|---------|
| `feature/` | New functionality | `feature/multi-agent-council` |
| `bugfix/` | Bug fixes | `bugfix/patch-position-calc` |
| `hotfix/` | Critical production fixes | `hotfix/security-oauth-fix` |
| `docs/` | Documentation only | `docs/config-examples` |
| `refactor/` | Code refactoring | `refactor/extract-browser-tool` |
| `test/` | Test additions/improvements | `test/agent-router-coverage` |

### 4.3 Commit Message Format

Use **Conventional Commits**:

```
<type>: <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `style:` — Formatting, no code change
- `refactor:` — Code refactoring
- `test:` — Adding or fixing tests
- `chore:` — Build, deps, CI changes
- `ci:` — CI/CD configuration changes

**Examples:**
```
feat: add repository browser tool for cross-file awareness
fix: correct patch position calculation for inline comments
docs: update AGENTS.md with branching strategy
refactor: extract LLM provider factory into separate module
test: add unit tests for synthesis agent deduplication
```

### 4.4 Pull Request Process

1. **Create branch:** `git checkout -b feature/my-feature main`
2. **Make commits:** Small, focused commits with clear messages
3. **Push branch:** `git push origin feature/my-feature`
4. **Open PR:** Target `main`, fill out PR template
5. **Ensure CI passes:** All tests, lint, type checks must be green
6. **Request review:** At least one approval required
7. **Merge:** Use "Squash and merge" or "Rebase and merge" (no merge commits)

### 4.5 PR Description Template

```markdown
## Summary
Brief description of what this PR does.

## Changes
- Change 1
- Change 2

## Testing
- [ ] Unit tests added/updated
- [ ] Tested on a real PR (if applicable)
- [ ] Manual testing steps

## Checklist
- [ ] Code follows project conventions (AGENTS.md)
- [ ] Self-review completed
- [ ] No secrets or hardcoded keys
- [ ] Documentation updated (if needed)
```

---

## 5. Code Conventions

### 5.1 Python Style

- **Formatter:** ruff (replaces black)
- **Line length:** 100 characters
- **Type hints:** Required on all function signatures, use `from __future__ import annotations`
- **Docstrings:** Google style for all public functions/classes
- **Imports:** Grouped as stdlib, third-party, local; sorted with ruff

### 5.2 Project Structure Rules

- All source code lives in `src/ai_council_review/`
- One concept per module — keep modules small and focused
- Agents live in `src/ai_council_review/agents/`
- Prompts are `.txt` files in `src/ai_council_review/prompts/` (not inline strings)
- Tests mirror the source structure under `tests/`
- No business logic in `__main__.py` — keep entry points thin

### 5.3 Configuration Conventions

- All configurable values live in Pydantic models in `config.py`
- Environment variable overrides use `AI_COUNCIL__` prefix with `__` as nested separator
- YAML config is the user-facing interface; Python config is the internal interface
- Never hardcode API keys, tokens, or URLs — always use config or env vars

### 5.4 Error Handling

- Use custom exception hierarchy in `exceptions.py`
- All GitHub API calls must have retry logic with exponential backoff
- Never swallow exceptions silently — log them with `structlog`
- Graceful degradation: if one agent fails, others continue

---

## 6. CI/CD

### 6.1 Project Workflows (`.github/workflows/`)

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | PR to `main`, push to `main` | Run tests, lint, type check |
| `ai-council-review.yml` | PR to `main` | Self-dogfood — run our own review action on this repo |

### 6.2 CI Requirements

All PRs must pass:
- [ ] `pytest` — all tests green
- [ ] `ruff check .` — no lint errors
- [ ] `ruff format --check .` — no formatting issues
- [ ] `mypy src/ai_council_review` — no type errors

### 6.3 Self-Dogfooding

We run our own AI Council Review action on this repository. This is both:
1. **Quality assurance** — our own code gets reviewed
2. **Integration testing** — we test the action on real PRs

---

## 7. Testing Strategy

### 7.1 Test Organization

```
tests/
├── test_config.py              # Config loading and validation
├── test_github_client.py       # GitHub API client (mocked)
├── test_repository_browser.py  # File reading tools
├── test_pr_ingestor.py         # PR metadata ingestion
├── test_agents/
│   ├── test_router.py          # Router agent logic
│   ├── test_security.py        # Security agent
│   ├── test_quality.py         # Quality agent
│   ├── test_architecture.py    # Architecture agent
│   └── test_synthesis.py       # Synthesis agent
└── fixtures/
    ├── pr_payload.json
    ├── changed_files.json
    └── config.yaml
```

### 7.2 Testing Principles

- **Mock external APIs:** Use `respx` for HTTP, `pytest-asyncio` for async
- **Test agent prompts:** Ensure prompt templates render correctly with context
- **Test patch parsing:** Use real diff samples from GitHub to verify position calculation
- **Test config validation:** Ensure invalid configs raise clear errors
- **Test error paths:** Agents should fail gracefully, not crash the workflow

### 7.3 Fixtures

- `pr_payload.json` — A real GitHub PR event payload (anonymized)
- `changed_files.json` — Sample PR file list with patches
- `config.yaml` — A complete but minimal valid configuration

---

## 8. Agent Conventions for This Project

When working on this codebase, agents should follow these principles:

### 8.1 Before Writing Code
1. Read `reference.md` for the full spec
2. Read `AGENTS.md` (this file) for conventions
3. Check the current branch — start from `main` if not specified
4. Look at existing code in the same module to match style

### 8.2 While Writing Code
1. **Small, pure functions** — one responsibility per function
2. **Type hints everywhere** — no untyped public APIs
3. **Structured logging** — use `structlog` instead of `print` or `logging`
4. **Pydantic for data** — all state objects, configs, and API responses are Pydantic models
5. **LangGraph patterns** — follow LangGraph conventions for state, nodes, and edges

### 8.3 Before Committing
1. Run tests: `pytest`
2. Run lint: `ruff check .`
3. Run type check: `mypy src/ai_council_review`
4. Review your own diff — remove debug prints, TODOs, and commented code

### 8.4 Documentation
- Update `AGENTS.md` if you change conventions, workflows, or tooling
- Update `README.md` if you change user-facing behavior
- Add docstrings to all public APIs
- Keep comments minimal and purposeful — "why" not "what"

---

## 9. Secrets & Environment

### 9.1 Required Secrets (for this repo's CI)

| Secret | Purpose | Required? |
|--------|---------|-----------|
| `FIREWORKS_API_KEY` | Default LLM provider | Yes (for self-dogfooding) |
| `OPENAI_API_KEY` | Alternative LLM provider | No |
| `ANTHROPIC_API_KEY` | Alternative LLM provider | No |

### 9.2 Local Development

Create a `.env` file (gitignored) for local testing:

```bash
# .env — NEVER commit this file
FIREWORKS_API_KEY=fw-xxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
GITHUB_TOKEN=ghp_xxxxxxxx   # For local GitHub API testing
```

Load with `python-dotenv` in test scripts.

---

## 10. Common Tasks

### 10.1 Adding a New Agent

1. Create `src/ai_council_review/agents/<agent_name>.py`
2. Inherit from `BaseAgent` (see `agents/base.py`)
3. Add prompt template to `src/ai_council_review/prompts/<agent_name>.txt`
4. Add agent config to `config.py` (Pydantic model)
5. Add agent to the default config YAML
6. Register agent in `graph.py`
7. Add tests in `tests/test_agents/test_<agent_name>.py`
8. Update `reference.md` agent documentation

### 10.2 Adding a New LLM Provider

1. Add `langchain-<provider>` to `pyproject.toml` dependencies
2. Add provider config to `config.py`
3. Add provider to `providers` section in default config YAML
4. Update `LLMProviderFactory` in `llm_provider.py`
5. Add provider to workflow env vars
6. Update tests

### 10.3 Adding a New Tool to RepositoryBrowser

1. Add method to `RepositoryBrowser` class in `repository_browser.py`
2. Add tool to agent's tool list in the agent's `get_tools()` method
3. Update tests in `tests/test_repository_browser.py`
4. Update `reference.md` if behavior is user-facing

---

## 11. Troubleshooting

| Problem | Solution |
|---------|----------|
| `uv` not found | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Tests fail with import errors | Run `uv pip install -e ".[dev]"` |
| `ruff` format conflicts | Run `ruff format .` before committing |
| `mypy` errors on LangChain types | Add `# type: ignore` for known upstream issues, document in comment |
| Mock GitHub API failing | Check `respx` mock URLs match exactly (including trailing slashes) |

---

*Document version: 1.0*
*Date: 2026-06-02*
*Status: Living document — update when conventions change*
