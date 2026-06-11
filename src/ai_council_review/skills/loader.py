"""SKILL.md frontmatter parser and single-file loader."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ai_council_review.exceptions import SkillLoadError
from ai_council_review.skills.models import Skill

_FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
_VALID_NAME = re.compile(r"^[a-z0-9-]+$")


def parse_skill_file(path: Path) -> Skill:
    """Parse a single SKILL.md file and return a validated Skill.

    Raises SkillLoadError on any validation failure.
    """
    raw = path.read_text(encoding="utf-8")

    match = _FRONTMATTER_PATTERN.match(raw)
    if not match:
        raise SkillLoadError(f"{path}: SKILL.md must begin with a '---' frontmatter block")

    frontmatter_text = match.group(1)
    body = raw[match.end() :]

    try:
        frontmatter: Any = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as exc:
        raise SkillLoadError(f"{path}: frontmatter is not valid YAML: {exc}") from exc

    if not isinstance(frontmatter, dict):
        raise SkillLoadError(
            f"{path}: frontmatter must be a YAML mapping, got {type(frontmatter).__name__}"
        )

    if "name" not in frontmatter:
        raise SkillLoadError(f"{path}: frontmatter is missing required field 'name'")

    if "description" not in frontmatter:
        raise SkillLoadError(f"{path}: frontmatter is missing required field 'description'")

    name: str = str(frontmatter["name"])
    description: str = str(frontmatter["description"])

    if not _VALID_NAME.match(name):
        raise SkillLoadError(
            f"{path}: 'name' must contain only lowercase letters, digits, and hyphens"
            f" — got {name!r}"
        )

    expected_dir = path.parent.name
    if name != expected_dir:
        raise SkillLoadError(
            f"{path}: 'name' field ({name!r}) must match the parent directory name"
            f" ({expected_dir!r})"
        )

    if len(description) > 1024:
        raise SkillLoadError(
            f"{path}: 'description' exceeds 1024 characters (got {len(description)})"
        )

    raw_frontmatter: dict[str, Any] = dict(frontmatter)

    return Skill(
        name=name,
        description=description,
        body=body,
        path=path.resolve(),
        raw_frontmatter=raw_frontmatter,
    )
