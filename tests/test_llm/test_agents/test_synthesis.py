"""Tests for the synthesis agent."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from ai_council_review.config import CouncilConfig
from ai_council_review.exceptions import BudgetExceededError
from ai_council_review.llm.agents.synthesis import (
    SynthesisOutput,
    _fallback_synthesize,
    build_synthesis_chain,
    run_synthesis_agent,
)
from ai_council_review.models import FileInfo, Finding, PRMetadata, ReviewState, Severity


def _make_state(agent_outputs: dict[str, list[Finding]] | None = None) -> ReviewState:
    """Return a ReviewState with optional pre-populated agent_outputs."""
    pr = PRMetadata(
        number=5,
        title="Merge all the things",
        state="open",
        author="eve",
        author_association="CONTRIBUTOR",
        base_ref="main",
        base_sha="ggg",
        head_ref="merge/all",
        head_sha="hhh",
        html_url="https://github.com/owner/repo/pull/5",
    )
    files = [FileInfo(filename="src/main.py", status="modified")]
    return ReviewState(
        pr_metadata=pr,
        changed_files=files,
        agent_outputs=agent_outputs or {},
    )


def _make_finding(
    path: str = "src/main.py",
    severity: str = "medium",
    category: str = "quality",
    body: str = "Some issue",
    line: int | None = 10,
) -> Finding:
    return Finding(path=path, severity=severity, category=category, body=body, line=line)


def _finding_as_dict(finding: Finding) -> dict[str, Any]:
    """Convert a Finding to the raw dict form used by _fallback_synthesize."""
    return {
        "path": finding.path,
        "position": finding.position,
        "severity": finding.severity.value,
        "category": finding.category,
        "body": finding.body,
        "confidence": finding.confidence,
        "line": finding.line,
    }


def _valid_synthesis_json() -> str:
    """Return a valid synthesis JSON response."""
    payload = {
        "summary": "Two findings across security and quality.",
        "verdict": "comment",
        "findings": [
            {
                "path": "src/main.py",
                "severity": "high",
                "category": "security",
                "body": "SQL injection risk in raw query.",
                "confidence": 0.95,
            }
        ],
        "categories": ["security"],
    }
    return json.dumps(payload)


class TestBuildSynthesisChain:
    """Tests for build_synthesis_chain."""

    def test_build_synthesis_chain_succeeds(self) -> None:
        """Chain builds without error given a mocked LLM."""
        mock_llm = MagicMock()

        with patch(
            "ai_council_review.llm.agents.synthesis.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            chain = build_synthesis_chain(CouncilConfig())

        assert chain is not None


class TestRunSynthesisAgent:
    """Tests for run_synthesis_agent."""

    def test_run_synthesis_agent_returns_synthesis_output(self) -> None:
        """Mock chain returns valid synthesis JSON; verify SynthesisOutput returned."""
        mock_message = AIMessage(content=_valid_synthesis_json())
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_message

        state = _make_state(
            agent_outputs={"security": [_make_finding(severity="high", category="security")]}
        )

        with patch(
            "ai_council_review.llm.agents.synthesis.build_synthesis_chain",
            return_value=mock_chain,
        ):
            result = run_synthesis_agent(state, CouncilConfig())

        assert isinstance(result, SynthesisOutput)
        assert result.verdict == "comment"
        assert result.summary == "Two findings across security and quality."
        assert len(result.findings) == 1
        assert result.categories == ["security"]

    def test_run_synthesis_agent_falls_back_when_parse_fails(self) -> None:
        """When LLM returns unparseable output, fallback synthesis is used."""
        mock_message = AIMessage(content="I could not synthesize anything useful.")
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_message

        finding = _make_finding(severity="high", category="security", body="XSS vulnerability")
        state = _make_state(agent_outputs={"security": [finding]})

        with patch(
            "ai_council_review.llm.agents.synthesis.build_synthesis_chain",
            return_value=mock_chain,
        ):
            result = run_synthesis_agent(state, CouncilConfig())

        assert isinstance(result, SynthesisOutput)
        assert len(result.findings) >= 1

    def test_run_synthesis_agent_propagates_budget_error(self) -> None:
        """BudgetExceededError propagates — not caught by synthesis."""
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = BudgetExceededError("over budget")

        # With no agent_outputs, fallback would produce empty synthesis.
        # But BudgetExceededError must propagate before fallback is reached.
        with (
            patch(
                "ai_council_review.llm.agents.synthesis.build_synthesis_chain",
                return_value=mock_chain,
            ),
            pytest.raises(BudgetExceededError),
        ):
            run_synthesis_agent(_make_state(), CouncilConfig())


class TestFallbackSynthesize:
    """Tests for the _fallback_synthesize helper."""

    def test_fallback_synthesize_deduplicates(self) -> None:
        """Duplicate findings (same path/position/body prefix) are deduplicated."""
        finding = _make_finding(body="Duplicate issue here in the code", line=5)
        raw = _finding_as_dict(finding)
        # Two identical dicts — only one should survive dedup
        result = _fallback_synthesize([raw, raw])

        assert len(result.findings) == 1

    def test_fallback_synthesize_deduplicates_near_identical_bodies(self) -> None:
        """Findings with the same path/line and same first-200-chars of body are deduped."""
        body = "A" * 200
        f1: dict[str, Any] = {
            "path": "src/a.py",
            "position": None,
            "severity": "medium",
            "category": "quality",
            "body": body,
            "confidence": 0.8,
            "line": 1,
        }
        # Tail differs but first 200 chars are identical — should dedup
        f2 = {**f1, "body": body + " EXTRA"}

        result = _fallback_synthesize([f1, f2])
        assert len(result.findings) == 1

    def test_fallback_synthesize_sorts_by_severity(self) -> None:
        """Findings are sorted high → low severity (critical first, info last)."""
        raw_findings: list[dict[str, Any]] = [
            {
                "path": "src/a.py",
                "position": None,
                "severity": "low",
                "category": "quality",
                "body": "Low severity finding",
                "confidence": 0.7,
                "line": 1,
            },
            {
                "path": "src/b.py",
                "position": None,
                "severity": "critical",
                "category": "security",
                "body": "Critical severity finding",
                "confidence": 0.95,
                "line": 2,
            },
            {
                "path": "src/c.py",
                "position": None,
                "severity": "medium",
                "category": "quality",
                "body": "Medium severity finding",
                "confidence": 0.8,
                "line": 3,
            },
        ]
        result = _fallback_synthesize(raw_findings)

        assert len(result.findings) == 3
        severities = [f.severity for f in result.findings]
        assert severities[0] == Severity.CRITICAL
        assert severities[1] == Severity.MEDIUM
        assert severities[2] == Severity.LOW

    def test_fallback_synthesize_verdict_request_changes_on_critical(self) -> None:
        """A critical finding forces verdict to request_changes."""
        raw: dict[str, Any] = {
            "path": "src/main.py",
            "position": None,
            "severity": "critical",
            "category": "security",
            "body": "RCE vulnerability",
            "confidence": 0.99,
            "line": 5,
        }
        result = _fallback_synthesize([raw])
        assert result.verdict == "request_changes"

    def test_fallback_synthesize_verdict_approve_on_empty(self) -> None:
        """No findings results in an approve verdict."""
        result = _fallback_synthesize([])
        assert result.verdict == "approve"
        assert result.findings == []
