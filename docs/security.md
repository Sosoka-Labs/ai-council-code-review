# Security

How AI Council handles secrets, fork PRs, and which pull requests it reviews.

← Back to [README](../README.md)

---

## Secrets handling

- API keys are passed via GitHub Secrets and are never logged.
- The [debug artifact](cost-control.md#debug-mode) strips any values that look like secrets before upload.
- The action does not persist code or review data outside the workflow run — AI Council is stateless.

## Fork behavior

By default, AI Council **skips commenting on pull requests from forks** (`comment_on_forks: false`). On fork PRs, `GITHUB_TOKEN` is read-only and cannot post reviews, so the post step exits cleanly rather than erroring.

If you understand the security trade-offs and want to enable fork reviews:

```yaml
comment_on_forks: true
```

> **Do not switch the workflow trigger to `pull_request_target` to work around this.** `pull_request_target` runs with a writable token in the context of the base repository while checking out untrusted fork code — a well-known privilege-escalation vector. AI Council's default `pull_request` trigger with a read-only token on forks is the safe posture. If you must review forks, prefer a manually triggered or label-gated workflow that a maintainer controls, and review the fork's workflow changes first.

## PR filtering

The action automatically skips review for:

- Draft PRs (`skip_drafts: true`).
- PRs carrying a skip label (e.g. `skip-ai-review`, `wip`).
- PRs that exceed the configured size limits (`max_files`, `max_lines`, `max_diff_size`).
- Files matching `skip_patterns` (lockfiles, build output, globs).

See [docs/configuration.md](configuration.md) for the full set of filters and [docs/cost-control.md](cost-control.md) for the size limits.

---

← Back to [README](../README.md)
