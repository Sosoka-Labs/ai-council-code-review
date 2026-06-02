# Team Handoff — AI Council Code Review

**Date:** 2026-06-02
**Current Branch:** `feature/sprint-2-multi-agent`
**Status:** Sprints 0, 1, 2 complete. Ready for Sprint 3: Production Hardening.
**Last Commit:** `7d55fda` — "feat: sprint 2 multi-agent council — router, security, quality, architecture, synthesis agents + parallel graph"

---

## 1. What Has Been Built

### Sprint 0: Foundation (feature/sprint-0-foundation)
- **Project structure:** `src/ai_council_review/`, `tests/`, `pyproject.toml`, `uv` venv
- **CI/CD:** `.github/workflows/ci.yml` and `ai-council-review.yml` (self-dogfooding workflow)
- **Core modules:**
  - `models.py` — Pydantic models: `FileInfo`, `Finding`, `ReviewComment`, `PRMetadata`, `ReviewState`
  - `config.py` — YAML config loader with `AI_COUNCIL__` env overrides
  - `exceptions.py` — Custom exception hierarchy
  - `github_client.py` — PyGithub + REST wrapper with retry logic
  - `pr_ingestor.py` — Event payload ingestion, filtering, skip logic
  - `repository_browser.py` — Local git + GitHub API file browser
  - `__main__.py` — CLI entry point
- **Tests:** `test_models.py`, `test_config.py` (16 tests)
- **Fixtures:** `pr_payload.json`, `changed_files.json`, `config.yaml`

### Sprint 1: Single-Agent End-to-End (feature/sprint-1-single-agent)
- **LLM provider:** `llm_provider.py` — factory for Fireworks, OpenAI, Anthropic
- **Patch parser:** `patch_parser.py` — unified diff parser, position-to-line mapping
- **Prompt system:** `prompts.py` + Jinja2-based `.txt` prompt files in `prompts/`
- **Generalist agent:** `agents/base.py` + `agents/generalist.py` — single agent with `RepositoryBrowser` tool
- **Publisher:** `publisher.py` — posts PR reviews + inline comments, batching (>100), validation
- **Graph:** `graph.py` — LangGraph state machine: `ingest` → `review` → `post`
- **Tests:** `test_llm_provider.py`, `test_patch_parser.py`, `test_publisher.py` (33 total)

### Sprint 2: Multi-Agent Council (feature/sprint-2-multi-agent)
- **Router agent:** `agents/router.py` — analyzes PR and decides which agents to run
- **Security agent:** `agents/security.py` — vulnerabilities, injection, auth, crypto
- **Quality agent:** `agents/quality.py` — bugs, type safety, tests, code smells
- **Architecture agent:** `agents/architecture.py` — cross-file impact, API design, docs
- **Synthesis agent:** `agents/synthesis.py` — deduplicates, prioritizes, merges findings
- **Updated graph:** `graph.py` — `ingest` → `router` → `[security, quality, architecture]` (parallel) → `synthesis` → `post`
- **Prompts:** `router.txt`, `security.txt`, `quality.txt`, `architecture.txt`, `synthesis.txt`

### All branches merged
- `feature/sprint-0-foundation` → `main` (commit `d7b9ac9`)
- `feature/sprint-1-single-agent` → `main` (commit `d31384d`)
- `feature/sprint-2-multi-agent` → current branch (commit `7d55fda`)

---

## 2. Architecture & Patterns

### State Machine (LangGraph)
```
ingest → router → [security, quality, architecture] (parallel) → synthesis → post
```

- `ReviewState` is the state object passed through all nodes
- Each node returns a `dict` of updates to the state
- LangGraph handles state merging
- All agents share `RepositoryBrowser` for cross-file awareness

