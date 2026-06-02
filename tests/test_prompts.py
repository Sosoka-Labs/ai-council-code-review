"""Tests for ai_council_review.prompts."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_council_review import prompts as prompts_module
from ai_council_review.prompts import load_prompt


class TestLoadPrompt:
    """Tests for load_prompt."""

    def test_load_prompt(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading a simple prompt."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        prompt_file = prompts_dir / "test.txt"
        prompt_file.write_text("Hello, {{ user }}!", encoding="utf-8")

        fake_module = tmp_path / "fake_module.py"
        fake_module.write_text("")
        monkeypatch.setattr(prompts_module, "__file__", str(fake_module))

        result = load_prompt("test", user="World")
        assert result == "Hello, World!"

    def test_load_prompt_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that missing prompt raises FileNotFoundError."""
        fake_module = tmp_path / "fake_module.py"
        fake_module.write_text("")
        monkeypatch.setattr(prompts_module, "__file__", str(fake_module))

        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent")

    def test_load_prompt_with_variables(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test Jinja2 variable substitution."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        prompt_file = prompts_dir / "vars.txt"
        prompt_file.write_text("Repo: {{ repo }}\nPR: {{ pr_number }}", encoding="utf-8")

        fake_module = tmp_path / "fake_module.py"
        fake_module.write_text("")
        monkeypatch.setattr(prompts_module, "__file__", str(fake_module))

        result = load_prompt("vars", repo="test/repo", pr_number=42)
        assert result == "Repo: test/repo\nPR: 42"
