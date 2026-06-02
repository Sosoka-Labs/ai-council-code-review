# Sprint Plan — AI Council Code Review v1.0

> **Purpose:** A concrete, task-level plan for building the AI Council Code Review system. Each sprint has clear deliverables, acceptance criteria, and known risks. This document is the entry point for every implementation session.
>
> **Status:** Not started
> **Based on:** `reference.md` v1.0 specification
> **Target:** v1.0 release in 4–5 sprints

---

## Sprint Overview

| Sprint | Focus | Duration | Key Deliverable |
|--------|-------|----------|-----------------|
| **Sprint 0** | Foundation & Scaffolding | 1 week | Project structure, CI, PR ingestion, repo browser |
| **Sprint 1** | Single-Agent End-to-End | 1 week | One generalist agent that posts review comments on real PRs |
| **Sprint 2** | Multi-Agent Council | 1–2 weeks | Router + 4 specialists + synthesis, parallel execution |
| **Sprint 3** | Production Hardening | 1 week | Cost control, rate limits, timeouts, error handling, docs |
| **Sprint 4** | Self-Dogfood & Release | 1 week | Run on this repo, fix edge cases, tag v1.0 |

---

## Sprint 0: Foundation & Scaffolding

**Goal:** The codebase exists, CI is green, and the action can ingest a PR and print its findings.

### Tasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| 0.1 | Set up project structure (`src/ai_council_review/`, `pyproject.toml`, `uv`) | — | 2h | `uv pip install -e ".[dev]"` works; `python -c "import ai_council_review"` succeeds |
| 0.2 | Configure ruff, mypy, pytest in `pyproject.toml` | — | 1h | `ruff check .`, `mypy src/ai_council_review`, `pytest` all pass on empty project |
| 0.3 | Create `.github/workflows/ci.yml` | — | 1h | CI workflow runs on PRs; pytest, ruff, mypy steps all green |
| 0.4 | Implement `models.py` — Pydantic models for `FileInfo`, `ReviewComment`, `ReviewState`, `PRMetadata` | — | 2h | All models have type hints, validation, and docstrings. Unit tests pass. |
| 0.5 | Implement `config.py` — Pydantic config loader with env overrides | — | 3h | Loads `.ai-council/config.yaml` with `AI_COUNCIL__` env overrides. Invalid config raises clear `ValidationError`. Unit tests pass. |
| 0.6 | Implement `github_client.py` — wrapper around PyGithub + raw REST | — | 4h | Can fetch PR metadata, changed files, file contents, diff. Rate limit headers tracked. Retry with backoff. Unit tests with `respx` mocks. |
| 0.7 | Implement `pr_ingestor.py` — load event payload, compute stats, filter PRs | — | 3h | Loads `GITHUB_EVENT_PATH` or CLI args. Computes file count, line stats. Skips drafts, labels, oversized PRs. Unit tests with fixtures. |
| 0.8 | Implement `repository_browser.py` — read files via local git + GitHub API | — | 4h | `get_file()`, `get_file_at_base()`, `get_file_at_head()`, `list_directory()`, `find_files()`, `file_exists()`. Prefers local git. Falls back to GitHub API. Tracks `api_calls`. Unit tests. |
| 0.9 | Write fixture files (`pr_payload.json`, `changed_files.json`, `config.yaml`) | — | 2h | Fixtures are anonymized but structurally real. Used by unit tests. |
| 0.10 | Create `__main__.py` entry point — CLI args → ingest → print | — | 2h | `python -m ai_council_review --pr-number 42 --repo owner/repo` prints structured PR metadata. No LLM calls yet. |

### Sprint 0 Risks

| Risk | Mitigation |
|------|------------|
| GitHub API mocking is flaky | Use `respx` with strict URL matching; include real response samples in fixtures |
| uv not available in CI | Use `astral-sh/setup-uv@v5` action; fallback to pip if needed |
| Patch position math is tricky | Defer to Sprint 1; Sprint 0 only needs file contents |

### Sprint 0 Definition of Done

- [ ] `pytest` passes with >80% coverage on new code
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `mypy src/ai_council_review` passes with zero errors
- [ ] CI workflow runs green on a test PR
- [ ] Running the entry point on a real PR prints correct metadata, changed files, and file contents

