# Cost control

How AI Council keeps a per-PR budget: router gating, hard size limits, and a debug mode for auditing spend.

← Back to [README](../README.md)

---

## Budget

The default cost budget is **$5.00 per PR**. This is a soft limit based on estimated token usage:

- The Router runs first on a fast, cheap model to decide which agents are needed.
- Before dispatching agents, the system estimates token usage.
- If the estimate approaches the budget, non-critical agents are skipped or switched to cheaper models.

```yaml
budget_usd: 5.00
```

## Typical costs

| PR size | Agents dispatched | Estimated cost |
|---------|-------------------|----------------|
| Small (1–3 files) | Router + 1–2 specialists + Synthesis | ~$0.50 – $1.50 |
| Medium (5–15 files) | Router + 2–4 specialists + Synthesis | ~$1.50 – $3.50 |
| Large (20–50 files) | Router + up to 4 specialists + Synthesis | ~$3.50 – $5.00 |

The router caps parallel specialists at four on `standard` depth; `review_depth: deep` lifts the cap to let all six run on changes that warrant it. Actual costs vary by provider and model — see [docs/providers.md](providers.md) and [docs/configuration.md](configuration.md).

## Hard limits

Enforce hard PR-size limits to prevent runaway costs. PRs that exceed any limit are skipped:

- `max_files: 50` — skip PRs with more than 50 changed files.
- `max_lines: 2000` — skip PRs with more than 2000 added/deleted lines.
- `max_diff_size: 50000` — skip PRs with a diff larger than 50 KB.

## Timeouts

| Key | Default | Meaning |
|-----|---------|---------|
| `agent_timeout_seconds` | `300` | Per-agent timeout (5 minutes). |
| `total_timeout_seconds` | `600` | Overall workflow timeout (10 minutes). |
| `rate_limit_threshold` | `50` | Enter conservative mode below this GitHub API rate-limit threshold. |

## Debug mode

Enable debug mode to dump the full review state as a workflow artifact. This is useful for troubleshooting why an agent did or did not flag something, or for auditing token usage.

```yaml
debug: true
```

When enabled, the action uploads a JSON artifact containing:

- The full `ReviewState` (PR metadata, agent outputs, synthesis).
- `files_read` — every file each agent browsed.
- `api_calls` — GitHub API call count.
- Estimated token usage per agent.

**Secrets are automatically stripped** from the artifact before upload. Download the artifact from the GitHub Actions run page under **Artifacts**.

---

← Back to [README](../README.md)
