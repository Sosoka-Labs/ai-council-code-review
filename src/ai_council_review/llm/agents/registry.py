"""Agent registry — single source of truth for specialist agent definitions.

Adding a new specialist agent requires only appending one ``AgentSpec`` to
``SPECIALIST_AGENTS``. The graph, router prompt, synthesis prompt, and valid-agent
filter all derive from this tuple at import time.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSpec:
    """Declarative specification for a specialist agent.

    Attributes:
        name: Agent identifier used as the graph node name and skill key
            (e.g. ``"security"``).
        prompt_key: Key into the prompt loader registry (usually == ``name``).
        category: Finding category label emitted by this agent
            (used in synthesis grouping).
        default_temperature: LLM temperature fallback when not set in config.
        default_max_tokens: Max output tokens fallback when not set in config.
        router_hint: One-line description of when the router should select
            this agent.  Injected into the router prompt's ``{{ agent_catalog }}``
            slot so adding an agent auto-teaches routing.
        enabled_by_default: When ``True`` the agent appears in the state
            default ``agents_needed`` list and the router fallback.
    """

    name: str
    prompt_key: str
    category: str
    default_temperature: float
    default_max_tokens: int
    router_hint: str
    enabled_by_default: bool = True


#: Ordered tuple of all specialist agents.  Order determines graph node
#: insertion order (cosmetic only — LangGraph executes them in parallel).
SPECIALIST_AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec(
        name="security",
        prompt_key="security",
        category="security",
        default_temperature=0.2,
        default_max_tokens=16000,
        router_hint=(
            "auth, crypto, user input, injection, secrets, deps, API endpoints, data persistence"
        ),
        enabled_by_default=True,
    ),
    AgentSpec(
        name="quality",
        prompt_key="quality",
        category="quality",
        default_temperature=0.3,
        default_max_tokens=16000,
        router_hint=(
            "logic bugs, error handling, tests, type safety, complexity, "
            "code smells, significant code changes"
        ),
        enabled_by_default=True,
    ),
    AgentSpec(
        name="architecture",
        prompt_key="architecture",
        category="architecture",
        default_temperature=0.3,
        default_max_tokens=16000,
        router_hint=(
            "cross-file impact, public API, docs/migration drift, "
            "multiple files/modules, data models, configuration"
        ),
        enabled_by_default=True,
    ),
    AgentSpec(
        name="performance",
        prompt_key="performance",
        category="performance",
        default_temperature=0.3,
        default_max_tokens=16000,
        router_hint=(
            "DB queries/ORM, loops over collections, request handlers, "
            "data-pipeline/batch code, N+1 patterns, sync I/O on hot paths, "
            "*/repositories/*, */dao/*, */queries/*"
        ),
        enabled_by_default=True,
    ),
    AgentSpec(
        name="documentation",
        prompt_key="documentation",
        category="documentation",
        default_temperature=0.3,
        default_max_tokens=16000,
        router_hint=(
            "README/docs/*.md changes, public function/class signature changes, "
            "new CLI flags/env vars, new exported symbols, docs-only PRs"
        ),
        enabled_by_default=True,
    ),
    AgentSpec(
        name="devops",
        prompt_key="devops",
        category="devops",
        default_temperature=0.3,
        default_max_tokens=16000,
        router_hint=(
            ".github/workflows/*, Dockerfile, *.tf, *.sh, *.yml/*.yaml CI configs, "
            "infrastructure-as-code, shell scripts, pipeline configuration"
        ),
        enabled_by_default=True,
    ),
)

#: Name-keyed lookup for O(1) spec access.
SPECIALIST_BY_NAME: dict[str, AgentSpec] = {a.name: a for a in SPECIALIST_AGENTS}