---

## Sprint 1: Single-Agent End-to-End

**Goal:** One generalist agent reviews diffs and posts coherent inline + summary comments on real PRs.

### Tasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| 1.1 | Implement `llm_provider.py` — factory for Fireworks, OpenAI, Anthropic | — | 3h | `LLMProviderFactory.create("fireworks", model="...", api_key="...")` returns a `BaseChatModel`. All three providers tested. |
| 1.2 | Implement `patch_parser.py` — parse unified diff, map line numbers to positions | — | 4h | `parse_patch(patch)` returns hunks with `old_start`, `new_start`, `lines`. `get_added_line_positions(patch)` returns `(position, new_line, text)`. Unit tests with real GitHub patches. |
| 1.3 | Implement prompt loading from `.txt` files in `src/ai_council_review/prompts/` | — | 2h | `load_prompt("generalist")` reads `prompts/generalist.txt`. Supports Jinja2-style variable substitution. |
| 1.4 | Write `prompts/generalist.txt` — language-agnostic system prompt | — | 2h | Prompt covers: code quality, security, architecture, docs. Explicitly language-agnostic. |
| 1.5 | Implement `agents/base.py` — `BaseAgent` class with `run()`, `get_tools()`, `get_prompt()` | — | 3h | Abstract class. Concrete agents inherit. Handles LLM call, tool binding, and structured output. |
| 1.6 | Implement `agents/generalist.py` — single agent with `RepositoryBrowser` tool | — | 4h | Agent receives changed files + browser tool. Returns list of `Finding` objects with `path`, `position`, `severity`, `body`. |
| 1.7 | Implement `publisher.py` — post reviews and comments to GitHub | — | 3h | `post_review(summary, inline_comments)` creates a PR review. `post_comment(body)` creates a general PR comment. Handles batching (>100 comments). |
| 1.8 | Implement `graph.py` — LangGraph state machine: `ingest` → `review` → `post` | — | 4h | `StateGraph` with 3 nodes. Compiles and runs. State typed with `ReviewState`. |
| 1.9 | Wire entry point to run the full graph | — | 2h | `python -m ai_council_review --pr-number 42 --repo owner/repo` runs the graph and posts a review. |
| 1.10 | Test on a real PR in a test repo | — | 4h | Review is posted. Inline comments land on correct lines. Summary is coherent. |

### Sprint 1 Risks

| Risk | Mitigation |
|------|------------|
| Patch position calculation is wrong | Extensive unit tests with real GitHub diffs; manual validation on test PRs |
| LLM outputs unstructured text | Use `with_structured_output()` or Pydantic parser; retry on parse failure |
| Agent hallucinates file paths | Validate all `path` values against `changed_files` before posting |
| Cost exceeds budget on first test | Set hard PR size limits; test on tiny PRs first |

### Sprint 1 Definition of Done

- [ ] `pytest` passes with >80% coverage
- [ ] ruff, mypy, CI all green
- [ ] Agent posts a review on a real PR with both inline and summary comments
- [ ] Inline comments appear on correct diff lines (verified manually)
- [ ] Review is coherent and actionable (subjective — human review)

---

## Sprint 2: Multi-Agent Council

**Goal:** Router dispatches 4 specialist agents in parallel. Synthesis merges findings. The review is structured by agent type.

### Tasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| 2.1 | Write `prompts/router.txt` | — | 2h | Prompt analyzes changed files and returns `agents_needed` + `review_depth` + reasoning. |
| 2.2 | Implement `agents/router.py` | — | 3h | Takes `changed_files`, `pr_title`, `pr_body`. Returns structured JSON with `agents_needed`. Uses cheap model. |
| 2.3 | Write `prompts/security.txt` | — | 2h | Security-focused prompt. Language-agnostic. OWASP-oriented. |
| 2.4 | Implement `agents/security.py` | — | 3h | Uses `RepositoryBrowser` to read adjacent auth files. Returns `Finding` objects tagged `security`. |
| 2.5 | Write `prompts/quality.txt` | — | 2h | Quality-focused prompt. Language-agnostic. Covers bugs, tests, complexity. |
| 2.6 | Implement `agents/quality.py` | — | 3h | Uses `RepositoryBrowser` to check `tests/` directory. Returns `Finding` objects tagged `quality`. |
| 2.7 | Write `prompts/architecture.txt` | — | 2h | Architecture-focused prompt. Language-agnostic. Cross-file impact. |
| 2.8 | Implement `agents/architecture.py` | — | 4h | Broader `RepositoryBrowser` permissions. Reads docs, lock files, migrations. Returns `Finding` objects tagged `architecture`. |
| 2.9 | Write `prompts/synthesis.txt` | — | 2h | Synthesis prompt. Deduplicates, prioritizes, formats markdown. |
| 2.10 | Implement `agents/synthesis.py` | — | 4h | Merges all agent outputs. Deduplicates by `path`+`position`+`message`. Resolves severity. Generates summary markdown. |
| 2.11 | Update `graph.py` — conditional routing + parallel agent execution | — | 4h | `router` → conditional edges → parallel agents (`security`, `quality`, `architecture`) → `synthesis` → `post`. LangGraph `Send` or parallel mapping. |
| 2.12 | Implement `Finding` model and agent output schemas | — | 2h | Pydantic model with `path`, `position`, `severity`, `category`, `body`, `confidence`. |
| 2.13 | Test on PRs that trigger multiple agents | — | 4h | Security + Quality + Architecture all fire on a relevant PR. Review is posted. No duplicate comments. |

### Sprint 2 Risks

| Risk | Mitigation |
|------|------------|
| Parallel agents exceed GitHub rate limit | Cap concurrent file reads; sequential agent execution as fallback |
| Synthesis produces duplicate comments | Deduplication by hash of `(path, position, normalized_body)` |
| Router misclassifies and skips important agents | Config override: user can force `agents_needed` in `.ai-council/config.yaml` |
| Agent output schemas drift | Strict Pydantic validation; fallback to unstructured text if parsing fails |

### Sprint 2 Definition of Done

- [ ] `pytest` passes with >80% coverage
- [ ] ruff, mypy, CI all green
- [ ] Router correctly dispatches agents on diverse PR types (verified manually)
- [ ] Multi-agent review posted on a real PR with no duplicate comments
- [ ] Review summary clearly attributes findings to agent types (Security, Quality, Architecture)
- [ ] Architecture agent reads at least 3 unchanged files per relevant PR (verified in logs)

---

## Sprint 3: Production Hardening

**Goal:** The system is reliable, observable, and cost-controlled. It degrades gracefully under pressure.

### Tasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| 3.1 | Implement cost tracking and budget enforcement | — | 3h | `CostTracker` estimates tokens per agent. If estimate > budget, drops non-critical agents or switches to cheaper models. |
| 3.2 | Implement GitHub API rate limit awareness | — | 2h | Checks `X-RateLimit-Remaining` before every call. If < threshold, switches to conservative mode. |
| 3.3 | Implement retry logic with exponential backoff | — | 2h | All GitHub API calls retry 3x with jitter. All LLM API calls retry 3x with backoff. |
| 3.4 | Implement per-agent and overall timeouts | — | 2h | Router: 30s. Agents: 2min each. Synthesis: 2min. Overall: 10min. Agent times out → skipped gracefully. |
| 3.5 | Implement graceful degradation | — | 2h | If one agent fails, others continue. Log error. If synthesis fails, post individual agent comments. |
| 3.6 | Implement debug mode (state dump artifact) | — | 2h | `DEBUG=1` writes `review_state.json` as a GitHub Actions artifact. Contains all agent outputs, files read, costs. |
| 3.7 | Add structured logging with `structlog` | — | 2h | All modules log with `structlog`. JSON output in CI. Key events: agent start/finish, file read, cost estimate, error. |
| 3.8 | Add fork PR detection and skip logic | — | 1h | Detects `pr.head.repo.full_name != pr.base.repo.full_name`. If `comment_on_forks: false`, skips with a note. |
| 3.9 | Write `README.md` — user-facing quick start guide | — | 3h | Covers: installation, config, secrets, workflow setup, troubleshooting. |
| 3.10 | Write `examples/.ai-council/config.yaml` — complete example | — | 1h | Example config with all agents enabled, all providers documented. |
| 3.11 | Performance test on large PRs (50 files, 2000 lines) | — | 3h | Completes within 10 minutes. Cost < $5.00. No timeouts. |

