"""Tests for the generalist agent."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from ai_council_review.config import CouncilConfig
from ai_council_review.exceptions import BudgetExceededError
from ai_council_review.llm.agents.generalist import (
    build_generalist_executor,
    run_generalist_agent,
)
from ai_council_review.models import FileInfo, Finding, PRMetadata, ReviewState, Severity


def _make_state() -> ReviewState:
    """Return a minimal ReviewState for generalist tests."""
    pr = PRMetadata(
        number=6,
        title="Generalist review test",
        state="open",
        author="frank",
        author_association="CONTRIBUTOR",
        base_ref="main",
        base_sha="iii",
        head_ref="feat/generalist",
        head_sha="jjj",
        html_url="https://github.com/owner/repo/pull/6",
    )
    files = [
        FileInfo(
            filename="src/utils.py",
            status="modified",
            additions=10,
            deletions=3,
            patch="@@ -1,5 +1,12 @@\n+def helper():\n+    pass\n",
        )
    ]
    return ReviewState(pr_metadata=pr, changed_files=files)


def _valid_findings_json() -> str:
    findings = [
        {
            "path": "src/utils.py",
            "line": 2,
            "severity": "low",
            "category": "quality",
            "body": "helper() is empty and has no docstring.",
            "confidence": 0.75,
        }
    ]
    return json.dumps(findings)


class TestBuildGeneralistExecutor:
    """Tests for build_generalist_executor."""

    def test_build_generalist_executor_returns_runnable(self) -> None:
        """Chain builds successfully for any provider (all providers supported)."""
        mock_llm = MagicMock()

        with patch(
            "ai_council_review.llm.agents.generalist.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            chain = build_generalist_executor(CouncilConfig(), None)

        assert chain is not None


class TestRunGeneralistAgent:
    """Tests for run_generalist_agent."""

    def test_run_generalist_agent_parses_output(self) -> None:
        """Mock chain returns AIMessage with valid findings JSON; verify Finding list."""
        mock_result = MagicMock()
        mock_result.content = _valid_findings_json()
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_result

        with patch(
            "ai_council_review.llm.agents.generalist.build_generalist_executor",
            return_value=mock_chain,
        ):
            findings = run_generalist_agent(_make_state(), CouncilConfig(), None)

        assert isinstance(findings, list)
        assert len(findings) == 1
        finding = findings[0]
        assert isinstance(finding, Finding)
        assert finding.path == "src/utils.py"
        assert finding.severity == Severity.LOW
        assert finding.agent == "generalist"

    def test_run_generalist_agent_returns_empty_on_bad_output(self) -> None:
        """Mock chain returns non-JSON content; verify empty list with no crash."""
        mock_result = MagicMock()
        mock_result.content = "Looks good to me, no issues."
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_result

        with patch(
            "ai_council_review.llm.agents.generalist.build_generalist_executor",
            return_value=mock_chain,
        ):
            findings = run_generalist_agent(_make_state(), CouncilConfig(), None)

        assert findings == []

    def test_run_generalist_agent_propagates_budget_error(self) -> None:
        """BudgetExceededError is re-raised, not swallowed."""
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = BudgetExceededError("over budget")

        with (
            patch(
                "ai_council_review.llm.agents.generalist.build_generalist_executor",
                return_value=mock_chain,
            ),
            pytest.raises(BudgetExceededError),
        ):
            run_generalist_agent(_make_state(), CouncilConfig(), None)
