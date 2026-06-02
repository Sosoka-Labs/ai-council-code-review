# AI Council Code Review — v1 Specification & Implementation Plan

> **Project:** A configurable, multi-agent AI code review system for GitHub Actions, built with Python, LangGraph, and LangChain.
> **Version:** 1.0 (Initial Release)
> **Date:** 2026-06-02
> **Status:** Specification / Ready for Implementation

---

## 1. Executive Summary

This project implements a **GitHub Action** that runs a **council of specialized AI agents** to review pull requests. Unlike single-agent tools that review diffs in isolation, our system gives agents the ability to **browse the repository in real-time** — reading unchanged files to check for cross-file impacts (e.g., "Did the README need updating after that API change?").

For v1, the system is **stateless** — no persistence layer, no vector store, no graph database. All context is fetched on-demand via the GitHub API. This keeps the initial architecture simple while still delivering the key differentiator: **cross-file awareness through real-time repository browsing**.

### Key Differentiators (v1)

| Feature | Typical AI Review Tools | AI Council (v1) |
|---------|------------------------|-----------------|
| Agent Model | Single generalist | 4+ specialist agents + router + synthesis |
| Cross-file Awareness | None (diffs only) | Real-time repo browsing via GitHub API |
| Configurability | Hardcoded prompts | YAML-configurable agents, models, rules |
| Persistence | Stateless | **Stateless** (by design for v1) |
| Cost Control | Fixed | Configurable model selection per agent, PR size limits |

---

## 2. Scope & Constraints

### 2.1 In Scope (v1)

- [ ] GitHub Action workflow triggered on PR events
- [ ] Multi-agent council with LangGraph orchestration using standard LangChain/LangGraph agents
- [ ] Real-time repository browsing (read any file via GitHub API)
- [ ] Cross-file awareness: agents can check unchanged files for consistency
- [ ] Configurable agent selection, models, and prompts via YAML
- [ ] Inline PR review comments + summary comment
- [ ] PR filtering (size limits, labels, skip patterns)
- [ ] Rate limiting and error handling for GitHub API
- [ ] Support for multiple LLM providers (Fireworks.ai default, OpenAI, Anthropic as first-class options)

### 2.2 Out of Scope (v1) — Intentionally Deferred

- [ ] Persistence layer (vector store, graph DB, relational DB)
- [ ] Review history or learning from past reviews
- [ ] Incremental review (only re-reviewing changed commits)
- [ ] IDE plugin or CLI tool
- [ ] Multi-repo support
- [ ] Custom agent creation by users (beyond config YAML)
- [ ] Performance profiling tools or static analysis integration
- [ ] Automatic code fixes or PR suggestions

### 2.3 Design Philosophy

> **"A code review should know your codebase like a senior engineer — not because it remembers everything, but because it knows where to look."**

For v1, we trade **memory** for **mobility**. Agents can't remember that "PR #42 established this convention," but they *can* read `CONTRIBUTING.md`, scan the `tests/` directory, or check `README.md` when an API changes. This is achieved by giving each agent a **Repository Browser** toolset.

All prompts are **language-agnostic** — agents infer the programming language from file extensions and directory structure, rather than assuming a specific stack.

---

## 3. System Architecture

