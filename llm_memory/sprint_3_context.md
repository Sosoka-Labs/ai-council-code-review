# Sprint 3 Context — Production Hardening

## Branch
`feature/sprint-3-hardening`

## Goal
Make the system reliable, observable, and cost-controlled. It degrades gracefully under pressure.

## Current State (post-Sprint 2)
- LangGraph state machine: `ingest` → `router` → `[security, quality, architecture]` (parallel) → `synthesis` → `post`
- `structlog` already imported in most modules (but not all)
- `github_client.py` has basic retry (3 attempts, 2^attempt sleep) and tracks `X-RateLimit-Remaining`
- `pr_ingestor.py` already handles fork detection and skip logic
- `ReviewState` has `costs: dict[str, Any]` and `api_calls: int` fields
- `CouncilConfig` has `budget_usd: float = 5.0`
- `graph.py` has parallel agent execution but no timeout or graceful degradation
- `__main__.py` has dry-run but no debug artifact mode

## Key Files to Modify
- `src/ai_council_review/exceptions.py` — Add `BudgetExceededError`, `TimeoutError`
- `src/ai_council_review/config.py` — Add timeout, debug, rate limit threshold fields
- `src/ai_council_review/models.py` — Add `CostRecord` model
- `src/ai_council_review/cost_tracker.py` — NEW: Track LLM call costs, enforce budget
- `src/ai_council_review/debug.py` — NEW: Dump state artifacts, strip secrets
- `src/ai_council_review/github_client.py` — Add jitter to retry, rate limit conservative mode
- `src/ai_council_review/llm_provider.py` — Add retry wrapper for LLM calls
- `src/ai_council_review/graph.py` — Add per-agent timeouts, graceful degradation, cost tracking
- `src/ai_council_review/__main__.py` — Add debug mode, state dump before posting
- `src/ai_council_review/agents/base.py` — Integrate cost tracking into `run()`
- `tests/test_cost_tracker.py` — NEW
- `tests/test_debug.py` — NEW
- `tests/test_graph.py` — NEW (or update existing)

## Acceptance Criteria
- `pytest` passes with >85% coverage
- ruff, mypy, CI all green
- Intentionally failing one agent does not crash the workflow
- Debug artifact can be downloaded and inspected
- README is sufficient for a new user to set up the action

## Conventions
- Python 3.11+, type hints everywhere
- ruff (100 char line length)
- mypy strict mode
- Pydantic for all data models
- structlog for logging (JSON in CI, console in dev)
- Google-style docstrings
- One concept per module
- Never hardcode secrets

## Token Cost Estimates (for cost_tracker)
We use conservative estimates since we don't have exact token counters for all providers:
- Input: ~$0.50 / 1M tokens (for Fireworks Llama 3.1 70B)
- Output: ~$0.50 / 1M tokens
- Approximate: count characters / 4 for token estimate, or use prompt length + max_tokens
- Capture actual usage from response metadata when available (`usage_metadata` on LangChain responses)

## Retry Strategy
- GitHub API: exponential backoff with jitter (2^attempt + random(0,1))
- LLM calls: 3 retries with exponential backoff, only on transient errors (RateLimitError, connection errors)
- Max retry delay: 60 seconds

## Timeout Strategy
- Per-agent timeout: 5 minutes default (configurable)
- Overall graph timeout: 10 minutes default (configurable)
- Use `concurrent.futures.ThreadPoolExecutor` for cross-platform agent timeout
- If agent times out, log warning and return empty findings (graceful degradation)

## Debug Artifact
- When `AI_COUNCIL__DEBUG=1` or `--debug` flag, dump `review_state.json` before posting
- Strip all API keys, tokens, and secrets from the dump
- Write to `ai_council_review_debug.json` in the working directory
