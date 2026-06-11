"""In-memory registry of skills discovered on disk."""

from __future__ import annotations

from pathlib import Path

import structlog

from ai_council_review.exceptions import SkillNotFoundError
from ai_council_review.skills.loader import parse_skill_file
from ai_council_review.skills.models import Skill

log = structlog.get_logger(__name__)

_SKILL_FILENAME = "SKILL.md"


class SkillRegistry:
    """In-memory registry of skills discovered from a skills directory."""

    def __init__(self, skills: dict[str, Skill]) -> None:
        """Initialise from a pre-built name → Skill mapping."""
        self._skills = skills

    @classmethod
    def load(cls, skills_dir: Path) -> SkillRegistry:
        """Scan *skills_dir* for ``<name>/SKILL.md`` files and return a registry.

        - If *skills_dir* does not exist, returns an empty registry (no error).
        - Each ``<subdir>/SKILL.md`` is parsed via :func:`parse_skill_file`.
        - Subdirs without ``SKILL.md`` are silently skipped.
        - Hidden subdirs (names starting with ``'.'``) are silently skipped.
        - Failures in any individual ``SKILL.md`` propagate as :exc:`SkillLoadError`.
        """
        if not skills_dir.exists():
            log.debug("skills_dir does not exist, returning empty registry", path=str(skills_dir))
            return cls({})

        skills: dict[str, Skill] = {}

        for subdir in sorted(skills_dir.iterdir()):
            if not subdir.is_dir():
                continue
            if subdir.name.startswith("."):
                continue

            skill_file = subdir / _SKILL_FILENAME
            if not skill_file.exists():
                log.debug("subdir has no SKILL.md, skipping", path=str(subdir))
                continue

            skill = parse_skill_file(skill_file)
            skills[skill.name] = skill
            log.debug("loaded skill", name=skill.name, path=str(skill_file))

        log.info("skill registry loaded", count=len(skills), names=list(skills.keys()))
        return cls(skills)

    def get(self, name: str) -> Skill:
        """Return the named skill, or raise :exc:`SkillNotFoundError`."""
        try:
            return self._skills[name]
        except KeyError as exc:
            raise SkillNotFoundError(
                f"Skill {name!r} not found in registry. Available skills: {self.names()}"
            ) from exc

    def get_many(self, names: list[str]) -> list[Skill]:
        """Return skills for each name in *names*, preserving order.

        Raises :exc:`SkillNotFoundError` on the first name not in the registry.
        """
        return [self.get(n) for n in names]

    def names(self) -> list[str]:
        """Return all skill names, sorted alphabetically."""
        return sorted(self._skills.keys())

    def all(self) -> list[Skill]:
        """Return all skills, sorted by name."""
        return [self._skills[n] for n in self.names()]

    def __contains__(self, name: object) -> bool:
        """Return True if a skill with *name* is in the registry."""
        return name in self._skills

    def __len__(self) -> int:
        """Return the number of skills in the registry."""
        return len(self._skills)
