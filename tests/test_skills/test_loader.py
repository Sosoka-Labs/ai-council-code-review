"""Tests for ai_council_review.skills.loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_council_review.exceptions import SkillLoadError
from ai_council_review.skills.loader import parse_skill_file
from ai_council_review.skills.models import Skill

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "skills"


class TestParseSkillFileHappyPath:
    """Valid SKILL.md files are parsed into Skill objects."""

    def test_returns_skill_with_expected_fields(self) -> None:
        """A well-formed SKILL.md produces a Skill with all fields populated."""
        skill = parse_skill_file(FIXTURE_DIR / "example-skill" / "SKILL.md")

        assert isinstance(skill, Skill)
        assert skill.name == "example-skill"
        assert "Demonstrates correct" in skill.description
        assert "# Example Skill" in skill.body
        assert skill.path == (FIXTURE_DIR / "example-skill" / "SKILL.md").resolve()

    def test_body_strips_frontmatter(self, tmp_path: Path) -> None:
        """The body must not contain the frontmatter block."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: A skill.\n---\n# Body content\n"
        )

        skill = parse_skill_file(skill_dir / "SKILL.md")

        assert "---" not in skill.body.split("\n")[0]
        assert "# Body content" in skill.body

    def test_body_preserves_content_verbatim(self, tmp_path: Path) -> None:
        """Everything after the closing frontmatter delimiter is preserved."""
        body_text = "# Title\n\nSome **markdown**.\n\n    code block\n"
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: my-skill\ndescription: A skill.\n---\n{body_text}"
        )

        skill = parse_skill_file(skill_dir / "SKILL.md")

        assert skill.body == body_text

    def test_unknown_frontmatter_keys_preserved(self) -> None:
        """Extra frontmatter keys appear in raw_frontmatter."""
        skill = parse_skill_file(FIXTURE_DIR / "example-skill" / "SKILL.md")

        assert "metadata" in skill.raw_frontmatter
        assert skill.raw_frontmatter["metadata"]["author"] == "ai-council"

    def test_known_keys_also_in_raw_frontmatter(self, tmp_path: Path) -> None:
        """name and description are also present in raw_frontmatter."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: A skill.\n---\n# Body\n"
        )

        skill = parse_skill_file(skill_dir / "SKILL.md")

        assert skill.raw_frontmatter["name"] == "my-skill"
        assert skill.raw_frontmatter["description"] == "A skill."


class TestParseSkillFileValidation:
    """Invalid SKILL.md files raise SkillLoadError."""

    def test_missing_frontmatter_delimiter(self, tmp_path: Path) -> None:
        """Files without a leading '---' raise SkillLoadError."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("name: my-skill\ndescription: A skill.\n")

        with pytest.raises(SkillLoadError):
            parse_skill_file(skill_dir / "SKILL.md")

    def test_invalid_yaml_in_frontmatter(self, tmp_path: Path) -> None:
        """Non-YAML frontmatter raises SkillLoadError."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\n: bad: yaml: [\n---\n# Body\n")

        with pytest.raises(SkillLoadError):
            parse_skill_file(skill_dir / "SKILL.md")

    def test_missing_name_key(self, tmp_path: Path) -> None:
        """Frontmatter without 'name' raises SkillLoadError mentioning 'name'."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: A skill.\n---\n# Body\n")

        with pytest.raises(SkillLoadError, match="name"):
            parse_skill_file(skill_dir / "SKILL.md")

    def test_missing_description_key(self, tmp_path: Path) -> None:
        """Frontmatter without 'description' raises SkillLoadError mentioning 'description'."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n# Body\n")

        with pytest.raises(SkillLoadError, match="description"):
            parse_skill_file(skill_dir / "SKILL.md")

    def test_description_exceeds_1024_chars(self, tmp_path: Path) -> None:
        """A description over 1024 characters raises SkillLoadError."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        long_desc = "x" * 1025
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: my-skill\ndescription: {long_desc}\n---\n# Body\n"
        )

        with pytest.raises(SkillLoadError):
            parse_skill_file(skill_dir / "SKILL.md")

    def test_name_with_bad_characters(self, tmp_path: Path) -> None:
        """A name containing uppercase or special characters raises SkillLoadError."""
        skill_dir = tmp_path / "My_Skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: My_Skill\ndescription: A skill.\n---\n# Body\n"
        )

        with pytest.raises(SkillLoadError):
            parse_skill_file(skill_dir / "SKILL.md")

    def test_name_mismatch_with_parent_directory(self, tmp_path: Path) -> None:
        """A 'name' that doesn't match its parent directory raises SkillLoadError."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: other-skill\ndescription: A skill.\n---\n# Body\n"
        )

        with pytest.raises(SkillLoadError):
            parse_skill_file(skill_dir / "SKILL.md")
