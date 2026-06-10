"""Tests for the security agent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_council_review.config import CouncilConfig
from ai_council_review.exceptions import BudgetExceededError
from ai_council_review.llm.agents.output_models import FindingList
from ai_council_review.llm.agents.security import build_security_chain, run_security_agent
from ai_council_review.models import FileInfo, Finding, PRMetadata, ReviewState, Severity


def _make_state() -> ReviewState:
    """Return a minimal ReviewState for security tests."""
    pr = PRMetadata(
        number=2,
        title="Fix auth token handling",
        state="open",
        author="bob",
        author_association="MEMBER",
        base_ref="main",
        base_sha="aaa",
        head_ref="fix/auth",
        head_sha="bbb",
        html_url="https://github.com/owner/repo/pull/2",
    )
    files = [
        FileInfo(
            filename="src/auth.py",
            status="modified",
            additions=5,
            deletions=1,
            patch="@@ -10,5 +10,9 @@\n-token = request.GET['token']\n+token = request.headers.get('Authorization')\n",
        )
    ]
    return ReviewState(pr_metadata=pr, changed_files=files)


def _valid_finding_list() -> FindingList:
    """Return a FindingList with one security finding."""
    return FindingList(
        findings=[
            Finding(
                path="src/auth.py",
                line=12,
                severity="high",
                category="security",
                body="Token retrieved from query param instead of header — exposes credentials in logs.",
                confidence=0.9,
            )
        ]
    )


class TestBuildSecurityChain:
    """Tests for build_security_chain."""

    def test_build_security_chain_succeeds(self) -> None:
        """Chain builds without error given a mocked LLM."""
        mock_llm = MagicMock()

        with patch(
            "ai_council_review.llm.agents.security.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            chain = build_security_chain(CouncilConfig())

        assert chain is not None


class TestRunSecurityAgent:
    """Tests for run_security_agent."""

    def test_run_security_agent_parses_valid_output(self) -> None:
        """Mock LLM returns FindingList; verify Finding list returned with agent tag."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = _valid_finding_list()

        with patch(
            "ai_council_review.llm.agents.security.build_security_chain",
            return_value=mock_chain,
        ):
            findings = run_security_agent(_make_state(), CouncilConfig(), None)

        assert isinstance(findings, list)
        assert len(findings) == 1
        finding = findings[0]
        assert isinstance(finding, Finding)
        assert finding.path == "src/auth.py"
        assert finding.severity == Severity.HIGH
        assert finding.category == "security"
        assert finding.agent == "security"

    def test_run_security_agent_returns_empty_on_bad_output(self) -> None:
        """Mock raises a generic Exception; verify empty list with no crash."""
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = Exception("structured output parse failure")

        with patch(
            "ai_council_review.llm.agents.security.build_security_chain",
            return_value=mock_chain,
        ):
            findings = run_security_agent(_make_state(), CouncilConfig(), None)

        assert findings == []

    def test_run_security_agent_propagates_budget_error(self) -> None:
        """BudgetExceededError is re-raised, not swallowed."""
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = BudgetExceededError("over budget")

        with (
            patch(
                "ai_council_review.llm.agents.security.build_security_chain",
                return_value=mock_chain,
            ),
            pytest.raises(BudgetExceededError),
        ):
            run_security_agent(_make_state(), CouncilConfig(), None)
