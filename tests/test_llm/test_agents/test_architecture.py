"""Tests for the architecture agent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_council_review.config import CouncilConfig
from ai_council_review.exceptions import BudgetExceededError
from ai_council_review.llm.agents.architecture import (
    build_architecture_chain,
    run_architecture_agent,
)
from ai_council_review.llm.agents.output_models import FindingList
from ai_council_review.models import FileInfo, Finding, PRMetadata, ReviewState, Severity
from ai_council_review.skills.models import Skill
from ai_council_review.skills.registry import SkillRegistry


def _make_registry(*names: str) -> SkillRegistry:
    skills = {
        n: Skill(
            name=n,
            description=f"Desc {n}",
            body=f"# {n} body",
            path=Path(f"/fake/{n}/SKILL.md"),
            raw_frontmatter={"name": n, "description": f"Desc {n}"},
        )
        for n in names
    }
    return SkillRegistry(skills)


def _make_state() -> ReviewState:
    """Return a minimal ReviewState for architecture tests."""
    pr = PRMetadata(
        number=4,
        title="Introduce new service layer",
        state="open",
        author="dave",
        author_association="MEMBER",
        base_ref="main",
        base_sha="eee",
        head_ref="feat/service-layer",
        head_sha="fff",
        html_url="https://github.com/owner/repo/pull/4",
    )
    files = [
        FileInfo(
            filename="src/services/payment.py",
            status="added",
            additions=80,
            deletions=0,
            patch="@@ -0,0 +1,80 @@\n+class PaymentService:\n+    pass\n",
        ),
        FileInfo(
            filename="src/routes/payments.py",
            status="modified",
            additions=15,
            deletions=3,
            patch="@@ -1,5 +1,17 @@\n+from services.payment import PaymentService\n",
        ),
    ]
    return ReviewState(pr_metadata=pr, changed_files=files)


def _valid_finding_list() -> FindingList:
    """Return a FindingList with one architecture finding."""
    return FindingList(
        findings=[
            Finding(
                path="src/services/payment.py",
                line=1,
                severity="medium",
                category="architecture",
                body="PaymentService is empty — missing interface contract and dependency injection.",
                confidence=0.8,
            )
        ]
    )


class TestBuildArchitectureChain:
    """Tests for build_architecture_chain."""

    def test_build_architecture_chain_succeeds(self) -> None:
        """Chain builds without error given a mocked LLM."""
        mock_llm = MagicMock()

        with patch(
            "ai_council_review.llm.agents.architecture.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            chain = build_architecture_chain(CouncilConfig())

        assert chain is not None

    def test_build_architecture_chain_injects_skills_when_registry_provided(self) -> None:
        """apply_skills is called when a non-empty registry with matching skills is given."""
        mock_llm = MagicMock()
        registry = _make_registry("domain-glossary")

        with (
            patch(
                "ai_council_review.llm.agents.architecture.LLMProviderFactory.from_config",
                return_value=mock_llm,
            ),
            patch(
                "ai_council_review.llm.agents.architecture.apply_skills",
                wraps=lambda prompt, skills: prompt,
            ) as mock_apply,
        ):
            build_architecture_chain(
                CouncilConfig(default_agent_skills=["domain-glossary"]),
                registry=registry,
            )

        mock_apply.assert_called_once()

    def test_build_architecture_chain_unchanged_when_registry_is_none(self) -> None:
        """Passing registry=None does not call apply_skills."""
        mock_llm = MagicMock()

        with (
            patch(
                "ai_council_review.llm.agents.architecture.LLMProviderFactory.from_config",
                return_value=mock_llm,
            ),
            patch(
                "ai_council_review.llm.agents.architecture.apply_skills",
            ) as mock_apply,
        ):
            build_architecture_chain(CouncilConfig(), registry=None)

        mock_apply.assert_not_called()


class TestRunArchitectureAgent:
    """Tests for run_architecture_agent."""

    def test_run_architecture_agent_parses_valid_output(self) -> None:
        """Mock LLM returns FindingList; verify Finding list returned with agent tag."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = _valid_finding_list()

        with patch(
            "ai_council_review.llm.agents.architecture.build_architecture_chain",
            return_value=mock_chain,
        ):
            findings = run_architecture_agent(_make_state(), CouncilConfig())

        assert isinstance(findings, list)
        assert len(findings) == 1
        finding = findings[0]
        assert isinstance(finding, Finding)
        assert finding.path == "src/services/payment.py"
        assert finding.severity == Severity.MEDIUM
        assert finding.category == "architecture"
        assert finding.agent == "architecture"

    def test_run_architecture_agent_returns_empty_on_bad_output(self) -> None:
        """Mock raises a generic Exception; verify empty list with no crash."""
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = Exception("structured output parse failure")

        with patch(
            "ai_council_review.llm.agents.architecture.build_architecture_chain",
            return_value=mock_chain,
        ):
            findings = run_architecture_agent(_make_state(), CouncilConfig())

        assert findings == []

    def test_run_architecture_agent_propagates_budget_error(self) -> None:
        """BudgetExceededError is re-raised, not swallowed."""
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = BudgetExceededError("over budget")

        with (
            patch(
                "ai_council_review.llm.agents.architecture.build_architecture_chain",
                return_value=mock_chain,
            ),
            pytest.raises(BudgetExceededError),
        ):
            run_architecture_agent(_make_state(), CouncilConfig())
