"""Tests for the performance specialist agent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ai_council_review.config import CouncilConfig
from ai_council_review.llm.agents.output_models import FindingList
from ai_council_review.llm.agents.registry import SPECIALIST_BY_NAME
from ai_council_review.llm.agents.specialist import build_specialist_chain, run_specialist_agent
from ai_council_review.models import FileInfo, Finding, PRMetadata, ReviewState

_SPEC = SPECIALIST_BY_NAME["performance"]


def _make_state() -> ReviewState:
    pr = PRMetadata(
        number=20,
        title="Add user list endpoint",
        state="open",
        author="alice",
        author_association="CONTRIBUTOR",
        base_ref="main",
        base_sha="aaa",
        head_ref="feat/user-list",
        head_sha="bbb",
        html_url="https://github.com/owner/repo/pull/20",
    )
    files = [
        FileInfo(
            filename="src/api/users.py",
            status="modified",
            additions=15,
            deletions=0,
            patch=(
                "@@ -0,0 +1,15 @@\n"
                "+def list_users():\n"
                "+    users = User.objects.all()\n"
                "+    for user in users:\n"
                "+        _ = user.orders.all()  # N+1\n"
                "+    return users\n"
            ),
        )
    ]
    return ReviewState(pr_metadata=pr, changed_files=files)


def _valid_finding_list() -> FindingList:
    return FindingList(
        findings=[
            Finding(
                path="src/api/users.py",
                line=4,
                severity="high",
                category="performance",
                body="N+1: user.orders accessed in loop without prefetch_related.",
                confidence=0.95,
            )
        ]
    )


class TestPerformanceSpec:
    """Verify the performance spec resolves correctly."""

    def test_spec_exists_in_registry(self) -> None:
        assert "performance" in SPECIALIST_BY_NAME

    def test_spec_has_correct_category(self) -> None:
        assert _SPEC.category == "performance"

    def test_spec_prompt_key_resolves(self) -> None:
        from ai_council_review.llm.prompts.loader import load_prompt

        prompt = load_prompt(_SPEC.prompt_key)
        assert prompt is not None

    def test_spec_router_hint_mentions_n_plus_one(self) -> None:
        assert "N+1" in _SPEC.router_hint or "n+1" in _SPEC.router_hint.lower()


class TestBuildPerformanceChain:
    """Tests for building the performance agent chain."""

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
        assert "agent:performance" in cfg["tags"]


class TestRunPerformanceAgent:
    """Tests for running the performance agent."""

    def test_findings_tagged_performance(self) -> None:
        """Findings must carry agent='performance'."""
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
        assert findings[0].agent == "performance"
        assert findings[0].category == "performance"

    def test_returns_empty_list_on_failure(self) -> None:
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = RuntimeError("LLM failure")

        with patch(
            "ai_council_review.llm.agents.specialist.build_specialist_chain",
            return_value=mock_chain,
        ):
            findings = run_specialist_agent(_SPEC, _make_state(), CouncilConfig(), browser=None)

        assert findings == []
