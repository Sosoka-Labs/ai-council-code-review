# AI Council Code Review

A configurable, multi-agent AI code review system for GitHub Actions. Unlike single-agent tools that review diffs in isolation, AI Council dispatches a council of specialized agents that can browse your repository in real time to check unchanged files for consistency, security, and architectural impact.

---

## Overview

AI Council reviews every pull request with a team of specialist agents:

| Capability | What it means for you |
|-----------|----------------------|
| **Multi-agent council** | Router, Security, Quality, Architecture, and Synthesis agents each focus on their domain |
| **Cross-file awareness** | Agents read `README.md`, tests, migrations, and dependencies to catch drift and impact |
| **Agent-attributed comments** | Every inline comment is tagged with the agent name and confidence score |
| **Cost-controlled** | Configurable per-PR budget ($5.00 default); skip on forks by default |
| **Graceful degradation** | One agent failure does not crash the workflow; others continue |
| **Multi-provider** | Fireworks.ai (default), OpenAI, and Anthropic are all first-class options |
| **Stateless** | No persistence, no vector store, no database — just the GitHub API and smart prompts |

**Why this matters:**
- A single-agent reviewer sees only the diff. AI Council's Architecture agent can check whether your `README.md` still matches the API you just changed.
- The Security agent scans for secrets and unsafe patterns, while the Quality agent checks for missing tests and edge cases.
- The Synthesis agent deduplicates and prioritizes findings so you get one coherent review, not a wall of noise.

---

## Quick Start

Add AI Council to any repository in three steps:

### 1. Add the workflow

Copy this file to `.github/workflows/ai-council-review.yml`:

```yaml
name: AI Council Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    branches: [main, master, develop]

permissions:
  contents: read
  pull-requests: write

concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  ai-review:
    name: AI Council Review
    runs-on: ubuntu-latest
    timeout-minutes: 15
    if: github.event.pull_request.draft == false

    steps:
      - name: Checkout PR HEAD
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 0

      - name: Fetch base branch
        run: git fetch origin ${{ github.event.pull_request.base.ref }} --depth=100

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          version: '0.6.0'

      - name: Install dependencies
        run: |
          uv pip install --system -e .

      - name: Run AI Council Review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          REPO: ${{ github.repository }}
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
          BASE_REF: ${{ github.event.pull_request.base.ref }}
          HEAD_REF: ${{ github.event.pull_request.head.ref }}
          FIREWORKS_API_KEY: ${{ secrets.FIREWORKS_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          python -m ai_council_review \
            --pr-number "$PR_NUMBER" \
            --repo "$REPO" \
            --base-sha "$BASE_SHA" \
            --head-sha "$HEAD_SHA" \
            --base-ref "$BASE_REF" \
            --head-ref "$HEAD_REF"
```

### 2. Add your API key

In your repository settings, go to **Settings > Secrets and variables > Actions** and add at least one of:

- `FIREWORKS_API_KEY` — recommended default
- `OPENAI_API_KEY` — alternative
- `ANTHROPIC_API_KEY` — alternative

### 3. (Optional) Customize behavior