### Sprint 3 Risks

| Risk | Mitigation |
|------|------------|
| Timeout logic is too aggressive | Make timeouts configurable; default to generous values |
| Cost estimation is inaccurate | Use conservative estimates (over-count tokens); track actual vs estimated |
| Debug artifact leaks secrets | Strip API keys and tokens from state dump before writing |

### Sprint 3 Definition of Done

- [ ] `pytest` passes with >85% coverage
- [ ] ruff, mypy, CI all green
- [ ] Large PR (50 files, 2000 lines) completes within 10 minutes and under $5.00
- [ ] Intentionally failing one agent does not crash the workflow
- [ ] Debug artifact can be downloaded and inspected
- [ ] README is sufficient for a new user to set up the action in their repo

---

## Sprint 4: Self-Dogfood & Release

**Goal:** The action reviews its own PRs. Edge cases are fixed. v1.0 is tagged.

### Tasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| 4.1 | Enable `ai-council-review.yml` on this repo | — | 1h | Workflow file exists. Secrets configured. Runs on every PR to `main`. |
| 4.2 | Fix issues found during self-dogfooding | — | 4h | Review the AI's reviews. Fix any incorrect positions, hallucinations, or poor formatting. |
| 4.3 | Add edge case handling (empty PRs, binary files, renamed files) | — | 2h | Empty PR: skip with note. Binary files: skip in review. Renamed files: check both old and new paths. |
| 4.4 | Add skip logic for generated files (lock files, snapshots, dist/) | — | 1h | `skip_patterns` in config filters out generated files. Unit tests. |
| 4.5 | Final review of `AGENTS.md` and `reference.md` | — | 2h | Docs are accurate and match the code. |
| 4.6 | Tag `v1.0.0` | — | 1h | Git tag created. GitHub release drafted with changelog. |

### Sprint 4 Risks

| Risk | Mitigation |
|------|------------|
| Self-dogfooding reveals major architectural issues | Budget extra time for rework; Sprint 4 is intentionally buffer time |
| Review quality is not good enough for public release | Iterate on prompts; consider delaying tag if needed |

### Sprint 4 Definition of Done

- [ ] This repository's PRs receive AI reviews from its own action
- [ ] Reviews are generally accurate and helpful (subjective — team consensus)
- [ ] Edge cases (empty PR, binary files, renamed files) handled gracefully
- [ ] `v1.0.0` tag exists
- [ ] GitHub release notes summarize features and known limitations

---

## Cross-Sprint Dependencies

```
Sprint 0 (Foundation)
  ├── Sprint 1 (Single Agent)
  │     ├── Sprint 2 (Multi-Agent)
  │     │     ├── Sprint 3 (Hardening)
  │     │     │     └── Sprint 4 (Release)
```

**Hard dependencies:**
- Sprint 1 requires Sprint 0 (models, config, GitHub client, browser, ingestor)
- Sprint 2 requires Sprint 1 (graph, LLM provider, publisher, patch parser)
- Sprint 3 requires Sprint 2 (cost tracking needs multi-agent to be meaningful)
- Sprint 4 requires Sprint 3 (release needs hardening)

**Soft dependencies:**
- Prompts can be refined in parallel with code
- Documentation can be drafted in Sprint 2, finalized in Sprint 3

---

## Session Entry Points

When starting a new session, pick the next uncompleted task from the current sprint. Update this document as tasks complete.

### Current Sprint: Sprint 0

**Next task:** TBD — start with 0.1 (project structure)

### Task Completion Checklist

For each task, before marking it complete:
- [ ] Code written and committed
- [ ] Unit tests pass (`pytest`)
- [ ] Lint passes (`ruff check .`)
- [ ] Type check passes (`mypy`)
- [ ] CI green
- [ ] PR reviewed and merged to `main`

---

*Document version: 1.0*
*Date: 2026-06-02*
*Status: Sprint 0 — Not started*
