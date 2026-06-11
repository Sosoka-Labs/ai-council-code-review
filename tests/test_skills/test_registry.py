"""Tests for ai_council_review.skills.registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_council_review.exceptions import SkillLoadError, SkillNotFoundError
from ai_council_review.skills.registry import SkillRegistry

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "skills"


def _write_skill(skills_dir: Path, name: str, description: str = "A test skill.") -> None:
    """Write a minimal valid SKILL.md into skills_dir/<name>/."""
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n# {name}\n"
    )


class TestRegistryLoad:
    """SkillRegistry.load() discovers and parses SKILL.md files."""

    def test_loads_fixture_skill(self) -> None:
        """The fixture directory loads the example-skill without error."""
        registry = SkillRegistry.load(FIXTURE_DIR)

        assert "example-skill" in registry
        assert len(registry) == 1

    def test_loads_multiple_skills(self, tmp_path: Path) -> None:
        """Multiple skill subdirectories each produce a Skill in the registry."""
        _write_skill(tmp_path, "skill-alpha")
        _write_skill(tmp_path, "skill-beta")

        registry = SkillRegistry.load(tmp_path)

        assert len(registry) == 2
        assert "skill-alpha" in registry
        assert "skill-beta" in registry

    def test_empty_directory_returns_empty_registry(self, tmp_path: Path) -> None:
        """An existing but empty directory produces an empty registry with no error."""
        registry = SkillRegistry.load(tmp_path)

        assert len(registry) == 0

    def test_missing_directory_returns_empty_registry(self, tmp_path: Path) -> None:
        """A non-existent directory produces an empty registry with no error."""
        registry = SkillRegistry.load(tmp_path / "nonexistent")

        assert len(registry) == 0

    def test_subdir_without_skill_md_is_skipped(self, tmp_path: Path) -> None:
        """A subdirectory without SKILL.md is silently ignored."""
        (tmp_path / "not-a-skill").mkdir()
        _write_skill(tmp_path, "real-skill")

        registry = SkillRegistry.load(tmp_path)

        assert len(registry) == 1
        assert "real-skill" in registry

    def test_hidden_subdir_is_skipped(self, tmp_path: Path) -> None:
        """Subdirectories starting with '.' are silently ignored."""
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "SKILL.md").write_text("---\nname: hidden\ndescription: Hidden.\n---\n# Hidden\n")
        _write_skill(tmp_path, "visible-skill")

        registry = SkillRegistry.load(tmp_path)

        assert "hidden" not in registry
        assert "visible-skill" in registry

    def test_malformed_skill_md_raises_with_path(self, tmp_path: Path) -> None:
        """A malformed SKILL.md propagates SkillLoadError with the path in the message."""
        bad_dir = tmp_path / "bad-skill"
        bad_dir.mkdir()
        (bad_dir / "SKILL.md").write_text("no frontmatter here\n")

        with pytest.raises(SkillLoadError, match="bad-skill"):
            SkillRegistry.load(tmp_path)


class TestRegistryAccess:
    """get(), get_many(), names(), all(), __contains__, __len__."""

    def test_get_returns_skill(self) -> None:
        """get() returns the Skill for a known name."""
        registry = SkillRegistry.load(FIXTURE_DIR)
        skill = registry.get("example-skill")

        assert skill.name == "example-skill"

    def test_get_raises_skill_not_found(self) -> None:
        """get() raises SkillNotFoundError for an unknown name."""
        registry = SkillRegistry.load(FIXTURE_DIR)

        with pytest.raises(SkillNotFoundError):
            registry.get("no-such-skill")

    def test_get_many_empty_list_returns_empty(self) -> None:
        """get_many([]) returns an empty list without error."""
        registry = SkillRegistry.load(FIXTURE_DIR)

        assert registry.get_many([]) == []

    def test_get_many_raises_on_unknown_name(self) -> None:
        """get_many() raises SkillNotFoundError on the first missing name."""
        registry = SkillRegistry.load(FIXTURE_DIR)

        with pytest.raises(SkillNotFoundError):
            registry.get_many(["example-skill", "missing"])

    def test_names_returns_sorted(self, tmp_path: Path) -> None:
        """names() returns skill names in sorted order."""
        _write_skill(tmp_path, "zebra-skill")
        _write_skill(tmp_path, "alpha-skill")

        registry = SkillRegistry.load(tmp_path)

        assert registry.names() == ["alpha-skill", "zebra-skill"]

    def test_contains_known_name(self) -> None:
        """__contains__ returns True for a skill that exists."""
        registry = SkillRegistry.load(FIXTURE_DIR)

        assert "example-skill" in registry

    def test_contains_unknown_name(self) -> None:
        """__contains__ returns False for a skill that does not exist."""
        registry = SkillRegistry.load(FIXTURE_DIR)

        assert "ghost-skill" not in registry

    def test_len_matches_skill_count(self, tmp_path: Path) -> None:
        """__len__ equals the number of skills discovered."""
        _write_skill(tmp_path, "a-skill")
        _write_skill(tmp_path, "b-skill")
        _write_skill(tmp_path, "c-skill")

        registry = SkillRegistry.load(tmp_path)

        assert len(registry) == 3