### 3.1 High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GITHUB ACTIONS                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  Trigger: pull_request (opened, synchronize, reopened)               ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   ││
│  │  │ Checkout    │  │ Setup Python│  │ Run AI Council Reviewer │   ││
│  │  │ (fetch-depth│  │ (3.11, deps)│  │ (main.py entrypoint)    │   ││
│  │  │  = 0)       │  │             │  │                         │   ││
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      INGESTION LAYER                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  PRIngestor                                                        ││
│  │  • Load event payload (GITHUB_EVENT_PATH)                          ││
│  │  • Fetch PR metadata via GitHub API                                ││
│  │  • Fetch changed files list + patches                              ││
│  │  • Compute PR stats (files, lines, additions, deletions)           ││
│  │  • Filter: skip if too large, labeled skip, draft, etc.              ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATION LAYER (LangGraph)                     │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  State: ReviewState                                                  ││
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   ││
│  │  │ Ingest   │───→│ Route    │───→│ Agents   │───→│ Synthesis│   ││
│  │  │          │    │ Agent    │    │ (parallel│    │ Agent    │   ││
│  │  │          │    │          │    │  where  │    │          │   ││
│  │  │          │    │          │    │ possible)│    │          │   ││
│  │  └──────────┘    └──────────┘    └──────────┘    └──────────┘   ││
│  │         │                                              │         ││
│  │         └──────────────────────────────────────────────┘         ││
│  │                                    │                                ││
│  │                                    ▼                                ││
│  │                           ┌──────────────┐                          ││
│  │                           │ Post to GitHub│                          ││
│  │                           │ (Review +     │                          ││
│  │                           │  Comments)    │                          ││
│  │                           └──────────────┘                          ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AGENT LAYER (Specialized LLM Agents)                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐│
│  │ Router      │ │ Security    │ │ Quality     │ │ Architecture        ││
│  │ Agent       │ │ Agent       │ │ Agent       │ │ Agent               ││
│  │             │ │             │ │             │ │                     ││
│  │ "What needs │ │ "Any vulns? │ │ "Bugs?      │ │ "Cross-file        ││
│  │  review?"   │ │             │ │  Type errs? │ │  impact?            ││
│  │             │ │             │ │  Tests?"    │ │  Docs stale?"       ││
│  │             │ │             │ │             │ │                     ││
│  │ Tool:       │ │ Tools:      │ │ Tools:      │ │ Tools:              ││
│  │ classify    │ │ secret_scan │ │ lint_check  │ │ find_related_files  ││
│  │             │ │ cwe_check   │ │ test_find   │ │ read_doc_files      ││
│  │             │ │             │ │ complexity  │ │ check_api_surface   ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  All agents share: RepositoryBrowser (read any file via GitHub API)  ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 LangGraph State Definition

```python
from typing import TypedDict, List, Dict, Optional, Any

class FileInfo(TypedDict):
    filename: str
    status: str  # added, removed, modified, renamed
    patch: Optional[str]
    additions: int
    deletions: int

class ReviewComment(TypedDict):
    path: str
    position: int
    body: str
    side: str  # LEFT or RIGHT

class ReviewState(TypedDict):
    # PR Context
    pr_number: int
    repo: str
    base_ref: str
    head_ref: str
    base_sha: str
    head_sha: str
    pr_title: str
    pr_body: str

    # Input Data
    changed_files: List[FileInfo]
    config: Dict[str, Any]           # Loaded from .ai-council/config.yaml

    # Agent Outputs
    agent_outputs: Dict[str, List[Dict[str, Any]]]  # {agent_name: [findings]}
    agents_needed: List[str]         # Determined by router

    # Synthesis
    synthesis: Optional[str]        # Final markdown summary
    verdict: str                    # "approve" | "comment" | "request_changes"
    inline_comments: List[ReviewComment]
    summary_comment: Optional[str]

    # Tracking
    files_read: List[str]           # For debugging/cost tracking
    api_calls: int                  # GitHub API call counter
    skipped_reason: Optional[str]   # If review was skipped
    errors: List[str]               # Non-fatal errors encountered
```

---

## 4. The Agent Council

Each agent is a LangChain/LangGraph agent with a specific system prompt, model configuration, and tool access.

### 4.1 Router Agent (Entry Node)

**Purpose:** Decide which specialist agents to invoke based on the PR diff.

**Inputs:**
- Changed file list (names, extensions, status)
- PR title and description
- File size statistics

**Outputs:**
```python
{
    "agents_needed": ["security", "quality", "architecture"],
    "review_depth": "standard",  # quick, standard, exhaustive
    "reasoning": "This PR modifies auth handlers and adds new API endpoints..."
}
```

**Logic:**
- If any files in `auth/`, `security/`, `crypto/` directories change → include **Security Agent**
- If any source files with significant additions change → include **Quality Agent**
- If any `README.md`, `docs/`, `api/` changes → include **Architecture Agent**
- If documentation files or public API signatures changed → include **Architecture Agent** (to check docs)
- Configurable overrides: user can force agents in config

