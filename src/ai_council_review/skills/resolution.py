"""Skill resolution — maps agent names to their effective Skill list.

This module is the single place that applies the config precedence rules
(agent.skills → default_agent_skills → []) and enforces token budgets.
"""

from __future__ import annotations

import structlog

from ai_council_review.exceptions import ConfigError
from ai_council_review.skills.budget import check_skill_budget
from ai_council_review.skills.models import Skill
from ai_council_review.skills.registry import SkillRegistry

log = structlog.get_logger(__name__)

# Synthesis never receives skill bodies in Phase 1.
_SYNTHESIS_AGENT = "synthesis"


def resolve_skills_for_agent(
    agent_name: str,
    config: object,  # CouncilConfig — typed as object to avoid circular import
    registry: SkillRegistry,
) -> list[Skill]:
    """Resolve and return the Skill objects for one agent.

    Precedence:
      1. ``config.agents[agent_name].skills`` if not None (including []).
      2. ``config.default_agent_skills`` if not None.
      3. [] (no skills — current behaviour, fully backwards-compatible).

    The ``"*"`` sentinel resolves to ``registry.all()``.
    Returns [] if the registry is empty.
    Enforces token budget limits:
      - Over ``skills_token_budget_soft`` → warning log, run continues.
      - Over ``skills_token_budget_hard`` → raises ``ConfigError``.

    Special case: the ``synthesis`` agent always returns [] in Phase 1.

    Args:
        agent_name: The canonical agent name (e.g. "security", "router").
        config: A ``CouncilConfig`` instance.
        registry: The loaded ``SkillRegistry``.

    Returns:
        Ordered list of ``Skill`` objects for this agent.

    Raises:
        ConfigError: When the resolved skills exceed the hard token budget.
    """
    # Synthesis never gets skills.
    if agent_name == _SYNTHESIS_AGENT:
        return []

    # Empty registry → nothing to inject.
    if len(registry) == 0:
        return []

    # Resolve the effective selector using the precedence rules.
    from ai_council_review.config import ALL_SKILLS

    agent_cfg = getattr(config, "agents", {}).get(agent_name)
    agent_selector = getattr(agent_cfg, "skills", None) if agent_cfg is not None else None
    default_selector = getattr(config, "default_agent_skills", None)

    # None (unset) falls through; explicit [] is an opt-out.
    if agent_selector is not None:
        selector = agent_selector
    elif default_selector is not None:
        selector = default_selector
    else:
        return []

    # Resolve the sentinel or explicit list.
    if selector == ALL_SKILLS:
        skills = registry.all()
    elif isinstance(selector, list):
        if not selector:
            # Explicit opt-out via empty list.
            return []
        skills = registry.get_many(selector)
    else:
        # Should not happen after config validation, but be defensive.
        return []

    if not skills:
        return []

    # Budget check.
    soft_limit: int = getattr(config, "skills_token_budget_soft", 8000)
    hard_limit: int = getattr(config, "skills_token_budget_hard", 16000)
    result = check_skill_budget(skills, soft_limit, hard_limit)

    if result.hard_exceeded:
        detail = ", ".join(f"{n}={t}" for n, t in result.per_skill)
        raise ConfigError(
            f"Skills for agent '{agent_name}' exceed the hard token budget "
            f"({result.total_tokens} estimated tokens > {hard_limit} limit). "
            f"Per-skill estimates (name=tokens): {detail}. "
            "Reduce the number of skills bound to this agent, or raise "
            "skills_token_budget_hard in your config."
        )

    if result.soft_exceeded:
        log.warning(
            "Skills for agent exceed soft token budget (len/4 heuristic); "
            "review may be slower or more expensive",
            agent=agent_name,
            total_tokens=result.total_tokens,
            soft_limit=soft_limit,
        )

    return skills
