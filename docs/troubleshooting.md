# Troubleshooting

Common errors and how to fix them.

← Back to [README](../README.md)

---

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `Configuration error: No LLM API key found` | Missing or misnamed secret | Add `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`, `FIREWORKS_API_KEY`) under **Settings › Secrets and variables › Actions**. See [README › Quick Start](../README.md#quick-start). |
| `LLM provider error: Unsupported provider: xyz` | Typo in the `model` field | Use one of: `openai`, `anthropic`, `fireworks`. Check `.ai-council/config.yaml`. |
| `LLM provider error: Failed to initialize...` | Invalid API key or model name | Verify the secret value and the `model_name` in config. Try an alias from the [model aliases table](configuration.md#providers-and-model-aliases). |
| `Review failed with timeout` | PR too large or model too slow | Reduce `max_files` / `max_lines`, or raise `agent_timeout_seconds` / `total_timeout_seconds`. See [docs/cost-control.md](cost-control.md). |
| `No review posted on fork PR` | Expected default behavior | Fork PRs are skipped by default (`comment_on_forks: false`). See [docs/security.md](security.md#fork-behavior). |
| `Agent output is empty or garbled` | Model context too short for the JSON response | Increase `max_tokens` for the affected agent (e.g. `16000`). |
| A finding is missing from inline comments | The finding targets unchanged code | GitHub drops comments outside changed hunks; such findings appear in the summary instead. See [docs/architecture.md](architecture.md#inline-comment-positioning). |

For deeper debugging, enable [debug mode](cost-control.md#debug-mode) to dump the full review state as a workflow artifact.

---

← Back to [README](../README.md)
