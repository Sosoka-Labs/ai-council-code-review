# Configuration

The complete reference for `.ai-council/config.yaml`, environment overrides, model aliases, and per-agent provider settings.

← Back to [README](../README.md)

---

AI Council looks for `.ai-council/config.yaml` in the repository root (on the base branch). **Every option has a default — the tool works with zero config.** If the file is missing, AI Council uses OpenAI with `gpt-4.1-mini` and sensible review settings.

The annotated source of truth is [`examples/.ai-council/config.yaml`](../examples/.ai-council/config.yaml). Copy it into your repo and trim to taste.

## Complete example

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
# `model` is the provider name: openai, anthropic, or fireworks
# `model_name` is a full model identifier or a shorthand alias
agents:
  router:
    enabled: true
    model: openai
    model_name: openai/gpt-4.1-mini   # fast, cheap
    temperature: 0.1
    max_tokens: 2000

  security:
    enabled: true
    model: openai
    model_name: openai/gpt-4.1
    temperature: 0.2
    max_tokens: 16000
    skills: [oauth-pitfalls]

  quality:
    enabled: true
    model: openai
    model_name: openai/gpt-4.1
    temperature: 0.3
    max_tokens: 16000

  architecture:
    enabled: true
    model: openai
    model_name: openai/gpt-4.1
    temperature: 0.3
    max_tokens: 16000

  performance:
    enabled: true
    model: openai
    model_name: openai/gpt-4.1
    temperature: 0.3
    max_tokens: 16000
    skills: [n-plus-one]

  documentation:
    enabled: true
    model: openai
    model_name: openai/gpt-4.1
    temperature: 0.3
    max_tokens: 16000
    skills: [docstring-style]

  devops:
    enabled: true
    model: openai
    model_name: openai/gpt-4.1
    temperature: 0.3
    max_tokens: 16000
    skills: [github-actions-hardening]

  synthesis:
    enabled: true
    model: openai
    model_name: openai/gpt-4.1-mini
    temperature: 0.2
    max_tokens: 16000

# ── LLM Provider Settings ─────────────────────────────
# API keys load from environment variables by default.
# Set OPENAI_API_KEY for the default configuration above.
providers:
  openai:
    api_key: null    # reads OPENAI_API_KEY from environment
  anthropic:
    api_key: null    # reads ANTHROPIC_API_KEY from environment
  fireworks:
    api_key: null    # reads FIREWORKS_API_KEY from environment
```

## Review settings

| Key | Default | Meaning |
|-----|---------|---------|
| `review_depth` | `standard` | `standard` caps parallel specialists at 4; `deep` lets all six run. |
| `max_files` | `50` | Skip PRs touching more than this many files. |
| `max_lines` | `2000` | Skip PRs with more than this many changed lines. |
| `max_diff_size` | `50000` | Skip PRs with a diff larger than this many bytes. |
| `comment_on_forks` | `false` | See [Security › Fork behavior](security.md#fork-behavior). |
| `skip_drafts` | `true` | Skip draft PRs. |
| `skip_labels` | `[skip-ai-review, wip]` | Skip PRs carrying any of these labels. |
| `skip_patterns` | lockfiles, build dirs, etc. | Exact names, directory prefixes, or globs (`*.snap`, `**/*.pyc`). |

Cost and timeout settings are documented in [docs/cost-control.md](cost-control.md).

## Environment variable overrides

Any config value can be overridden via environment variables using the `AI_COUNCIL__` prefix with `__` as the nested separator. API keys are the most common case:

```bash
AI_COUNCIL__OPENAI_API_KEY=sk-xxxxxxxx
AI_COUNCIL__ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
AI_COUNCIL__FIREWORKS_API_KEY=fw-xxxxxxxx
AI_COUNCIL__GITHUB_TOKEN=ghp_xxxxxxxx
```

The Quick Start workflow instead passes bare env vars (`OPENAI_API_KEY`, etc.), which LangChain reads automatically. Use whichever you prefer.

## Providers and model aliases

The `model` field selects a provider; `model_name` accepts either a full provider model ID or a shorthand alias.

| Provider | Default model | Set this key |
|----------|---------------|--------------|
| **OpenAI** (default) | `gpt-4.1-mini` | `OPENAI_API_KEY` |
| **Anthropic** | `claude-3-5-haiku-20241022` | `ANTHROPIC_API_KEY` |
| **Fireworks** | `accounts/fireworks/models/kimi-k2p6` | `FIREWORKS_API_KEY` |

Recommended aliases:

| Alias | Resolves to |
|-------|-------------|
| `openai/gpt-4.1` | `gpt-4.1` |
| `openai/gpt-4.1-mini` | `gpt-4.1-mini` |
| `anthropic/claude-sonnet` | `claude-sonnet-4-20250514` |
| `anthropic/claude-haiku` | `claude-3-5-haiku-20241022` |
| `fireworks/kimi-k2p6` | `accounts/fireworks/routers/kimi-k2p6-turbo` |

New aliases are added in `src/ai_council_review/config.py`. Choosing a model is a cost/quality trade-off — see [docs/cost-control.md](cost-control.md) and [docs/providers.md](providers.md).

## Mixed-provider example

You can mix providers and models per agent to optimize cost and quality:

```yaml
agents:
  router:
    model: openai
    model_name: openai/gpt-4.1-mini   # fast, cheap
    temperature: 0.1
    max_tokens: 2000

  security:
    model: anthropic
    model_name: anthropic/claude-sonnet   # strong reasoning
    temperature: 0.2
    max_tokens: 16000

  synthesis:
    model: openai
    model_name: openai/gpt-4.1
    temperature: 0.2
    max_tokens: 16000
```

> **Tip:** Using a fast/cheap model for the Router and a stronger one for the specialists and Synthesis is the recommended balance.

## Override prompts

Override any agent's system prompt by adding a `system_prompt` field to its config:

```yaml
agents:
  security:
    system_prompt: |
      You are a security-focused code reviewer. Focus on OWASP Top 10,
      secret leakage, and injection risks. Be concise.
```

## Skills configuration

Binding domain-knowledge `SKILL.md` files to agents (`skills:`, the `"*"` sentinel, and `default_agent_skills`) is covered in full in [docs/skills.md](skills.md).

---

← Back to [README](../README.md)
