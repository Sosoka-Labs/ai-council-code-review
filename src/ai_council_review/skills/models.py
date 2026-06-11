"""Skill dataclass for AI Council domain-knowledge files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Skill:
    """A parsed SKILL.md file binding domain knowledge to an agent."""

    name: str
    """Skill identifier — lowercase letters, digits, and hyphens only."""

    description: str
    """Short description used in router catalog; max 1024 characters."""

    body: str
    """Full markdown body from the SKILL.md file (frontmatter stripped)."""

    path: Path
    """Absolute path to the SKILL.md file that was parsed."""

    raw_frontmatter: dict[str, Any]
    """All frontmatter keys, including any unknown ones not used by this tool."""

    def estimated_tokens(self) -> int:
        """Return a rough token estimate using the len(body) // 4 heuristic.

        This is an approximation; exact counts vary by model and tokenizer.
        """
        return len(self.body) // 4