**Model:** Fast/cheap model for classification. Fireworks.ai is the default, but all three providers are supported:

| Provider | Recommended Model | Notes |
|----------|-------------------|-------|
| **Fireworks** (default) | `accounts/fireworks/routers/kimi-k2p6-turbo` | Fast, strong reasoning, excellent code understanding |
| **OpenAI** | `gpt-4.1-mini` | Fast, good at structured output |
| **Anthropic** | `claude-3-haiku-20240307` | Fast, concise reasoning |

### 4.2 Security Agent

**Focus:** Vulnerabilities, authentication, authorization, secrets leakage, injection risks.

**System Prompt Themes:**
- "You are a security-focused code reviewer. Check for OWASP Top 10 patterns, secret leakage, unsafe deserialization, injection risks, and auth bypasses."

**Special Behaviors:**
- Always scans changed files for high-entropy strings that look like API keys, tokens, passwords
- Checks if new endpoints have authentication/authorization
- Flags `eval()`, `exec()`, `pickle.loads()`, SQL concatenation
- If auth files change, reads adjacent auth files for context

**Model:** Strong reasoning model for security analysis. All three providers supported:

| Provider | Recommended Model | Notes |
|----------|-------------------|-------|
| **Fireworks** (default) | `accounts/fireworks/routers/kimi-k2p6-turbo` | Strong reasoning, excellent at finding vulnerabilities |
| **OpenAI** | `gpt-4.1` | Excellent at finding subtle bugs |
| **Anthropic** | `claude-sonnet-4-20250514` | Best at reasoning about vulnerabilities |

### 4.3 Code Quality Agent

**Focus:** Bugs, logic errors, type safety, test coverage, edge cases, readability.

**System Prompt Themes:**
- "You are a senior engineer focused on code correctness. Check for null pointer risks, off-by-one errors, missing error handling, type mismatches, and insufficient test coverage."

**Special Behaviors:**
- If a new function is added without tests, checks `tests/` directory for related test files
- Flags functions with high cyclomatic complexity (estimated from code)
- Checks for missing docstrings on public functions
- Reviews exception handling

**Model:** Balanced model for general code review. All three providers supported:

| Provider | Recommended Model | Notes |
|----------|-------------------|-------|
| **Fireworks** (default) | `accounts/fireworks/routers/kimi-k2p6-turbo` | Strong reasoning, excellent code understanding |
| **OpenAI** | `gpt-4.1` | Reliable, good at structured output |
| **Anthropic** | `claude-sonnet-4-20250514` | Strong reasoning, excellent code understanding |

### 4.4 Architecture Agent

**Focus:** Cross-file impact, API consistency, documentation freshness, system-level design.

**System Prompt Themes:**
- "You are a staff engineer reviewing system-level impact. Check if API changes are documented, if dependencies are handled correctly, and if cross-file contracts are maintained."

**Special Behaviors:**
- **Cross-file browsing:** This is the primary agent for reading unchanged files
- If public API changes → reads `README.md`, `docs/API.md`, `CHANGELOG.md`
- If new models/schemas → checks migration files
- If dependency changes → checks `requirements.txt`, `poetry.lock`, `package.json`
- If configuration changes → checks `docker-compose.yml`, `Dockerfile`, `.env.example`
- Flags when code and docs drift

**Model:** Strong reasoning model for system-level analysis. All three providers supported:

| Provider | Recommended Model | Notes |
|----------|-------------------|-------|
| **Fireworks** (default) | `accounts/fireworks/routers/kimi-k2p6-turbo` | Strongest reasoning, excellent at cross-file analysis |
| **OpenAI** | `gpt-4.1` | Good at cross-file analysis |
| **Anthropic** | `claude-sonnet-4-20250514` | Best at understanding large codebases |

### 4.5 Synthesis Agent (Exit Node)

**Purpose:** Merge all agent outputs into a coherent, non-redundant review.

