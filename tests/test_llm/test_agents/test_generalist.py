"""Tests for the generalist agent."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from ai_council_review.config import AgentConfig, CouncilConfig
from ai_council_review.exceptions import BudgetExceededError, ConfigError
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

    def test_build_generalist_executor_raises_on_anthropic(self) -> None:
        """ConfigError is raised when the agent_config has provider attribute set to anthropic.

        Note: AgentConfig has no `provider` field — the guard checks
        `getattr(agent_config, "provider", "")`. To trigger it we must inject
        a config object that exposes `provider = "anthropic"`.
        """
        mock_llm = MagicMock()

        # Inject an agent_config with provider="anthropic" via a mock
        mock_agent_config = MagicMock(spec=AgentConfig)
        mock_agent_config.provider = "anthropic"

        config = CouncilConfig()
        config.agents["generalist"] = mock_agent_config  # type: ignore[assignment]

        with (
            patch(
                "ai_council_review.llm.agents.generalist.LLMProviderFactory.from_config",
                return_value=mock_llm,
            ),
            pytest.raises(ConfigError, match="not compatible with Anthropic"),
        ):
            build_generalist_executor(config, None)

    def test_build_generalist_executor_succeeds_for_non_anthropic(self) -> None:
        """Executor builds successfully when provider is not anthropic."""
        mock_llm = MagicMock()
        mock_executor = MagicMock()

        with (
            patch(
                "ai_council_review.llm.agents.generalist.LLMProviderFactory.from_config",
                return_value=mock_llm,
            ),
            patch(
                "ai_council_review.llm.agents.generalist.create_tool_calling_agent",
                return_value=MagicMock(),
            ),
            patch(
                "ai_council_review.llm.agents.generalist.AgentExecutor",
                return_value=mock_executor,
            ),
        ):
            executor = build_generalist_executor(CouncilConfig(), None)

        assert executor is mock_executor


class TestRunGeneralistAgent:
    """Tests for run_generalist_agent."""

    def test_run_generalist_agent_parses_output(self) -> None:
        """Mock executor returns valid findings JSON; verify Finding list returned."""
        mock_executor = MagicMock()
        mock_executor.invoke.return_value = {"output": _valid_findings_json()}

        with patch(
            "ai_council_review.llm.agents.generalist.build_generalist_executor",
            return_value=mock_executor,
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
        """Mock executor returns non-JSON; verify empty list with no crash."""
        mock_executor = MagicMock()
        mock_executor.invoke.return_value = {"output": "Looks good to me, no issues."}

        with patch(
            "ai_council_review.llm.agents.generalist.build_generalist_executor",
            return_value=mock_executor,
        ):
            findings = run_generalist_agent(_make_state(), CouncilConfig(), None)

        assert findings == []

    def test_run_generalist_agent_propagates_budget_error(self) -> None:
        """BudgetExceededError is re-raised, not swallowed."""
        mock_executor = MagicMock()
        mock_executor.invoke.side_effect = BudgetExceededError("over budget")

        with (
            patch(
                "ai_council_review.llm.agents.generalist.build_generalist_executor",
                return_value=mock_executor,
            ),
            pytest.raises(BudgetExceededError),
        ):
            run_generalist_agent(_make_state(), CouncilConfig(), None)
