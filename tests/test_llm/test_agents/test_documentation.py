"""Tests for the documentation specialist agent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ai_council_review.config import CouncilConfig
from ai_council_review.llm.agents.output_models import FindingList
from ai_council_review.llm.agents.registry import SPECIALIST_BY_NAME
from ai_council_review.llm.agents.specialist import build_specialist_chain, run_specialist_agent
from ai_council_review.models import FileInfo, Finding, PRMetadata, ReviewState

_SPEC = SPECIALIST_BY_NAME["documentation"]


def _make_state() -> ReviewState:
    pr = PRMetadata(
        number=21,
        title="Update client timeout default",
        state="open",
        author="bob",
        author_association="MEMBER",
        base_ref="main",
        base_sha="ccc",
        head_ref="feat/timeout",
        head_sha="ddd",
        html_url="https://github.com/owner/repo/pull/21",
    )
    files = [
        FileInfo(
            filename="src/api/client.py",
            status="modified",
            additions=3,
            deletions=1,
            patch=(
                "@@ -30,7 +30,9 @@\n"
                "-def connect(timeout=30):\n"
                "+def connect(timeout=60):\n"
                '+    """Connect to service.\n'
                "+    Args: timeout: seconds (default was 30, now 60)\n"
                '+    """\n'
            ),
        )
    ]
    return ReviewState(pr_metadata=pr, changed_files=files)


def _valid_finding_list() -> FindingList:
    return FindingList(
        findings=[
            Finding(
                path="src/api/client.py",
                line=31,
                severity="medium",
                category="documentation",
                body="README still says default timeout is 30s, but it is now 60s.",
                confidence=0.88,
            )
        ]
    )


class TestDocumentationSpec:
    """Verify the documentation spec resolves correctly."""

    def test_spec_exists_in_registry(self) -> None:
        assert "documentation" in SPECIALIST_BY_NAME

    def test_spec_has_correct_category(self) -> None:
        assert _SPEC.category == "documentation"

    def test_spec_prompt_key_resolves(self) -> None:
        from ai_council_review.llm.prompts.loader import load_prompt

        prompt = load_prompt(_SPEC.prompt_key)
        assert prompt is not None

    def test_spec_router_hint_mentions_readme(self) -> None:
        hint_lower = _SPEC.router_hint.lower()
        assert "readme" in hint_lower or "docs" in hint_lower or ".md" in hint_lower


class TestBuildDocumentationChain:
    """Tests for building the documentation agent chain."""

    def test_chain_builds_successfully(self) -> None:
        mock_llm = MagicMock()
        with patch(
            "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            chain = build_specialist_chain(_SPEC, CouncilConfig())
        assert chain is not None

    def test_chain_metadata_tags_agent_name(self) -> None:
        mock_llm = MagicMock()
        with patch(
            "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            chain = build_specialist_chain(_SPEC, CouncilConfig())
        cfg = chain.config
        assert "agent:documentation" in cfg["tags"]


class TestRunDocumentationAgent:
    """Tests for running the documentation agent."""

    def test_findings_tagged_documentation(self) -> None:
        """Findings must carry agent='documentation'."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = _valid_finding_list()

        with (
            patch(
                "ai_council_review.llm.agents.specialist.build_specialist_chain",
                return_value=mock_chain,
            ),
            patch(
                "ai_council_review.llm.agents.specialist.make_repository_tools",
                return_value=[],
            ),
        ):
            findings = run_specialist_agent(_SPEC, _make_state(), CouncilConfig(), browser=None)

        assert len(findings) == 1
        assert findings[0].agent == "documentation"
        assert findings[0].category == "documentation"

    def test_returns_empty_list_on_failure(self) -> None:
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = RuntimeError("LLM failure")

        with patch(
            "ai_council_review.llm.agents.specialist.build_specialist_chain",
            return_value=mock_chain,
        ):
            findings = run_specialist_agent(_SPEC, _make_state(), CouncilConfig(), browser=None)

        assert findings == []