**Tasks:**
1. Deduplicate findings (e.g., Security and Architecture both flag the same missing validation)
2. Resolve conflicts (e.g., "add validation" vs "keep it simple")
3. Prioritize by severity
4. Format inline comments with correct `path` and `position`
5. Generate executive summary markdown
6. Decide verdict: `COMMENT` (default) or `REQUEST_CHANGES` (if critical findings)

**Model:** Strongest reasoning model for conflict resolution and synthesis. All three providers supported:

| Provider | Recommended Model | Notes |
|----------|-------------------|-------|
| **Fireworks** (default) | `accounts/fireworks/routers/kimi-k2p6-turbo` | Strongest reasoning, excellent at conflict resolution |
| **OpenAI** | `gpt-4.1` | Excellent at structured output and deduplication |
| **Anthropic** | `claude-sonnet-4-20250514` | Best at resolving conflicting recommendations |

---

## 5. Repository Browser — Cross-File Awareness

Since v1 has **no persistence layer**, all cross-file awareness is achieved through **real-time GitHub API calls**. We provide agents with a `RepositoryBrowser` tool that acts like a read-only filesystem.

### 5.1 Tool Interface

```python
class RepositoryBrowser:
    """Read-only filesystem access to the repository via GitHub API."""

    def get_file(self, path: str, ref: Optional[str] = None) -> str:
        """Read file content at given path. Defaults to HEAD if ref not provided."""

    def get_file_at_base(self, path: str) -> str:
        """Read file content at base branch (before PR)."""

    def get_file_at_head(self, path: str) -> str:
        """Read file content at PR branch (after changes)."""

    def list_directory(self, path: str, ref: Optional[str] = None) -> List[str]:
        """List files in a directory."""

    def find_files(self, pattern: str, ref: Optional[str] = None) -> List[str]:
        """Find files matching glob pattern (e.g., 'tests/**/test_*.py')."""

    def file_exists(self, path: str, ref: Optional[str] = None) -> bool:
        """Check if a file exists."""

    def get_changed_files(self) -> List[FileInfo]:
        """Return the list of files changed in this PR."""

    def get_patch_for_file(self, filename: str) -> Optional[str]:
        """Get the unified diff patch for a specific changed file."""

    def get_repo_tree(self, ref: Optional[str] = None, recursive: bool = False) -> List[Dict]:
        """Get repository file tree (useful for understanding structure)."""
```

### 5.2 Cross-File Awareness Patterns

| Scenario | Agent Action | Files Read |
|----------|-------------|------------|
| New public API endpoint added | Architecture reads docs | `README.md`, `docs/API.md`, `openapi.yaml` |
| New function added without tests | Quality checks test dir | `tests/`, `test_*` files in related directories |
| Auth logic modified | Security reads adjacent files | Other files in `auth/`, `middleware/` directories |
| Dependency added | Architecture checks lock files | Dependency manifest files (e.g., `requirements.txt`, `package.json`, `Cargo.lock`) |
| Model/DB schema changed | Architecture checks migrations | Migration files in `migrations/`, `db/migrate/`, etc. |
| Config key added | Architecture checks examples | `.env.example`, `config.yaml`, `docker-compose.yml` |
| Error message changed | Quality checks consistency | Other error messages in same file/module |
| CLI command added | Architecture checks help text | CLI entry point, help docs |

### 5.3 Cost & Rate Limit Considerations

- **Track every API call:** The `RepositoryBrowser` increments `state.api_calls` on each request
- **Limit file reads:** Config `max_files_to_browse` defaults to 20 per agent
- **Cost budget enforcement:** Config `cost_budget_usd` defaults to `$5.00` per PR. The system estimates token usage before dispatching agents and switches to cheaper models or skips non-critical agents if the budget is at risk.
- **Prefer HEAD content:** Use `git show HEAD:path` in the checked-out repo when possible (free, no API rate limit)
- **GitHub API fallback:** Use REST API for files not in checkout, or for base branch versions
- **Rate limit awareness:** If GitHub API rate limit < 100, switch to conservative mode (limit browsing)

---

## 6. GitHub Integration

### 6.0 Project-Level Workflows

This repository itself uses two workflows (defined in `.github/workflows/`):

