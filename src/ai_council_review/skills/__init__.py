"""Skills package — domain-knowledge files bound to specialist agents."""

from ai_council_review.skills.budget import BudgetCheckResult, check_skill_budget
from ai_council_review.skills.injection import apply_skill_catalog, apply_skills
from ai_council_review.skills.loader import parse_skill_file
from ai_council_review.skills.models import Skill
from ai_council_review.skills.registry import SkillRegistry
from ai_council_review.skills.resolution import resolve_skills_for_agent

__all__ = [
    "BudgetCheckResult",
    "Skill",
    "SkillRegistry",
    "apply_skill_catalog",
    "apply_skills",
    "check_skill_budget",
    "parse_skill_file",
    "resolve_skills_for_agent",
]