Add `.ai-council/config.yaml` to your repository root to customize agents, models, and rules. See [Configuration](#configuration) and the [example config](examples/.ai-council/config.yaml).

That's it. Open a pull request and AI Council will post a review.

---

## Configuration

AI Council looks for `.ai-council/config.yaml` in the repository root (on the base branch). If the file is missing, sensible defaults are used.

### Complete example

```yaml
version: "1"

# ── Review Settings ───────────────────────────────────
review_depth: standard          # "standard" or "deep"
max_files: 50                   # Skip PRs with more than this many files
max_lines: 2000                 # Skip PRs with more than this many changed lines
max_diff_size: 50000            # Skip PRs with diff larger than this (bytes)
comment_on_forks: false         # Skip commenting on fork PRs by default
skip_drafts: true               # Skip draft PRs
skip_labels:                    # Skip PRs with any of these labels
  - "skip-ai-review"
  - "wip"
skip_patterns:                  # Skip files matching these patterns
  - "package-lock.json"
  - "yarn.lock"
  - "poetry.lock"
  - "Cargo.lock"
  - "Gemfile.lock"
  - "*.snap"
  - "dist/"
  - "build/"
  - "node_modules/"

# ── Cost & Timeout Control ──────────────────────────
budget_usd: 5.00                # Max estimated cost per PR
agent_timeout_seconds: 300      # Per-agent timeout (5 minutes)
total_timeout_seconds: 600      # Overall workflow timeout (10 minutes)
debug: false                    # Dump debug artifact when true
rate_limit_threshold: 50        # Enter conservative mode below this threshold

# ── Agent Configuration ───────────────────────────────
# `model` is the provider name: fireworks, openai, or anthropic
# `model_name` is the full model identifier the provider expects
agents:
  router:
    enabled: true
    model: fireworks
    model_name: accounts/fireworks/models/llama-v3p1-70b-instruct
    temperature: 0.1
    max_tokens: 2000

  security:
    enabled: true
    model: fireworks
    model_name: accounts/fireworks/models/llama-v3p1-70b-instruct
    temperature: 0.2
    max_tokens: 4000

  quality:
    enabled: true
    model: fireworks
    model_name: accounts/fireworks/models/llama-v3p1-70b-instruct
    temperature: 0.3
    max_tokens: 4000

  architecture:
    enabled: true
    model: fireworks
    model_name: accounts/fireworks/models/llama-v3p1-70b-instruct
    temperature: 0.3
    max_tokens: 4000

  synthesis:
    enabled: true
    model: fireworks
    model_name: accounts/fireworks/models/llama-v3p1-70b-instruct
    temperature: 0.2
    max_tokens: 4000

# ── LLM Provider Settings ─────────────────────────────
# API keys are loaded from environment variables by default.
# Hardcoding them here is not recommended for public repos.

providers:
  fireworks:
    api_key: null
  openai:
    api_key: null
  anthropic:
    api_key: null
```

### Environment variable overrides

API keys can be set via environment variables:

```bash
AI_COUNCIL__FIREWORKS_API_KEY=fw-xxxxxxxx
AI_COUNCIL__OPENAI_API_KEY=sk-xxxxxxxx
AI_COUNCIL__ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
AI_COUNCIL__GITHUB_TOKEN=ghp_xxxxxxxx
```

### Override prompts

You can override any agent's system prompt by adding a `system_prompt` field to that agent's config:

```yaml
agents:
  security:
    system_prompt: |
      You are a security-focused code reviewer. Focus on OWASP Top 10,
      secret leakage, and injection risks. Be concise.
```

---

## Agents

| Agent | Role | What it checks |
|-------|------|----------------|
| **Router** | Orchestrator | Reads the PR title, description, and changed files to decide which specialist agents are needed and how deep the review should go |
| **Security** | Vulnerability hunter | Secrets leakage, auth bypasses, injection risks, unsafe deserialization, missing input validation |
| **Quality** | Correctness reviewer | Logic errors, off-by-one bugs, missing error handling, type mismatches, missing tests, high complexity |
| **Architecture** | System-level reviewer | Cross-file impact, API consistency, documentation freshness, dependency changes, migration alignment |
| **Synthesis** | Editor-in-chief | Deduplicates findings across agents, resolves conflicts, prioritizes by severity, formats the final review and verdict |

### How the Router decides

The Router uses simple heuristics plus model reasoning:
- Files in `auth/`, `security/`, `crypto/` → include Security
- Source files with significant additions → include Quality
- `README.md`, `docs/`, `api/` changes → include Architecture
- Configurable overrides in `config.yaml` can force agents on or off

### Cross-file awareness

The Architecture agent is the primary user of the Repository Browser, but all agents can read files when needed:

| Scenario | Files the agent may read |
|----------|--------------------------|
| New public API endpoint | `README.md`, `docs/API.md`, `openapi.yaml` |
| New function without tests | `tests/`, `test_*` files in related directories |
| Auth logic modified | Other files in `auth/`, `middleware/` directories |
| Dependency added | `requirements.txt`, `package.json`, `poetry.lock` |
| Model/DB schema changed | Migration files in `migrations/` |
| Config key added | `.env.example`, `config.yaml`, `docker-compose.yml` |

---

## Cost Control

### Budget

The default cost budget is **$5.00 per PR**. This is a soft limit based on estimated token usage:
- The Router runs first on a fast, cheap model to decide which agents are needed
- Before dispatching agents, the system estimates token usage
- If the estimate approaches the budget, non-critical agents are skipped or switched to cheaper models

### Typical costs

| PR size | Agents dispatched | Estimated cost |
|---------|-------------------|----------------|
| Small (1-3 files) | Router + 2 specialists + Synthesis | ~$0.50 - $1.50 |
| Medium (5-15 files) | Router + 3 specialists + Synthesis | ~$1.50 - $3.50 |
| Large (20-50 files) | Router + 3 specialists + Synthesis | ~$3.50 - $5.00 |

Costs vary by provider and model. Fireworks.ai is the default because it offers strong reasoning at a lower price point for the models used in this project.

### Hard limits

You can also enforce hard PR size limits to prevent runaway costs:
- `max_files: 50` — skip PRs with more than 50 changed files
- `max_lines: 2000` — skip PRs with more than 2000 added/deleted lines
- `max_diff_size: 50000` — skip PRs with a diff larger than 50 KB

---

## Debug Mode

Enable debug mode to dump the full review state as a workflow artifact. This is useful for troubleshooting why an agent did or did not flag something, or for auditing token usage.

```yaml
debug: true
```

When enabled, the action uploads a JSON artifact containing:
- The full `ReviewState` (PR metadata, agent outputs, synthesis)
- `files_read` — every file each agent browsed
- `api_calls` — GitHub API call count
- Estimated token usage per agent

**Secrets are automatically stripped** from the artifact before upload.

Download the artifact from the GitHub Actions run page under **Artifacts**.

---

## Security

### Secrets handling

- API keys are passed via GitHub Secrets and are never logged
- The debug artifact strips any values that look like secrets before upload
- The action does not persist code or review data outside the workflow run

### Fork behavior

By default, AI Council **skips commenting on pull requests from forks** (`comment_on_forks: false`). This is because `GITHUB_TOKEN` on fork PRs is read-only and cannot post reviews.

If you understand the security trade-offs of `pull_request_target` and want to enable fork reviews, set:

```yaml
comment_on_forks: true
```

### PR filtering

The action skips review automatically for:
- Draft PRs
- PRs with skip labels (e.g., `skip-ai-review`, `wip`, `do-not-review`)
- PRs that exceed size limits

---

## Development

To run the project locally or contribute:

```bash
# Clone and enter the repo
git clone <repo-url>
cd ai-council-code-review

# Install dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Lint and type check
ruff check .
mypy src/ai_council_review
```

For full project conventions, branching strategy, and agent architecture, see `AGENTS.md` and `reference.md`.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

*Project status: v1.0 — Production-ready*
*Last updated: 2026-06-02*