| Workflow | File | Purpose |
|----------|------|---------|
| **CI** | `ci.yml` | Runs on every PR to `main` — pytest, ruff, mypy |
| **AI Council Review** | `ai-council-review.yml` | Self-dogfood — runs our own action on this repo's PRs |

These are separate from the **user-facing workflow** (described in §6.1) that consumers of this action copy into their own repos.

### 6.1 User-Facing GitHub Actions Workflow

```yaml
# .github/workflows/ai-council-review.yml
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
      - name: Checkout PR branch
        uses: actions/checkout@v4
        with:
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
          # LLM API keys (configure in repo secrets)
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

### 6.2 Comment Posting Strategy

**Mode: Full Review (Recommended)**

Post a single PR review containing:
1. **Summary comment** (top-level review body) — markdown overview with agent findings
2. **Inline comments** (on specific diff positions) — line-level feedback

```python
# Create a full review
pr.create_review(
    body=synthesis.summary_markdown,
    comments=[
        {"path": "src/api.py", "position": 5, "body": "Security: Missing input validation...", "side": "RIGHT"},
        {"path": "src/api.py", "position": 12, "body": "Architecture: Update README docs...", "side": "RIGHT"},
    ],
    event="COMMENT"  # or "REQUEST_CHANGES" if critical findings
)
```

**Alternative: Separate Comments**
If review API fails (e.g., too many comments), fall back to:
- One general PR comment (conversation timeline) with the full summary

### 6.3 PR Filtering

Before running agents, check if PR should be skipped:

```python
SKIP_LABELS = {"skip-ai-review", "wip", "draft", "do-not-review"}
MAX_FILES = 50
MAX_LINES = 2000
MAX_DIFF_SIZE = 50000  # bytes

skip_conditions = [
    (pr.is_draft, "Draft PR"),
    (any(l in SKIP_LABELS for l in pr.labels), f"Skip label present"),
    (pr.changed_files > MAX_FILES, f"Too many files: {pr.changed_files}"),
    (pr.additions + pr.deletions > MAX_LINES, f"Diff too large"),
]
```

---

## 7. Configuration System

### 7.1 Config File Location

The action looks for `.ai-council/config.yaml` in the repository root (on the base branch). If not found, it uses sensible defaults.

### 7.2 Config Schema

```yaml
# .ai-council/config.yaml
version: "1"

# ── Agent Configuration ───────────────────────────────
agents:
  router:
    enabled: true
    model: "accounts/fireworks/routers/kimi-k2p6-turbo"
    provider: "fireworks"
    temperature: 0.1
    # System prompt can be overridden
    system_prompt: |
      You are a routing agent. Analyze the PR and decide which specialist
      agents should review it. Return a JSON object with "agents_needed".

  security:
    enabled: true
    model: "accounts/fireworks/routers/kimi-k2p6-turbo"
    provider: "fireworks"
    temperature: 0.2
    system_prompt: |
      You are a security-focused code reviewer...

  quality:
    enabled: true
    model: "accounts/fireworks/routers/kimi-k2p6-turbo"
    provider: "fireworks"
    temperature: 0.3

  architecture:
    enabled: true
    model: "accounts/fireworks/routers/kimi-k2p6-turbo"
    provider: "fireworks"
    temperature: 0.3

  synthesis:
    enabled: true
    model: "accounts/fireworks/routers/kimi-k2p6-turbo"
    provider: "fireworks"
    temperature: 0.2

# ── Review Settings ───────────────────────────────────
review:
  # PR size limits
  max_files: 50
  max_lines_per_file: 500
  max_total_lines: 2000
  max_diff_size: 50000

  # Agent limits
  max_files_to_browse: 20        # Per agent, to control API costs
  max_browse_depth: 3            # How many "hops" from changed files

  # Filtering
  skip_labels:
    - "skip-ai-review"
    - "wip"
    - "do-not-review"
  skip_patterns:
    - "*.lock"
    - "package-lock.json"
    - "yarn.lock"
    - "poetry.lock"
    - "dist/**"
    - "node_modules/**"
    - "*.snap"
    - "__pycache__/**"

  # Comment settings
  comment_mode: "review"         # "review" | "comment" | "both"
  inline_comments: true
  summary_comment: true

  # When to request changes
  request_changes_on:
    - "security_critical"
    - "breaking_change_undocumented"

  # Cost control
  cost_budget_usd: 5.00          # Max estimated cost per PR
  comment_on_forks: false         # Default: skip commenting on fork PRs

