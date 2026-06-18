# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-18

Initial public release.

### Added

- Multi-agent council code review for GitHub Actions: a **router**, six specialist agents (**security, quality, architecture, performance, documentation, devops**), and a **synthesis** agent that deduplicates findings and emits a verdict (`approve` / `comment` / `request_changes`), posted as inline PR comments.
- **Data-driven agent registry** (`AgentSpec`) — adding a new specialist is a single registry entry plus a prompt; the graph, router catalog, and synthesis categories derive from it automatically.
- **Real cross-file browsing** — specialists run a bounded agentic tool loop to read unchanged repository files (hard caps on tool rounds, tool calls, and file size), degrading gracefully to diff-only when no GitHub token is available.
- **Bindable domain skills** — opt-in, user-defined `SKILL.md` files under `.ai-council/skills/` in the reviewed repository inject project conventions and known pitfalls into an agent's prompt; bound per agent, via a `"*"` sentinel, or as a repo-wide default. Ships with `n-plus-one`, `docstring-style`, `github-actions-hardening`, and `oauth-pitfalls` examples.
- **Multi-provider support** — OpenAI (default), Anthropic, and Fireworks; per-agent provider/model selection with shorthand model aliases.
- **Cost & safety controls** — configurable per-PR budget ($5.00 default), router gating, hard PR-size limits, and prompt-injection hardening that treats untrusted PR/agent content as data.
- **Configurable PR filtering** — size limits, labels, draft PRs, and glob skip patterns; fork detection with read-only-token handling.
- Startup API-key validation, structured logging, debug state dumps, and graceful degradation (one agent failing does not crash the run).
- **CI/CD & repo automation** — SHA-pinned actions, least-privilege workflow permissions, concurrency control, dependency caching, Dependabot, CodeQL scanning (on public repos), an automated release workflow, and a PR template.
- **Stateless design** — no database, vector store, or persistence layer.

[Unreleased]: https://github.com/Sosoka-Labs/ai-council-code-review/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Sosoka-Labs/ai-council-code-review/releases/tag/v0.1.0
