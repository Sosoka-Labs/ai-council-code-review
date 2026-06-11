"""Tests for ai_council_review.skills.budget."""

from __future__ import annotations

from pathlib import Path

from ai_council_review.skills.budget import BudgetCheckResult, check_skill_budget
from ai_council_review.skills.models import Skill


def _make_skill(name: str, body: str) -> Skill:
    """Return a Skill with a specific body length for budget testing."""
    return Skill(
        name=name,
        description="A skill.",
        body=body,
        path=Path(f"/fake/{name}/SKILL.md"),
        raw_frontmatter={"name": name, "description": "A skill."},
    )


class TestCheckSkillBudget:
    """check_skill_budget() correctly tallies tokens and sets flags."""

    def test_empty_list_returns_zero_tokens_no_flags(self) -> None:
        """An empty skill list produces 0 tokens with neither flag set."""
        result = check_skill_budget([], soft_limit=100, hard_limit=200)

        assert isinstance(result, BudgetCheckResult)
        assert result.total_tokens == 0
        assert result.soft_exceeded is False
        assert result.hard_exceeded is False
        assert result.per_skill == []

    def test_under_soft_limit_both_flags_false(self) -> None:
        """When total tokens < soft_limit, both flags are False."""
        # body of 40 chars → 10 tokens
        skill = _make_skill("small-skill", "x" * 40)
        result = check_skill_budget([skill], soft_limit=100, hard_limit=200)

        assert result.total_tokens == 10
        assert result.soft_exceeded is False
        assert result.hard_exceeded is False

    def test_between_soft_and_hard_only_soft_exceeded(self) -> None:
        """When soft_limit < total <= hard_limit, only soft_exceeded is True."""
        # body of 400 chars → 100 tokens; soft=50, hard=200
        skill = _make_skill("medium-skill", "y" * 400)
        result = check_skill_budget([skill], soft_limit=50, hard_limit=200)

        assert result.total_tokens == 100
        assert result.soft_exceeded is True
        assert result.hard_exceeded is False

    def test_over_hard_limit_both_flags_true(self) -> None:
        """When total > hard_limit, both soft_exceeded and hard_exceeded are True."""
        # body of 4000 chars → 1000 tokens; soft=500, hard=800
        skill = _make_skill("large-skill", "z" * 4000)
        result = check_skill_budget([skill], soft_limit=500, hard_limit=800)

        assert result.total_tokens == 1000
        assert result.soft_exceeded is True
        assert result.hard_exceeded is True

    def test_per_skill_sorted_descending(self) -> None:
        """per_skill is sorted by token count from highest to lowest."""
        small = _make_skill("small", "a" * 40)  # 10 tokens
        large = _make_skill("large", "b" * 400)  # 100 tokens
        medium = _make_skill("medium", "c" * 200)  # 50 tokens

        result = check_skill_budget([small, large, medium], soft_limit=500, hard_limit=1000)

        names = [name for name, _ in result.per_skill]
        assert names == ["large", "medium", "small"]

    def test_total_tokens_sums_all_skills(self) -> None:
        """total_tokens is the sum of individual skill estimates."""
        s1 = _make_skill("a", "x" * 100)  # 25 tokens
        s2 = _make_skill("b", "y" * 200)  # 50 tokens
        s3 = _make_skill("c", "z" * 300)  # 75 tokens

        result = check_skill_budget([s1, s2, s3], soft_limit=9999, hard_limit=9999)

        assert result.total_tokens == 150
