# Skills — binding domain knowledge to agents

How to teach a specialist your project's conventions and known pitfalls with versioned markdown files.

← Back to [README](../README.md)

---

Skills are markdown files that inject project-specific knowledge into a specialist agent's system prompt. They let teams encode conventions, known pitfalls, or domain rules that the generic agents would otherwise have no visibility into. Skills travel with the reviewed repository, are versioned in git, and can be PR-reviewed like any other config.

## File layout

Place skill files under `.ai-council/skills/<name>/SKILL.md`:

```
.ai-council/
└── skills/
    └── oauth-pitfalls/
        └── SKILL.md         # required: YAML frontmatter + markdown body
```

Minimal `SKILL.md`:

```markdown
---
name: oauth-pitfalls
description: Use when reviewing OAuth 2.0 flows, token handling, or PKCE implementations.
---
# OAuth Pitfalls

...review guidance here...
```

## Frontmatter fields

| Field | Required | Notes |
|-------|----------|-------|
| `name` | Yes | Lowercase and hyphens only; must match the parent directory name. |
| `description` | Yes | 1024 chars max; the Router reads descriptions to route more accurately. |
| Any other fields | No | Preserved as-is; ignored by AI Council in Phase 1. |

## Binding to agents

Skills are bound explicitly per agent in `.ai-council/config.yaml`. Three patterns are supported:

```yaml
# Pattern 1 — explicit per-agent list (recommended)
agents:
  security:
    skills: [oauth-pitfalls]

# Pattern 2 — star sentinel: give this agent every discovered skill
agents:
  architecture:
    skills: "*"

# Pattern 3 — top-level default applied to every agent that doesn't set its own
default_agent_skills: [domain-glossary]
# Set skills: [] on a specific agent to opt it out of the default.
```

Resolution order per agent: explicit `skills:` on the agent → `default_agent_skills` → none.

Listing a skill name that does not exist on disk is a hard error at config load time. The `"*"` sentinel always resolves at runtime and is never a load-time error.

## What each role receives

- **Specialist agents** (security, quality, architecture, performance, documentation, devops) — full skill bodies appended to the system prompt.
- **Router** — a descriptions-only catalog (name + description for each skill), so it can route more accurately when domain skills are present. No bodies.
- **Synthesis** — no skills in Phase 1.

## Bundled skills

The repository ships four demo skills under [`.ai-council/skills/`](../.ai-council/skills/), each wired to a matching agent in the [example config](../examples/.ai-council/config.yaml):

| Skill | Bound to | Encodes |
|-------|----------|---------|
| `oauth-pitfalls` | security | OAuth 2.0 / JWT / PKCE review guidance |
| `n-plus-one` | performance | N+1 query and ORM access-pattern detection |
| `docstring-style` | documentation | Google-style docstring conventions |
| `github-actions-hardening` | devops | GitHub Actions security and correctness |

Copy any of these into your own repo as a starting point, or drop in a new `SKILL.md` and bind it the same way.

## Token budgets

The sum of skill bodies for each agent is checked before the run:

- **Soft limit** (default 8 000 tokens): warning logged, run continues.
- **Hard limit** (default 16 000 tokens): `ConfigError` raised, run aborts with a list of offending skill sizes.

Both limits are configurable:

```yaml
skills_token_budget_soft: 8000
skills_token_budget_hard: 16000
```

The budget uses a `len / 4` character approximation — exact per-model tokenization is deferred to a later phase.

## Future phases

Progressive disclosure (on-demand body loading via a `load_skill` tool) and skill scripts (a `scripts/` subdirectory) are tracked for Phase 2 and Phase 3 respectively.

---

← Back to [README](../README.md)
