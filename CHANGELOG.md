# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
