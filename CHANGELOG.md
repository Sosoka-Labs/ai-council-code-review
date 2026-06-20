# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-20

Caps the number of inline comments per review. A real PR produced 77 findings; posting all of them as inline comments in a single review triggered a GitHub `502` and the secondary content-creation rate limit, and the review failed to post. Inline comments are now ranked and capped.

### Added

- **`max_inline_comments`** (default `20`) — hard cap on inline comments posted per review. Findings beyond the cap are listed in the review body instead of dropped.
- **`min_confidence`** (default `0.0`) — minimum finding confidence required to post inline; lower-confidence findings are withheld to the body.

### Changed

- **Inline comments are now ranked and capped.** Findings are deduplicated, filtered by `min_confidence`, ranked by severity (then confidence as a tiebreaker), and limited to `max_inline_comments`. Withheld findings (over the cap, below the threshold, or outside changed lines) are enumerated in the review body so nothing is lost. Previously every finding was posted inline.
- Review comment batch size lowered from 100 to 30 as defense-in-depth against oversized-review `502`s.

## [0.1.1] - 2026-06-20

Bugfix release. Eliminates a review hang caused by GitHub API rate limiting during cross-file browsing.

### Fixed

- **Cross-file browsing no longer hangs the review.** When the reviewed repository is already checked out (the normal GitHub Actions case), specialists now read unchanged files directly from the working tree and make **zero** GitHub Contents API calls. Previously the browser always attached an API client and silently fell back to it, so parallel specialists could exhaust the rate limit.
- **Rate-limit waits are now bounded.** A `403` from the GitHub API previously slept until the reset window (observed: ~59 minutes), stalling the job until its CI timeout. The client now caps the wait and raises `RateLimitError` past the cap, so the run fails fast instead of hanging.

### Changed

- The repository browser reads HEAD/working-tree files from disk (with a path-traversal guard) and only uses `git show` for explicit non-HEAD refs; the GitHub Contents API is a last resort, used only when no local checkout is present.
- The selected browser mode (filesystem-only vs. API-backed) is now logged at `INFO` so it is visible without enabling debug.

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

[Unreleased]: https://github.com/Sosoka-Labs/ai-council-code-review/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Sosoka-Labs/ai-council-code-review/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/Sosoka-Labs/ai-council-code-review/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Sosoka-Labs/ai-council-code-review/releases/tag/v0.1.0