# ── LLM Provider Settings ─────────────────────────────
providers:
  fireworks:
    api_key_env: "FIREWORKS_API_KEY"
    base_url: "https://api.fireworks.ai/inference/v1"
  openai:
    api_key_env: "OPENAI_API_KEY"
    base_url: null  # Optional: for Azure or proxies
  anthropic:
    api_key_env: "ANTHROPIC_API_KEY"
  # Future: add local/ollama provider for v2

# ── Repository Browser Settings ───────────────────────
browser:
  # Prefer local git checkout over GitHub API when possible
  prefer_local_git: true
  # GitHub API rate limit threshold for conservative mode
  rate_limit_threshold: 100
```

### 7.3 Environment Variable Overrides

All config values can be overridden via environment variables:

```bash
AI_COUNCIL_AGENTS__SECURITY__MODEL=gpt-4o
AI_COUNCIL_REVIEW__MAX_FILES=100
AI_COUNCIL_REVIEW__COMMENT_MODE=comment
```

---

## 8. Implementation Plan

### 8.1 Phase 0: Foundation & Scaffolding (Week 1)

**Goal:** Project structure, GitHub Action workflow, PR ingestion, basic API client.

**Tasks:**
- [ ] Set up Python project structure (`pyproject.toml`, `src/ai_council_review/`, `uv`)
- [ ] Create GitHub Action workflow YAML
- [ ] Implement `GitHubAPIClient` wrapper (PyGithub + raw REST fallback)
- [ ] Implement `PRIngestor` — load event payload, fetch PR metadata, changed files
- [ ] Implement `RepositoryBrowser` — read files via local git + GitHub API
- [ ] Implement `ConfigLoader` — load `.ai-council/config.yaml` with env overrides
- [ ] Implement PR filtering (size, labels, draft)
- [ ] Add basic logging and error handling
- [ ] Write unit tests for ingestion and browser

**Deliverable:** The action can run, ingest a PR, and print what it found.

### 8.2 Phase 1: Single-Agent Review (Week 1)

**Goal:** One generalist agent that reviews diffs and posts comments.

**Tasks:**
- [ ] Set up LangGraph with basic state machine: `ingest` → `review` → `post`
- [ ] Implement single generalist agent with `RepositoryBrowser` tool
- [ ] Implement `GitHubPublisher` — post review comments and summary
- [ ] Add LLM provider abstraction (Fireworks, OpenAI, Anthropic — all three first-class)
- [ ] Add prompt templates for generalist review
- [ ] Handle patch position calculation for inline comments
- [ ] Test on real PRs

**Deliverable:** Action posts coherent review comments on PRs.

### 8.3 Phase 2: Multi-Agent Council (Week 1–2)

**Goal:** Router + 4 specialist agents + synthesis.

**Tasks:**
- [ ] Implement `RouterAgent` with classification logic
- [ ] Implement `SecurityAgent` with security-specific prompt
- [ ] Implement `QualityAgent` with quality-specific prompt
- [ ] Implement `ArchitectureAgent` with cross-file browsing behavior
- [ ] Implement `SynthesisAgent` with deduplication and formatting
- [ ] Design LangGraph conditional edges: router → parallel agents → synthesis
- [ ] Add agent-specific tool restrictions (e.g., Architecture gets broader browse permissions)
- [ ] Implement agent output schemas (structured JSON findings)
- [ ] Add synthesis logic: merge, deduplicate, resolve conflicts
- [ ] Test with PRs that trigger multiple agents

**Deliverable:** Multi-agent reviews with specialized feedback.

### 8.4 Phase 3: Polish & Hardening (Week 1)

**Goal:** Production-ready error handling, cost control, observability.

**Tasks:**
- [ ] Add rate limiting awareness (GitHub API + LLM API)
- [ ] Add retry logic with exponential backoff
- [ ] Add cost tracking (token usage per agent, per PR)
- [ ] Add timeout handling (per-agent timeouts, overall workflow timeout)
- [ ] Add graceful degradation (if one agent fails, others continue)
- [ ] Add debug mode (dump state to artifact for troubleshooting)
- [ ] Add comprehensive logging (structured JSON logs)
- [ ] Add test suite with mock GitHub API
- [ ] Write documentation (README, configuration guide, troubleshooting)
- [ ] Performance test on large PRs

**Deliverable:** Production-ready v1.0.

### 8.5 Total Estimate: 4–5 Weeks

| Phase | Duration | Output |
|-------|----------|--------|
| 0 — Foundation | 1 week | Scaffolding, ingestion, browser |
| 1 — Single Agent | 1 week | Working end-to-end review |
| 2 — Multi-Agent | 1–2 weeks | Specialist agents + synthesis |
| 3 — Polish | 1 week | Production-ready |
| **Total** | **4–5 weeks** | **v1.0 Release** |

---

## 9. Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Orchestration** | LangGraph | Native multi-agent support, state machines, parallel execution, conditional edges |
| **LLM Interface** | LangChain | Unified interface for multiple providers, tool calling, structured output |
| **GitHub API** | PyGithub + raw REST | PyGithub for convenience, raw REST for edge cases (diffs, rate limit headers) |
| **Local Git** | Git CLI (via subprocess) | Free file reads, no rate limit, for files in checked-out repo |
| **Configuration** | Pydantic + YAML | Type-safe config loading with validation |
| **Python** | 3.11+ | Modern Python with async support, type hints |
| **Package Management** | uv | Fast, modern Python package manager (replaces pip/poetry) |
| **Deployment** | GitHub Actions | Native CI integration, no infrastructure needed |
| **Testing** | pytest + pytest-asyncio | Standard Python testing |
| **Logging** | structlog | Structured JSON logging for observability |

### 9.1 Dependencies (pyproject.toml)

Dependencies are managed via `uv` and declared in `pyproject.toml`. No `requirements.txt` files.

```toml
[project]
name = "ai-council-review"
version = "0.1.0"
description = "Multi-agent AI code review for GitHub Actions"
requires-python = ">=3.11"
dependencies = [
    "langgraph>=0.3.0",
    "langchain>=0.3.0",
    "langchain-fireworks>=0.3.0",
    "langchain-openai>=0.3.0",
    "langchain-anthropic>=0.3.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "PyYAML>=6.0",
    "PyGithub>=2.1.0",
    "requests>=2.31.0",
    "structlog>=24.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "respx>=0.21.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
]
```

**Installing dependencies:**
```bash
# Install project + dev dependencies
uv pip install -e ".[dev]"

