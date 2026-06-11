"""Token budget heuristic for skill bodies."""

from __future__ import annotations

from dataclasses import dataclass

from ai_council_review.skills.models import Skill


@dataclass(frozen=True)
class BudgetCheckResult:
    """Result of a skill budget check."""

    total_tokens: int
    """Sum of estimated tokens across all skills."""

    soft_exceeded: bool
    """True when total_tokens > soft_limit."""

    hard_exceeded: bool
    """True when total_tokens > hard_limit."""

    per_skill: list[tuple[str, int]]
    """(name, estimated_tokens) pairs sorted in descending order of token count."""


def check_skill_budget(
    skills: list[Skill],
    soft_limit: int,
    hard_limit: int,
) -> BudgetCheckResult:
    """Sum estimated_tokens() across *skills* and report against the limits.

    Token counts use the ``len(body) // 4`` heuristic documented in :meth:`Skill.estimated_tokens`.
    """
    per_skill = [(s.name, s.estimated_tokens()) for s in skills]
    per_skill.sort(key=lambda t: t[1], reverse=True)
    total = sum(tokens for _, tokens in per_skill)

    return BudgetCheckResult(
        total_tokens=total,
        soft_exceeded=total > soft_limit,
        hard_exceeded=total > hard_limit,
        per_skill=per_skill,
    )
