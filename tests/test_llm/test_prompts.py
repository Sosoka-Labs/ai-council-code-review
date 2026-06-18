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


class TestSynthesisPromptInjectionHardening:
    """H-1: Verify the synthesis prompt wraps findings_json in untrusted delimiters.

    A PR author who controls specialist finding bodies could otherwise inject
    text like 'IGNORE PREVIOUS INSTRUCTIONS' into the synthesis LLM.  The
    <untrusted_agent_output> wrapper and the IMPORTANT system guard address this.
    """

    def _render_synthesis(self) -> tuple[str, str]:
        """Render the synthesis prompt with a representative findings payload."""
        from ai_council_review.llm.prompts.templates import SYNTHESIS

        system_msg, human_msg = SYNTHESIS.format_messages(
            repo="owner/repo",
            pr_number=1,
            pr_title="Add login feature",
            findings_json='[{"path": "src/auth.py", "body": "Potential SQL injection"}]',
            categories="security, quality",
        )
        return system_msg.content, human_msg.content

    def test_system_message_contains_important_guard(self) -> None:
        """IMPORTANT guard is present in the synthesis system message."""
        system_content, _ = self._render_synthesis()
        assert "IMPORTANT" in system_content
        assert "untrusted" in system_content.lower()

    def test_human_message_wraps_findings_in_untrusted_delimiters(self) -> None:
        """findings_json is wrapped in <untrusted_agent_output> delimiters."""
        _, human_content = self._render_synthesis()
        assert "<untrusted_agent_output>" in human_content
        assert "</untrusted_agent_output>" in human_content

    def test_findings_json_appears_inside_delimiters(self) -> None:
        """The actual findings payload sits between the delimiter tags."""
        _, human_content = self._render_synthesis()
        start = human_content.index("<untrusted_agent_output>")
        end = human_content.index("</untrusted_agent_output>")
        inside = human_content[start:end]
        assert "SQL injection" in inside


class TestRouterPromptDepthVocabulary:
    """H-3/depth-vocab: Verify the router prompt uses the canonical standard|deep vocabulary."""

    def test_router_prompt_mentions_standard_and_deep(self) -> None:
        """Router prompt must use 'standard' and 'deep', not 'quick' or 'exhaustive'."""
        from ai_council_review.llm.prompts.templates import ROUTER

        # Collect all text from the system message.
        # The template uses jinja2 so we render with a dummy catalog.
        messages = ROUTER.format_messages(
            repo="owner/repo",
            pr_number=1,
            pr_title="Test",
            pr_body="",
            changed_files="- src/main.py",
            diff="@@ -1 +1 @@",
            agent_catalog="- **security** — auth changes",
        )
        system_text = messages[0].content

        assert '"standard"' in system_text
        assert '"deep"' in system_text
        # Old vocabulary must not appear in the output format spec.
        assert '"quick"' not in system_text
        assert '"exhaustive"' not in system_text
