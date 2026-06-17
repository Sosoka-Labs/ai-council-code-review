# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Three new specialist agents: **Performance** (N+1 queries, hot-path I/O, complexity), **Documentation** (stale docs, missing docstrings, changelog drift), and **DevOps** (CI/CD, GitHub Actions, Dockerfile, IaC, shell hardening) — bringing the council to six router-gated specialists
- Data-driven agent registry (`AgentSpec`) — adding a new agent is now a single registry entry plus a prompt; the graph, router catalog, and synthesis categories derive from it automatically
- Bindable domain **skills** — `SKILL.md` files under `.ai-council/skills/` inject domain knowledge into an agent's prompt (ships with `n-plus-one`, `docstring-style`, `github-actions-hardening`, `oauth-pitfalls`)
- CI/CD hardening: SHA-pinned actions, least-privilege workflow permissions, concurrency control, dependency caching, Dependabot, CodeQL scanning, automated release workflow, and a PR template

### Changed

- **Cross-file browsing is now genuinely wired in** — specialists run a bounded agentic tool loop to read unchanged repository files (previously advertised but not active), with hard caps on tool rounds, tool calls, and file size; degrades gracefully to diff-only when no token is available
- Adopted a `develop`/`main` branching model (feature branches integrate into `develop`; releases are tagged from `main`)
- Consolidated `review_depth` vocabulary to `standard` (cost-capped specialists) and `deep` (uncapped)

### Fixed

- Hardened untrusted PR/agent content against prompt injection (delimited, treated as data) across router, specialist, and synthesis prompts
- Enforced `max_diff_size` truncation (previously dead config) and PR title/body caps to prevent context-window overflow
- Startup API-key validation now covers all six specialists; router no longer swallows budget-exceeded errors
- Added `gpt-4.1` / `gpt-4.1-mini` pricing so budget enforcement is accurate for those models

## [1.0.0] - 2026-06-08

### Added

- Multi-agent council code review for GitHub Actions (Router, Security, Quality, Architecture, Synthesis)
- Cross-file awareness — agents can browse the repository to check unchanged files for consistency
- Support for three LLM providers: Fireworks.ai (default), OpenAI, and Anthropic
- Per-agent model selection — use cheap models for routing and strong models for synthesis
- Model alias mapping — write `fireworks/llama-3.1-70b` instead of full Fireworks paths
- Startup API key validation with clear, actionable error messages
- Configurable PR filtering (size limits, labels, draft PRs, skip patterns)
- Cost control with configurable per-PR budget ($5.00 default)
- Graceful degradation — one agent failure does not crash the workflow
- Debug mode with structured state dump artifacts
- Fork PR detection and skip logic (disabled by default for security)
- Stateless design — no database, no vector store, no persistence layer

### Changed

- N/A — initial release

### Fixed

- N/A — initial release

### Removed

- N/A — initial release

## [0.1.0] - 2026-06-02

### Added

- Project scaffolding and CI pipeline
- GitHub API client with retry logic and rate limit awareness
- Repository browser for cross-file reading
- Single-agent (generalist) review pipeline
- LangGraph orchestration with state machine

[1.0.0]: https://github.com/Sosoka-Labs/ai-council-code-review/releases/tag/v1.0.0
[0.1.0]: https://github.com/Sosoka-Labs/ai-council-code-review/releases/tag/v0.1.0
