"""Tests for the quality agent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_council_review.config import CouncilConfig
from ai_council_review.exceptions import BudgetExceededError
from ai_council_review.llm.agents.output_models import FindingList
from ai_council_review.llm.agents.quality import build_quality_chain, run_quality_agent
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
    """Return a minimal ReviewState for quality tests."""
    pr = PRMetadata(
        number=3,
        title="Refactor data processing",
        state="open",
        author="carol",
        author_association="CONTRIBUTOR",
        base_ref="main",
        base_sha="ccc",
        head_ref="refactor/data",
        head_sha="ddd",
        html_url="https://github.com/owner/repo/pull/3",
    )
    files = [
        FileInfo(
            filename="src/processor.py",
            status="modified",
            additions=20,
            deletions=5,
            patch="@@ -5,10 +5,25 @@\n+def process(items):\n+    for x in items:\n+        pass\n",
        )
    ]
    return ReviewState(pr_metadata=pr, changed_files=files)


def _valid_finding_list() -> FindingList:
    """Return a FindingList with two quality findings."""
    return FindingList(
        findings=[
            Finding(
                path="src/processor.py",
                line=7,
                severity="medium",
                category="quality",
                body="Function `process` has no type hints or docstring.",
                confidence=0.85,
            ),
            Finding(
                path="src/processor.py",
                line=9,
                severity="low",
                category="quality",
                body="Loop body is a no-op (`pass`); likely unfinished implementation.",
                confidence=0.7,
            ),
        ]
    )


class TestBuildQualityChain:
    """Tests for build_quality_chain."""

    def test_build_quality_chain_succeeds(self) -> None:
        """Chain builds without error given a mocked LLM."""
        mock_llm = MagicMock()

        with patch(
            "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            chain = build_quality_chain(CouncilConfig())

        assert chain is not None

    def test_build_quality_chain_injects_skills_when_registry_provided(self) -> None:
        """apply_skills is called when a non-empty registry with matching skills is given."""
        mock_llm = MagicMock()
        registry = _make_registry("style-guide")

        with (
            patch(
                "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
                return_value=mock_llm,
            ),
            patch(
                "ai_council_review.llm.agents.specialist.apply_skills",
                wraps=lambda prompt, skills: prompt,
            ) as mock_apply,
        ):
            build_quality_chain(
                CouncilConfig(default_agent_skills=["style-guide"]),
                registry=registry,
            )

        mock_apply.assert_called_once()

    def test_build_quality_chain_unchanged_when_registry_is_none(self) -> None:
        """Passing registry=None does not call apply_skills."""
        mock_llm = MagicMock()

        with (
            patch(
                "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
                return_value=mock_llm,
            ),
            patch(
                "ai_council_review.llm.agents.specialist.apply_skills",
            ) as mock_apply,
        ):
            build_quality_chain(CouncilConfig(), registry=None)

        mock_apply.assert_not_called()


class TestRunQualityAgent:
    """Tests for run_quality_agent."""

    def test_run_quality_agent_parses_valid_output(self) -> None:
        """Mock LLM returns FindingList; verify Finding list returned with agent tag."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = _valid_finding_list()

        with patch(
            "ai_council_review.llm.agents.specialist.build_specialist_chain",
            return_value=mock_chain,
        ):
            findings = run_quality_agent(_make_state(), CouncilConfig(), None)

        assert isinstance(findings, list)
        assert len(findings) == 2

        severities = {f.severity for f in findings}
        assert Severity.MEDIUM in severities
        assert Severity.LOW in severities

        for finding in findings:
            assert isinstance(finding, Finding)
            assert finding.path == "src/processor.py"
            assert finding.agent == "quality"

    def test_run_quality_agent_returns_empty_on_bad_output(self) -> None:
        """Mock raises a generic Exception; verify empty list with no crash."""
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = Exception("structured output parse failure")

        with patch(
            "ai_council_review.llm.agents.specialist.build_specialist_chain",
            return_value=mock_chain,
        ):
            findings = run_quality_agent(_make_state(), CouncilConfig(), None)

        assert findings == []

    def test_run_quality_agent_propagates_budget_error(self) -> None:
        """BudgetExceededError is re-raised, not swallowed."""
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = BudgetExceededError("over budget")

        with (
            patch(
                "ai_council_review.llm.agents.specialist.build_specialist_chain",
                return_value=mock_chain,
            ),
            pytest.raises(BudgetExceededError),
        ):
            run_quality_agent(_make_state(), CouncilConfig(), None)
