# LLM providers

OpenAI (default), Anthropic, and Fireworks — how to wire each one up, the model aliases, and how to pick models.

← Back to [README](../README.md)

---

Every agent uses LangChain's `BaseChatModel` interface, so switching providers requires no agent-level code changes — only config. You can mix providers per agent. Providers are resolved in `src/ai_council_review/llm/providers/factory.py`.

## Supported providers

| Provider | Default model | Required secret | When to reach for it |
|----------|---------------|-----------------|----------------------|
| **OpenAI** (default) | `gpt-4.1-mini` | `OPENAI_API_KEY` | Default. Strong general reasoning; `gpt-4.1` for specialists, `gpt-4.1-mini` for router/synthesis. |
| **Anthropic** | `claude-3-5-haiku-20241022` | `ANTHROPIC_API_KEY` | Strong reasoning; `claude-sonnet` is a good choice for high-stakes specialists. |
| **Fireworks** | `accounts/fireworks/models/kimi-k2p6` | `FIREWORKS_API_KEY` | Open-weight models at a lower price point. |

Set at least one secret in **Settings › Secrets and variables › Actions**. The default configuration needs only `OPENAI_API_KEY`.

## Selecting a provider and model

In `.ai-council/config.yaml`, set `model` to the provider name and `model_name` to a full model ID or a shorthand alias:

```yaml
agents:
  security:
    model: openai
    model_name: openai/gpt-4.1
```

## Model aliases

Shorthand aliases resolve to full provider model IDs (see `src/ai_council_review/config.py`):

| Alias | Resolves to |
|-------|-------------|
| `openai/gpt-4.1` | `gpt-4.1` |
| `openai/gpt-4.1-mini` | `gpt-4.1-mini` |
| `anthropic/claude-sonnet` | `claude-sonnet-4-20250514` |
| `anthropic/claude-haiku` | `claude-3-5-haiku-20241022` |
| `fireworks/kimi-k2p6` | `accounts/fireworks/routers/kimi-k2p6-turbo` |

## How to pick models

- **Router & Synthesis:** a fast, cheap model is enough — the router only classifies, and synthesis mostly merges. `gpt-4.1-mini` is the default for both.
- **Specialists:** a stronger model pays off, since these do the substantive reasoning. `gpt-4.1` is the default.
- **Cost:** model choice directly drives spend — see [docs/cost-control.md](cost-control.md).

A worked mixed-provider config is in [docs/configuration.md](configuration.md#mixed-provider-example). Adding a brand-new provider is documented in [`AGENTS.md`](../AGENTS.md).

---

← Back to [README](../README.md)