### Agent Pattern
All agents follow the same pattern:
1. **Prompt rendering** via `prompts.py` with Jinja2 substitution
2. **LLM invocation** via `LLMProviderFactory.from_config()`
3. **Structured output** via `llm.with_structured_output(PydanticModel)`
4. **Fallback parsing** if structured output fails (extract JSON from text)
5. **Tool binding** for `RepositoryBrowser` (read_file tool)

### Key Files
```
src/ai_council_review/
├── __init__.py
├── __main__.py           # Entry point, CLI args, graph execution
├── models.py             # Pydantic models (FileInfo, Finding, ReviewState, etc.)
├── config.py             # Config loader (YAML + env overrides)
├── exceptions.py         # Custom exceptions
├── github_client.py      # GitHub API wrapper (PyGithub + REST)
├── pr_ingestor.py        # PR ingestion, filtering, skip logic
├── repository_browser.py # File browser (local git + GitHub API)
├── llm_provider.py       # LLM factory (Fireworks, OpenAI, Anthropic)
├── patch_parser.py       # Unified diff parser
├── prompts.py            # Prompt loading utilities
├── publisher.py          # Posts reviews to GitHub
├── graph.py              # LangGraph state machine
├── agents/
│   ├── __init__.py
│   ├── base.py           # Abstract BaseAgent
│   ├── generalist.py     # Single agent (Sprint 1)
│   ├── router.py         # Routing agent (Sprint 2)
│   ├── security.py      # Security agent (Sprint 2)
│   ├── quality.py        # Quality agent (Sprint 2)
│   ├── architecture.py   # Architecture agent (Sprint 2)
│   └── synthesis.py      # Synthesis agent (Sprint 2)
└── prompts/
    ├── generalist.txt
    ├── router.txt
    ├── security.txt
    ├── quality.txt
    ├── architecture.txt
    └── synthesis.txt
```

---

## 3. Sprint 3: Production Hardening

### Goal
The system is reliable, observable, and cost-controlled. It degrades gracefully under pressure.

### Tasks

| # | Task | File(s) | Effort |
|---|------|---------|--------|
| **3.1** | Cost tracking and budget enforcement | `cost_tracker.py` | 3h |
| **3.2** | GitHub API rate limit awareness | `github_client.py` | 2h |
| **3.3** | Retry logic with exponential backoff | `github_client.py`, `llm_provider.py` | 2h |
| **3.4** | Per-agent and overall timeouts | `graph.py`, agents | 2h |
| **3.5** | Graceful degradation | `graph.py`, `publisher.py` | 2h |
| **3.6** | Debug mode (state dump artifact) | `__main__.py`, `debug.py` | 2h |
| **3.7** | Structured logging with `structlog` | All modules | 2h |
| **3.8** | Fork PR detection and skip logic | `pr_ingestor.py` | 1h |
| **3.9** | Write `README.md` | `README.md` | 3h |
| **3.10** | Write `examples/.ai-council/config.yaml` | `examples/` | 1h |
| **3.11** | Performance test on large PRs | Manual | 3h |

### Acceptance Criteria
- `pytest` passes with >85% coverage
- ruff, mypy, CI all green
- Large PR (50 files, 2000 lines) completes within 10 minutes and under $5.00
- Intentionally failing one agent does not crash the workflow
- Debug artifact can be downloaded and inspected
- README is sufficient for a new user to set up the action

### Risks
- Timeout logic too aggressive → Make configurable, generous defaults
- Cost estimation inaccurate → Conservative estimates, track actual vs estimated
- Debug artifact leaks secrets → Strip API keys and tokens before writing

---

## 4. Development Environment

### Setup
```bash
# Use uv (already installed at ~/.local/bin)
export PATH="$HOME/.local/bin:$PATH"

# Create venv and install
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
pytest -v

# Run lint
ruff check .
ruff format --check .

# Run type check
mypy src/ai_council_review
```

### Key Conventions
- **Python 3.11+**, type hints everywhere
- **ruff** for linting (100 char line length)
- **mypy** strict mode for type checking
- **Pydantic** for all data models
- **structlog** for logging (JSON in CI, console in dev)
- **Google-style** docstrings
- **One concept per module**
- Prompts are `.txt` files (not inline strings)

