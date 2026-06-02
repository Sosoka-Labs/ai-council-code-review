# AI Council Code Review

A configurable, multi-agent AI code review system for GitHub Actions.

**Key features:**
- **Multi-agent council** — Router, Security, Quality, Architecture, and Synthesis agents review your PRs
- **Cross-file awareness** — Agents browse the repository to check unchanged files for consistency (e.g., docs, tests, dependencies)
- **Language-agnostic** — Works with any programming language
- **Multi-provider** — Fireworks.ai (default), OpenAI, Anthropic — all first-class options
- **Cost-controlled** — Configurable per-PR budget ($5.00 default), skip on forks by default

**Documentation:**
- `reference.md` — Full specification & implementation plan
- `AGENTS.md` — Project conventions, branching strategy, and development setup
- `reference/` — Research materials for GitHub API, Actions, and architecture

**Quick start:**
1. Copy `.github/workflows/ai-council-review.yml` to your repository
2. Add `FIREWORKS_API_KEY` (or `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) to your repository secrets
3. Optionally add `.ai-council/config.yaml` to customize agents

---

*Status: v1 in development*
