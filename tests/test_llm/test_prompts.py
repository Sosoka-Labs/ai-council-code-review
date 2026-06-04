"""Tests for ai_council_review.llm.prompts."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from ai_council_review.llm.prompts import load_prompt


class TestLoadPrompt:
    """Tests for load_prompt."""

    def test_load_prompt_returns_chat_template(self) -> None:
        """Test that load_prompt returns a ChatPromptTemplate."""
        result = load_prompt("generalist")
        assert isinstance(result, ChatPromptTemplate)

    def test_load_prompt_not_found(self) -> None:
        """Test that an unknown prompt name raises KeyError."""
        try:
            load_prompt("nonexistent")
            raise AssertionError("Expected KeyError")
        except KeyError as e:
            assert "nonexistent" in str(e)

    def test_load_prompt_format_messages(self) -> None:
        """Test that loaded template can be formatted into messages."""
        template = load_prompt("generalist")
        messages = template.format_messages(
            repo="test/repo",
            pr_number=42,
            pr_title="Test PR",
            changed_files="- src/main.py",
            diff="@@ -1,1 +1,1 @@",
            agent_scratchpad=[],
        )
        assert len(messages) == 2
        assert messages[0].type == "system"
        assert "senior software engineer" in messages[0].content
        assert messages[1].type == "human"
        assert "test/repo" in messages[1].content
        assert "42" in messages[1].content

    def test_all_prompts_registered(self) -> None:
        """Test that all expected prompt names are registered."""
        names = ["router", "quality", "security", "generalist", "synthesis", "architecture"]
        for name in names:
            template = load_prompt(name)
            assert isinstance(template, ChatPromptTemplate)