---

## 5. Known Issues & TODOs

### Current Warnings
- `pyproject.toml` has unused `module = ['langchain.*']` in mypy overrides — can be cleaned up
- Fireworks client has Pydantic V1 deprecation warnings (upstream, not our code)

### Integration Tests Pending
- **Sprint 1.10** — Test on a real PR (requires real GitHub token + LLM API key)
- **Sprint 2.13** — Test on PRs that trigger multiple agents

### Technical Debt
- `graph.py` uses `Any` return type for `build_graph()` — LangGraph types are complex
- `agents/base.py` has `run()` method that tries structured output first, then fallback — this pattern is duplicated in each agent
- Patch position math is tricky — extensive unit tests exist, but real GitHub validation needed

### Sprint 3 Specific Notes
- **Cost tracking (3.1):** No token/cost tracking exists yet. Need to estimate tokens per agent call. Consider using tiktoken for token counting, or LLM response metadata.
- **Rate limits (3.2):** `github_client.py` already tracks `X-RateLimit-Remaining` in `_request()`. Need to add threshold check and conservative mode.
- **Retry (3.3):** `github_client.py` already has 3 retries. Need to add jitter and LLM retry logic.
- **Timeouts (3.4):** No timeout logic exists. Consider `asyncio.timeout` or `signal` for per-agent timeouts.
- **Debug (3.6):** `DEBUG=1` env var should dump `review_state.json` before posting. Must strip secrets.
- **Fork detection (3.8):** `pr_ingestor.py` already has `is_fork` flag. Skip logic is already there. May need enhancement.

---

## 6. Quick Reference

### Running the Action Locally
```bash
# Dry run (no GitHub posting)
python -m ai_council_review \
  --pr-number 42 \
  --repo owner/repo \
  --dry-run

# With real GitHub token
export GITHUB_TOKEN=ghp_xxx
export FIREWORKS_API_KEY=fw_xxx
python -m ai_council_review \
  --pr-number 42 \
  --repo owner/repo
```

### Config Example
```yaml
version: "1"
review_depth: standard
max_files: 50
max_lines: 2000
budget_usd: 5.0
comment_on_forks: false
skip_drafts: true
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
```

### Adding a New Agent
1. Create `src/ai_council_review/agents/<agent_name>.py` (inherit from `BaseAgent`)
2. Add prompt `src/ai_council_review/prompts/<agent_name>.txt`
3. Add agent config to `config.py` (optional, defaults exist)
4. Register in `graph.py` (add node + edges)
5. Add tests in `tests/test_agents/test_<agent_name>.py`

---

## 7. Resources

- **SPRINT_PLAN.md** — Task breakdown for all 4 sprints
- **AGENTS.md** — Project conventions, coding style, branching strategy
- **reference.md** — Full v1 specification
- **reference/** — Research materials:
  - `architecture.md` — Brainstorm & architecture design
  - `gh-api-python-patterns.md` — GitHub API patterns
  - `gh-actions-workflow-patterns.md` — Actions workflow patterns
  - `gh-actions-pr-payloads.md` — PR event payloads

---

## 8. Next Steps

1. **Create branch:** `feature/sprint-3-hardening` from `main`
   ```bash
   git checkout main
   git pull
   git checkout -b feature/sprint-3-hardening
   git merge feature/sprint-2-multi-agent --no-edit
   ```
2. **Start with 3.1 (cost tracking)** or 3.7 (structured logging) — both are foundational
3. **Write tests as you go** — target >85% coverage
4. **Run full verification after each module:**
   ```bash
   pytest -v && ruff check . && ruff format --check . && mypy src/ai_council_review
   ```
5. **Commit regularly** — small, focused commits with conventional commit messages

---

*Handoff prepared by: AI Council Lead*
*Date: 2026-06-02*