# Or in CI (system-wide, no venv needed in containers)
uv pip install --system -e ".[dev]"
```

---

## 10. Project Structure

```
ai-council-code-review/
├── .github/
│   └── workflows/
│       ├── ci.yml                     # Project CI: test, lint, type check
│       └── ai-council-review.yml      # Self-dogfood: run our own review on PRs
├── src/
│   └── ai_council_review/
│       ├── __init__.py
│       ├── __main__.py                # Entry point: python -m ai_council_review
│       ├── config.py                  # Config loading & validation (Pydantic)
│       ├── github_client.py           # GitHub API wrapper (PyGithub + REST)
│       ├── pr_ingestor.py             # PR metadata & diff ingestion
│       ├── repository_browser.py      # File reading tools (git + API)
│       ├── graph.py                   # LangGraph state machine
│       ├── publisher.py             # Post review comments to GitHub
│       ├── models.py                  # Pydantic models for state, findings, comments
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base.py                # Base agent class
│       │   ├── router.py              # Router agent
│       │   ├── security.py            # Security agent
│       │   ├── quality.py             # Code quality agent
│       │   ├── architecture.py        # Architecture agent
│       │   └── synthesis.py           # Synthesis agent
│       └── prompts/
│           ├── router.txt
│           ├── security.txt
│           ├── quality.txt
│           ├── architecture.txt
│           └── synthesis.txt
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_github_client.py
│   ├── test_repository_browser.py
│   ├── test_pr_ingestor.py
│   ├── test_agents/
│   │   ├── test_router.py
│   │   ├── test_security.py
│   │   ├── test_quality.py
│   │   ├── test_architecture.py
│   │   └── test_synthesis.py
│   └── fixtures/
│       ├── pr_payload.json
│       ├── changed_files.json
│       └── config.yaml
├── examples/
│   └── .ai-council/
│       └── config.yaml                # Example configuration
├── pyproject.toml                     # uv-managed project config
├── uv.lock                            # uv lockfile (generated)
├── README.md
├── AGENTS.md                          # Project conventions & branching
├── LICENSE
└── reference/                          # Research & reference docs
    ├── architecture.md
    ├── gh-api-python-patterns.md
    ├── gh-actions-workflow-patterns.md
    └── gh-actions-pr-payloads.md
