# AI Council Code Review

[![CI](https://github.com/Sosoka-Labs/ai-council-code-review/actions/workflows/ci.yml/badge.svg)](https://github.com/Sosoka-Labs/ai-council-code-review/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](https://github.com/Sosoka-Labs/ai-council-code-review/releases)

**A council of specialist AI agents that reviews your pull requests — and reads the rest of your repo to catch what a diff alone can't.**

Most AI reviewers see only the diff. AI Council dispatches six domain specialists — security, quality, architecture, performance, documentation, and devops — that can browse your repository in real time, reading unchanged files to catch consistency, security, and architectural impact a single-pass reviewer misses. A router gates which specialists run on each PR (so cost stays low), and a synthesis agent dedupes and prioritizes their findings into one coherent review.

---

## Why AI Council vs. a single-agent reviewer

- **Six focused specialists, not one generalist.** Each agent reasons about a single domain at the right temperature and depth, instead of one prompt trying to be a security expert, a performance expert, and a docs reviewer at once.
- **It reads beyond the diff.** When a GitHub token is present, agents browse unchanged files on demand — so the documentation agent can check whether your `README.md` still matches the signature you just changed, and the architecture agent can trace cross-file impact.
- **Routed for cost.** A fast, cheap router decides which specialists a PR actually needs, so a typical change runs a couple of agents — not all six.
- **One review, not a wall of noise.** The synthesis agent deduplicates overlapping findings, resolves conflicts, and emits a single verdict.
- **Pluggable domain knowledge.** Bind project-specific [Skills](#skills--binding-domain-knowledge-to-agents) (markdown files versioned in your repo) to any agent to teach it your conventions and known pitfalls.

---

## Overview

| Capability | What it means for you |
|-----------|----------------------|
| **Six-agent council** | Security, Quality, Architecture, Performance, Documentation, and DevOps specialists each own their domain |
| **Router-gated** | A fast model picks only the specialists a PR needs, keeping typical reviews cheap |
| **Cross-file awareness** | Agents read unchanged files — `README.md`, tests, migrations, dependencies — to catch drift and impact (when a GitHub token is present) |
| **Skills** | Bind versioned `SKILL.md` domain-knowledge files to any agent to encode your team's conventions |
| **Agent-attributed comments** | Every inline comment is tagged with the agent name and a confidence score |
| **Cost-controlled** | Configurable per-PR budget ($5.00 default); skips forks and drafts by default |
| **Graceful degradation** | One agent failure does not crash the workflow; others continue. No token? Agents fall back to diff-only review |
| **Multi-provider** | Fireworks.ai (default), OpenAI, and Anthropic — every agent supports all three, mixable per agent |
| **Stateless** | No persistence, no vector store, no database — just the GitHub API and smart prompts |

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
    branches: [main]

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

> **Note:** The workflow above passes these secrets as bare environment variables (e.g., `FIREWORKS_API_KEY`), which LangChain reads automatically. If you prefer to set them via the config system, use the `AI_COUNCIL__FIREWORKS_API_KEY` style instead.

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
  - "package-lock.json"           # Exact filename match
  - "yarn.lock"
  - "poetry.lock"
  - "Cargo.lock"
  - "Gemfile.lock"
  - "*.snap"                      # Glob wildcard: all .snap files
  - "dist/"                       # Directory prefix: anything under dist/
  - "build/"
  - "node_modules/"
  - "**/*.pyc"                    # Glob: all .pyc files in any directory

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

  performance:
    enabled: true
    model: fireworks
    model_name: accounts/fireworks/models/llama-v3p1-70b-instruct
    temperature: 0.3
    max_tokens: 4000

  documentation:
    enabled: true
    model: fireworks
    model_name: accounts/fireworks/models/llama-v3p1-70b-instruct
    temperature: 0.3
    max_tokens: 4000

  devops:
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

### Model aliases

You can use shorthand names instead of full provider paths. Both the alias form and the full model ID are accepted — for example, `fireworks/llama-3.1-70b` and `accounts/fireworks/models/llama-v3p1-70b-instruct` are equivalent.

| Alias | Resolves to |
|-------|-------------|
| `fireworks/llama-3.1-70b` | `accounts/fireworks/models/llama-v3p1-70b-instruct` |
| `fireworks/llama-3.1-8b` | `accounts/fireworks/models/llama-v3p1-8b-instruct` |
| `fireworks/kimi-k2p6` | `accounts/fireworks/routers/kimi-k2p6-turbo` |
| `openai/gpt-4o` | `gpt-4o` |
| `openai/gpt-4.1` | `gpt-4.1` |
| `openai/gpt-4.1-mini` | `gpt-4.1-mini` |
| `anthropic/claude-sonnet` | `claude-sonnet-4-20250514` |
| `anthropic/claude-haiku` | `claude-3-haiku-20240307` |

### Mixed-provider example

You can mix providers and models per agent to optimize cost and quality:

```yaml
agents:
  router:
    model: openai
    model_name: openai/gpt-4.1-mini   # fast, cheap
    temperature: 0.1
    max_tokens: 2000

  security:
    model: fireworks
    model_name: fireworks/llama-3.1-70b
    temperature: 0.2
    max_tokens: 16000

  synthesis:
    model: anthropic
    model_name: anthropic/claude-sonnet  # strong reasoning
    temperature: 0.2
    max_tokens: 16000
```

> **Tip:** Model choice directly affects cost. Using a cheaper model for Router and a stronger one for Synthesis is the recommended balance.

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

## Skills — Binding domain knowledge to agents

Skills are markdown files that inject project-specific knowledge into a specialist agent's system prompt. They let downstream teams encode conventions, known pitfalls, or domain rules that the generic agents would otherwise have no visibility into. Skills travel with the reviewed repository, are versioned in git, and can be PR-reviewed like any other config.

### File layout

Place skill files under `.ai-council/skills/<name>/SKILL.md`:

```
.ai-council/
└── skills/
    └── oauth-pitfalls/
        └── SKILL.md         # required: YAML frontmatter + markdown body
```

Minimal `SKILL.md`:

```markdown
---
name: oauth-pitfalls
description: Use when reviewing OAuth 2.0 flows, token handling, or PKCE implementations.
---
# OAuth Pitfalls

...review guidance here...
```

### Frontmatter fields

| Field | Required | Notes |
|-------|----------|-------|
| `name` | Yes | Lowercase and hyphens only; must match the parent directory name |
| `description` | Yes | 1024 chars max; the Router reads descriptions to route more accurately |
| Any other fields | No | Preserved as-is; ignored by AI Council in Phase 1 |

### Binding to agents

Skills are bound explicitly per agent in `.ai-council/config.yaml`. Three patterns are supported:

```yaml
# Pattern 1 — explicit per-agent list (recommended)
agents:
  security:
    skills: [oauth-pitfalls]

# Pattern 2 — star sentinel: give this agent every discovered skill
agents:
  architecture:
    skills: "*"

# Pattern 3 — top-level default applied to every agent that doesn't set its own
default_agent_skills: [domain-glossary]
# Set skills: [] on a specific agent to opt it out of the default.
```

Resolution order per agent: explicit `skills:` on the agent → `default_agent_skills` → none (no skills).

Listing a skill name that does not exist on disk is a hard error at config load time. The `"*"` sentinel always resolves at runtime and is never a load-time error.

### Bundled skills

The repository ships four demo skills under [`.ai-council/skills/`](.ai-council/skills/), each wired to a matching agent in the [example config](examples/.ai-council/config.yaml):

| Skill | Bound to | Encodes |
|-------|----------|---------|
| `oauth-pitfalls` | security | OAuth 2.0 / JWT / PKCE review guidance |
| `n-plus-one` | performance | N+1 query and ORM access-pattern detection |
| `docstring-style` | documentation | Google-style docstring conventions |
| `github-actions-hardening` | devops | GitHub Actions security and correctness |

Copy any of these into your own repo as a starting point, or drop in a new `SKILL.md` and bind it the same way.

### What each role receives

- **Specialist agents** (security, quality, architecture, performance, documentation, devops) — full skill bodies appended to the system prompt.
- **Router** — a descriptions-only catalog (name + description for each skill) appended to its system prompt, so it can route more accurately when domain skills are present. No bodies.
- **Synthesis** — no skills in Phase 1.

### Token budgets

The sum of skill bodies for each agent is checked before the run:

- Soft limit (default 8 000 tokens): warning logged, run continues.
- Hard limit (default 16 000 tokens): `ConfigError` raised, run aborts with a list of offending skill sizes.

Both limits are configurable:

```yaml
skills_token_budget_soft: 8000
skills_token_budget_hard: 16000
```

The budget uses a `len / 4` character approximation — exact per-model tokenization is deferred to a later phase.

### Future phases

Progressive disclosure (on-demand body loading via a `load_skill` tool) and skill scripts (`scripts/` subdirectory) are tracked for Phase 2 and Phase 3 respectively.

---

## Agents

AI Council is built from **six specialist agents**, plus a **router** that gates them and a **synthesis** agent that merges their output. The roster is registry-driven (`src/ai_council_review/llm/agents/registry.py`) — the router catalog and synthesis categories derive from it automatically.

| Agent | Focus | Triggers when the diff touches… |
|-------|-------|---------------------------------|
| **Security** | Secrets leakage, auth bypasses, injection, unsafe deserialization, missing input validation | auth, crypto, user input, secrets, deps, API endpoints, data persistence |
| **Quality** | Logic bugs, error handling, type safety, missing tests, complexity, code smells | significant source changes, error handling, tests, typing |
| **Architecture** | Cross-file impact, public-API consistency, docs/migration drift, data models | multiple files/modules, public APIs, data models, configuration |
| **Performance** | N+1 queries, unbounded result sets, O(n²) loops, sync I/O on hot paths, missing caching/indexes | DB/ORM queries, loops over collections, request handlers, `repositories/`, `dao/`, `queries/` |
| **Documentation** | Stale docstrings vs. changed signatures, missing docs on new public APIs, changelog gaps, broken examples | `*.md`, public signature changes, new CLI flags/env vars, new exports |
| **DevOps** | GitHub Actions, Dockerfiles, Terraform, shell scripts, CI/CD correctness and hardening | `.github/workflows/*`, `Dockerfile`, `*.tf`, `*.sh`, CI YAML |

| Coordinator | Role |
|-------------|------|
| **Router** | Reads the PR title, description, and changed files to decide which specialists are needed and how deep the review goes. Falls back to all agents on parse failure. |
| **Synthesis** | Deduplicates findings across agents, resolves conflicts, prioritizes by severity, and emits the final summary and verdict (`approve` / `comment` / `request_changes`). |

### How the Router decides

Each specialist's trigger conditions (the `router_hint` in the registry) are injected into the router prompt, so the router knows when to call each one. It combines those hints with model reasoning over the PR's files and intent. You can also force agents on or off per agent via `enabled` in `config.yaml`. On `standard` depth, the router caps the number of parallel specialists to keep cost predictable.

### Cross-file awareness

When a GitHub token is present, any specialist can call the Repository Browser to read unchanged files on demand for cross-file analysis. Without a token (dry-run, fork, or local diff-only mode) the agents degrade gracefully to reviewing the diff alone. Typical reads:

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
| Small (1-3 files) | Router + 1-2 specialists + Synthesis | ~$0.50 - $1.50 |
| Medium (5-15 files) | Router + 2-4 specialists + Synthesis | ~$1.50 - $3.50 |
| Large (20-50 files) | Router + up to 4 specialists + Synthesis | ~$3.50 - $5.00 |

The router caps parallel specialists at four on `standard` depth; `review_depth: deep` lifts the cap to let all six run on changes that warrant it.

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

## Troubleshooting

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `Configuration error: No LLM API key found` | Missing or misnamed secret | Add `FIREWORKS_API_KEY` (or `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) to **Settings > Secrets and variables > Actions**. See [Quick Start > Add your API key](#2-add-your-api-key). |
| `LLM provider error: Unsupported provider: xyz` | Typo in `model` field | Use one of: `fireworks`, `openai`, `anthropic`. Check `.ai-council/config.yaml`. |
| `LLM provider error: Failed to initialize...` | Invalid API key or model name | Verify the secret value and the `model_name` in config. Try an alias from the [Model aliases](#model-aliases) table. |
| `Review failed with timeout` | PR too large or model too slow | Reduce `max_files` / `max_lines` in config, or increase `agent_timeout_seconds` / `total_timeout_seconds`. |
| `No review posted on fork PR` | Expected default behavior | Fork PRs are skipped by default (`comment_on_forks: false`). See [Security > Fork behavior](#fork-behavior). |
| `Agent output is empty or garbled` | Model context too short for JSON | Increase `max_tokens` for the affected agent (e.g., 16000 for Fireworks reasoning models). |

---

## Known Limitations

- **Stateless — no memory across reviews.** AI Council does not learn from past reviews or remember project conventions between runs; each PR is reviewed from scratch.
- **Inline comments land only on changed hunks.** GitHub silently drops review comments outside the lines a PR actually touches, so a finding about unchanged code is reported in the summary rather than inline.
- **Router-gated cost ceiling.** To stay within budget, the router caps how many specialists run on `standard`-depth PRs — a relevant agent can be skipped on a borderline change. Raise `review_depth` to `deep` or force the agent on in config when needed.
- **No IDE or CLI tool** — the only supported interface is the GitHub Actions workflow.
- **No custom provider support** — only Fireworks.ai, OpenAI, and Anthropic are supported today.
- **Max 50 files / 2000 lines default** — large PRs are skipped by default to control cost and runtime.
- **Language-agnostic but not language-aware** — agents infer language from file extensions; there are no language-specific parsers.

---

## Roadmap

A one-line **GitHub Marketplace Action** (drop-in `uses:` step) and **PyPI packaging** are planned to make installation a single line instead of the full workflow shown in Quick Start.

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

For full project conventions, branching strategy, and agent architecture, see `AGENTS.md` and `CONTRIBUTING.md`.

---

## Branching & Release Strategy

This project uses a **Gitflow-lite** model with two long-lived branches:

| Branch | Purpose |
|--------|---------|
| `develop` | Integration branch. All feature and bugfix branches target `develop`. CI gates run here. |
| `main` | Release branch. Only receives merges from `develop` when a release is cut. Tags are always from `main`. |

### Contributor flow

```
develop   ←── feature/my-feature   (PR into develop, CI must pass)
   │
   └── (merge to main at release time, then tag)
main      ←── v1.2.0 tag
```

1. Branch from `develop`: `git checkout -b feature/my-feature develop`
2. Open a PR targeting `develop`. CI (tests, lint, type check) must be green.
3. After review, merge into `develop`.
4. At release time, `develop` is merged to `main` and a `vX.Y.Z` tag is pushed from `main`.

### Consumer guidance

Pin to a release tag rather than `main` or `develop` in your workflow:

```yaml
# Pin to a stable release
- name: Checkout AI Council
  uses: actions/checkout@v4
  with:
    repository: Sosoka-Labs/ai-council-code-review
    ref: v1.0.0          # <-- always pin to a release tag
    path: ai-council
```

`develop` can include in-progress work and is not guaranteed to be stable. `main` is stable but is only updated at release boundaries. Pinning to a tag is the only guarantee of a reproducible, reviewed build.

New releases are announced in [CHANGELOG.md](CHANGELOG.md) and [GitHub Releases](https://github.com/Sosoka-Labs/ai-council-code-review/releases).

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

*Project status: v1.0 — Production-ready*
*Last updated: 2026-06-08*
