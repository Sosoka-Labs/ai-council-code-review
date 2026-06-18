"""Tests for the devops specialist agent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ai_council_review.config import CouncilConfig
from ai_council_review.llm.agents.output_models import FindingList
from ai_council_review.llm.agents.registry import SPECIALIST_BY_NAME
from ai_council_review.llm.agents.specialist import build_specialist_chain, run_specialist_agent
from ai_council_review.models import FileInfo, Finding, PRMetadata, ReviewState

_SPEC = SPECIALIST_BY_NAME["devops"]


def _make_state() -> ReviewState:
    pr = PRMetadata(
        number=22,
        title="Add CI workflow",
        state="open",
        author="carol",
        author_association="CONTRIBUTOR",
        base_ref="main",
        base_sha="eee",
        head_ref="feat/ci",
        head_sha="fff",
        html_url="https://github.com/owner/repo/pull/22",
    )
    files = [
        FileInfo(
            filename=".github/workflows/ci.yml",
            status="added",
            additions=20,
            deletions=0,
            patch=(
                "@@ -0,0 +1,20 @@\n"
                "+name: CI\n"
                "+on: [push]\n"
                "+jobs:\n"
                "+  build:\n"
                "+    runs-on: ubuntu-latest\n"
                "+    steps:\n"
                "+      - uses: actions/checkout@v4\n"
                "+      - run: echo ${{ github.event.pull_request.title }}\n"
            ),
        )
    ]
    return ReviewState(pr_metadata=pr, changed_files=files)


def _valid_finding_list() -> FindingList:
    return FindingList(
        findings=[
            Finding(
                path=".github/workflows/ci.yml",
                line=7,
                severity="high",
                category="devops",
                body=(
                    "actions/checkout@v4 should be pinned to a full commit SHA "
                    "to prevent supply-chain attacks via tag mutation."
                ),
                confidence=0.95,
            )
        ]
    )


class TestDevopsSpec:
    """Verify the devops spec resolves correctly."""

    def test_spec_exists_in_registry(self) -> None:
        assert "devops" in SPECIALIST_BY_NAME

    def test_spec_has_correct_category(self) -> None:
        assert _SPEC.category == "devops"

    def test_spec_prompt_key_resolves(self) -> None:
        from ai_council_review.llm.prompts.loader import load_prompt

        prompt = load_prompt(_SPEC.prompt_key)
        assert prompt is not None

    def test_spec_router_hint_mentions_workflows(self) -> None:
        hint_lower = _SPEC.router_hint.lower()
        assert "workflow" in hint_lower or "github" in hint_lower or ".github" in hint_lower

    def test_spec_router_hint_mentions_dockerfile(self) -> None:
        hint_lower = _SPEC.router_hint.lower()
        assert "dockerfile" in hint_lower or "docker" in hint_lower or "terraform" in hint_lower


class TestBuildDevopsChain:
    """Tests for building the devops agent chain."""

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
        assert "agent:devops" in cfg["tags"]


class TestRunDevopsAgent:
    """Tests for running the devops agent."""

    def test_findings_tagged_devops(self) -> None:
        """Findings must carry agent='devops'."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = _valid_finding_list()

        with patch(
            "ai_council_review.llm.agents.specialist.build_specialist_chain",
            return_value=mock_chain,
        ):
            findings = run_specialist_agent(_SPEC, _make_state(), CouncilConfig(), browser=None)

        assert len(findings) == 1
        assert findings[0].agent == "devops"
        assert findings[0].category == "devops"

    def test_returns_empty_list_on_failure(self) -> None:
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = RuntimeError("LLM failure")

        with patch(
            "ai_council_review.llm.agents.specialist.build_specialist_chain",
            return_value=mock_chain,
        ):
            findings = run_specialist_agent(_SPEC, _make_state(), CouncilConfig(), browser=None)

        assert findings == []