```

---

## 11. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **GitHub API rate limits** | Review fails mid-run | Track API calls; use local git for file reads; implement conservative mode |
| **LLM API costs** | Expensive for large PRs | Hard PR size limits; configurable model selection (cheap for router); token tracking |
| **LLM context overflow** | Truncated diffs, missed issues | Chunk files intelligently; prioritize changed lines; use file browser for context instead of dumping everything |
| **Incorrect inline positions** | Comments appear on wrong lines | Rigorous patch parsing; unit tests with sample diffs; validate positions before posting |
| **Agent hallucinations** | False positives, noise | Synthesis agent deduplicates; configurable severity thresholds; clear "AI-generated" disclaimers |
| **Security: secrets in PRs** | LLM sees API keys | Same risk as any code review; agents don't store or transmit code beyond the review context |
| **Fork PRs** | `GITHUB_TOKEN` is read-only | **Skip by default** (`comment_on_forks: false`). Users can opt-in via config if they understand `pull_request_target` security trade-offs. |
| **Workflow timeout** | Large PRs hit 15-min limit | PR size filtering; per-agent timeouts; chunked processing |

---

## 12. Future Roadmap (Post-v1)

### v2: Persistence, Memory & DeepAgents
- **DeepAgents integration:** Explore specialized agent libraries for advanced reasoning and tool-use patterns
- Vector store (ChromaDB/pgvector) for semantic file search
- Graph database (NetworkX) for dependency tracking
- Review history in SQLite/PostgreSQL
- Incremental review (only re-review changed commits)
- False positive learning loop

### v3: Intelligence & Scale
- Automatic convention detection ("this project uses X pattern")
- Predictive hot-path analysis
- Custom agent creation via YAML
- Multi-repo support
- Team-level policy enforcement

### v4: Integration Expansion
- GitLab support
- CLI tool for local review
- IDE plugin (VS Code)
- Slack/Teams notifications

---

## 13. Open Questions

1. **Fireworks.ai Model Selection:** Fireworks models are prefixed with `accounts/fireworks/models/`. Should we provide a simplified alias mapping (e.g., `fireworks/llama-3.1-70b` → full path) in the config loader for better UX?

2. **Cost Tracking Accuracy:** The `$5.00` budget is a soft limit based on estimated token usage. Should we implement a hard stop (abort review if estimate exceeds budget) or just a warning? Fireworks.ai pricing may vary by model — do we need a pricing table in config?

3. **Language-Agnostic Prompts:** While prompts are language-agnostic, should we include a `language` field in config so agents can mention the primary language in their system prompts? Or keep it fully inferred from file extensions?

---

## 14. References

- `reference/architecture.md` — Full architecture vision with persistence layer
- `reference/gh-api-python-patterns.md` — GitHub API patterns for Python agents
- `reference/gh-actions-workflow-patterns.md` — Workflow design, checkout, security
- `reference/gh-actions-pr-payloads.md` — PR event payloads, context, filtering

---

*Document version: 1.0*
*Date: 2026-06-02*
*Status: Specification — Ready for implementation review*
