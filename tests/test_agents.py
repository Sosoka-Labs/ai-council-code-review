"""Tests for ai_council_review.agents."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ai_council_review.agents.architecture import ArchitectureAgent
from ai_council_review.agents.base import BaseAgent
from ai_council_review.agents.generalist import GeneralistAgent
from ai_council_review.agents.quality import QualityAgent
from ai_council_review.agents.router import RouterAgent, RouterOutput
from ai_council_review.agents.security import SecurityAgent
from ai_council_review.agents.synthesis import SynthesisAgent, SynthesisOutput
from ai_council_review.config import CouncilConfig
from ai_council_review.cost_tracker import CostTracker
from ai_council_review.models import (
    FileInfo,
    FileStatus,
    Finding,
    PRMetadata,
    ReviewState,
    Severity,
)


class DummyAgent(BaseAgent):
    """Concrete agent for testing BaseAgent behavior."""

    def __init__(self, config: CouncilConfig, cost_tracker: Any | None = None) -> None:
        super().__init__("dummy", config, cost_tracker=cost_tracker)

    def get_tools(self) -> list[Any]:
        return []

    def get_prompt(self, state: ReviewState) -> str:
        return "dummy prompt"


def _make_pr() -> PRMetadata:
    return PRMetadata(
        number=1,
        title="Test PR",
        state="open",
        author="test",
        author_association="OWNER",
        base_ref="main",
        base_sha="abc",
        head_ref="feat",
        head_sha="def",
        html_url="https://github.com/test/repo/pull/1",
    )


def _make_state() -> ReviewState:
    return ReviewState(
        pr_metadata=_make_pr(),
        changed_files=[
            FileInfo(
                filename="src/main.py",
                status=FileStatus.MODIFIED,
                additions=5,
                deletions=2,
                patch="diff content",
            )
        ],
    )


class TestBaseAgent:
    """Tests for BaseAgent."""

    def test_cannot_instantiate_abstract(self) -> None:
        """Test that BaseAgent is abstract."""
        with pytest.raises(TypeError):
            BaseAgent("test", CouncilConfig())

    def test_parse_findings_with_json(self) -> None:
        """Test parsing findings from JSON."""
        agent = DummyAgent(CouncilConfig())
        text = json.dumps(
            [
                {
                    "path": "src/main.py",
                    "severity": "high",
                    "category": "bug",
                    "body": "issue",
                    "confidence": 0.9,
                }
            ]
        )
        findings = agent._parse_findings(text)
        assert len(findings) == 1
        assert findings[0].path == "src/main.py"
        assert findings[0].severity == Severity.HIGH

    def test_parse_findings_no_json(self) -> None:
        """Test parsing findings when no JSON present."""
        agent = DummyAgent(CouncilConfig())
        findings = agent._parse_findings("no json here")
        assert findings == []

    def test_parse_findings_invalid_json(self) -> None:
        """Test parsing findings with invalid JSON."""
        agent = DummyAgent(CouncilConfig())
        findings = agent._parse_findings("[invalid json}")
        assert findings == []

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_run_with_structured_output(self, mock_from_config: MagicMock) -> None:
        """Test BaseAgent.run with structured output success."""
        agent = DummyAgent(CouncilConfig())
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.with_structured_output.return_value = mock_structured
        mock_result = MagicMock()
        mock_result.findings = [
            Finding(path="src/a.py", severity=Severity.LOW, category="style", body="test")
        ]
        mock_structured.invoke.return_value = mock_result
        mock_from_config.return_value = mock_llm

        findings = agent.run(_make_state())
        assert len(findings) == 1
        assert findings[0].path == "src/a.py"

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_run_fallback(self, mock_from_config: MagicMock) -> None:
        """Test BaseAgent.run fallback when structured output fails."""
        agent = DummyAgent(CouncilConfig())
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.invoke.side_effect = Exception("structured output failed")

        mock_response = MagicMock()
        mock_response.content = json.dumps(
            [
                {
                    "path": "src/b.py",
                    "severity": "medium",
                    "category": "bug",
                    "body": "fallback",
                }
            ]
        )
        mock_llm.invoke.return_value = mock_response
        mock_from_config.return_value = mock_llm

        findings = agent.run(_make_state())
        assert len(findings) == 1
        assert findings[0].path == "src/b.py"

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_run_records_cost(self, mock_from_config: MagicMock) -> None:
        """Test that BaseAgent.run records cost."""
        config = CouncilConfig()
        tracker = CostTracker(config)
        agent = DummyAgent(config, cost_tracker=tracker)

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.with_structured_output.return_value = mock_structured
        mock_result = MagicMock()
        mock_result.findings = []
        mock_structured.invoke.return_value = mock_result
        mock_from_config.return_value = mock_llm

        agent.run(_make_state())
        assert len(tracker.records) == 1

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_run_budget_exceeded(self, mock_from_config: MagicMock) -> None:
        """Test that BaseAgent.run raises BudgetExceededError."""
        from ai_council_review.exceptions import BudgetExceededError

        config = CouncilConfig(budget_usd=0.0)
        tracker = CostTracker(config)
        agent = DummyAgent(config, cost_tracker=tracker)

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.invoke.return_value = MagicMock(findings=[])
        mock_from_config.return_value = mock_llm

        with pytest.raises(BudgetExceededError):
            agent.run(_make_state())

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_fallback_run(self, mock_from_config: MagicMock) -> None:
        """Test BaseAgent._fallback_run."""
        agent = DummyAgent(CouncilConfig())
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            [{"path": "src/c.py", "severity": "low", "category": "style", "body": "test"}]
        )
        mock_llm.invoke.return_value = mock_response
        mock_from_config.return_value = mock_llm

        findings = agent._fallback_run("prompt", [])
        assert len(findings) == 1
        assert findings[0].path == "src/c.py"

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_fallback_run_failure(self, mock_from_config: MagicMock) -> None:
        """Test BaseAgent._fallback_run when LLM fails."""
        agent = DummyAgent(CouncilConfig())
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("llm failed")
        mock_from_config.return_value = mock_llm

        findings = agent._fallback_run("prompt", [])
        assert findings == []

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_record_cost_with_usage(self, mock_from_config: MagicMock) -> None:
        """Test _record_cost with actual usage metadata."""
        config = CouncilConfig()
        tracker = CostTracker(config)
        agent = DummyAgent(config, cost_tracker=tracker)

        mock_llm = MagicMock()
        mock_from_config.return_value = mock_llm

        response = MagicMock()
        response.usage_metadata = {
            "input_tokens": 100,
            "output_tokens": 50,
        }

        agent._record_cost("prompt", response=response)
        assert len(tracker.records) == 1
        assert tracker.records[0].actual_input_tokens == 100
        assert tracker.records[0].actual_output_tokens == 50

    def test_record_cost_no_tracker(self) -> None:
        """Test _record_cost does nothing when no tracker."""
        agent = DummyAgent(CouncilConfig())
        # Should not raise
        agent._record_cost("prompt")


class TestSecurityAgent:
    """Tests for SecurityAgent."""

    @patch("ai_council_review.agents.security.load_prompt")
    def test_get_prompt(self, mock_load: MagicMock) -> None:
        """Test SecurityAgent.get_prompt renders correctly."""
        mock_load.return_value = "security prompt"
        agent = SecurityAgent(CouncilConfig())
        state = _make_state()
        result = agent.get_prompt(state)
        assert result == "security prompt"
        mock_load.assert_called_once()
        kwargs = mock_load.call_args.kwargs
        assert kwargs["repo"] == "https://github.com/test/repo/pull/1"
        assert kwargs["pr_number"] == 1
        assert kwargs["pr_title"] == "Test PR"
        assert "changed_files" in kwargs
        assert "diff" in kwargs

    def test_get_tools_with_browser(self) -> None:
        """Test SecurityAgent.get_tools with browser."""
        browser = MagicMock()
        agent = SecurityAgent(CouncilConfig(), browser=browser)
        tools = agent.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "read_file"

    def test_get_tools_without_browser(self) -> None:
        """Test SecurityAgent.get_tools without browser."""
        agent = SecurityAgent(CouncilConfig())
        tools = agent.get_tools()
        assert tools == []

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_run(self, mock_from_config: MagicMock) -> None:
        """Test SecurityAgent.run."""
        agent = SecurityAgent(CouncilConfig())
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            [
                {
                    "path": "src/main.py",
                    "severity": "high",
                    "category": "security",
                    "body": "issue",
                }
            ]
        )
        mock_llm.invoke.return_value = mock_response
        mock_from_config.return_value = mock_llm

        findings = agent.run(_make_state())
        assert len(findings) == 1
        assert findings[0].category == "security"

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_run_fallback(self, mock_from_config: MagicMock) -> None:
        """Test SecurityAgent.run fallback."""
        agent = SecurityAgent(CouncilConfig())
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = Exception("fail")
        mock_from_config.return_value = mock_llm

        findings = agent.run(_make_state())
        assert findings == []


class TestQualityAgent:
    """Tests for QualityAgent."""

    @patch("ai_council_review.agents.quality.load_prompt")
    def test_get_prompt(self, mock_load: MagicMock) -> None:
        """Test QualityAgent.get_prompt renders correctly."""
        mock_load.return_value = "quality prompt"
        agent = QualityAgent(CouncilConfig())
        state = _make_state()
        result = agent.get_prompt(state)
        assert result == "quality prompt"
        kwargs = mock_load.call_args.kwargs
        assert kwargs["pr_number"] == 1

    def test_get_tools_with_browser(self) -> None:
        """Test QualityAgent.get_tools with browser."""
        browser = MagicMock()
        agent = QualityAgent(CouncilConfig(), browser=browser)
        tools = agent.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "read_file"

    def test_get_tools_without_browser(self) -> None:
        """Test QualityAgent.get_tools without browser."""
        agent = QualityAgent(CouncilConfig())
        tools = agent.get_tools()
        assert tools == []

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_run(self, mock_from_config: MagicMock) -> None:
        """Test QualityAgent.run."""
        agent = QualityAgent(CouncilConfig())
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            [
                {
                    "path": "src/main.py",
                    "severity": "medium",
                    "category": "quality",
                    "body": "issue",
                }
            ]
        )
        mock_llm.invoke.return_value = mock_response
        mock_from_config.return_value = mock_llm

        findings = agent.run(_make_state())
        assert len(findings) == 1
        assert findings[0].category == "quality"

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_run_fallback(self, mock_from_config: MagicMock) -> None:
        """Test QualityAgent.run fallback."""
        agent = QualityAgent(CouncilConfig())
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = Exception("fail")
        mock_from_config.return_value = mock_llm

        findings = agent.run(_make_state())
        assert findings == []


class TestArchitectureAgent:
    """Tests for ArchitectureAgent."""

    @patch("ai_council_review.agents.architecture.load_prompt")
    def test_get_prompt(self, mock_load: MagicMock) -> None:
        """Test ArchitectureAgent.get_prompt renders correctly."""
        mock_load.return_value = "arch prompt"
        agent = ArchitectureAgent(CouncilConfig())
        state = _make_state()
        result = agent.get_prompt(state)
        assert result == "arch prompt"
        kwargs = mock_load.call_args.kwargs
        assert kwargs["pr_number"] == 1

    def test_get_tools_with_browser(self) -> None:
        """Test ArchitectureAgent.get_tools with browser."""
        browser = MagicMock()
        agent = ArchitectureAgent(CouncilConfig(), browser=browser)
        tools = agent.get_tools()
        assert len(tools) == 3
        names = [t.name for t in tools]
        assert "read_file" in names
        assert "list_files" in names
        assert "find_files" in names

    def test_get_tools_without_browser(self) -> None:
        """Test ArchitectureAgent.get_tools without browser."""
        agent = ArchitectureAgent(CouncilConfig())
        tools = agent.get_tools()
        assert tools == []

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_run(self, mock_from_config: MagicMock) -> None:
        """Test ArchitectureAgent.run."""
        agent = ArchitectureAgent(CouncilConfig())
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            [
                {
                    "path": "src/main.py",
                    "severity": "low",
                    "category": "architecture",
                    "body": "issue",
                }
            ]
        )
        mock_llm.invoke.return_value = mock_response
        mock_from_config.return_value = mock_llm

        findings = agent.run(_make_state())
        assert len(findings) == 1
        assert findings[0].category == "architecture"

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_run_fallback(self, mock_from_config: MagicMock) -> None:
        """Test ArchitectureAgent.run fallback."""
        agent = ArchitectureAgent(CouncilConfig())
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = Exception("fail")
        mock_from_config.return_value = mock_llm

        findings = agent.run(_make_state())
        assert findings == []


class TestGeneralistAgent:
    """Tests for GeneralistAgent."""

    @patch("ai_council_review.agents.generalist.load_prompt")
    def test_get_prompt(self, mock_load: MagicMock) -> None:
        """Test GeneralistAgent.get_prompt renders correctly."""
        mock_load.return_value = "generalist prompt"
        agent = GeneralistAgent(CouncilConfig())
        state = _make_state()
        result = agent.get_prompt(state)
        assert result == "generalist prompt"
        kwargs = mock_load.call_args.kwargs
        assert kwargs["pr_number"] == 1

    def test_get_tools_with_browser(self) -> None:
        """Test GeneralistAgent.get_tools with browser."""
        browser = MagicMock()
        agent = GeneralistAgent(CouncilConfig(), browser=browser)
        tools = agent.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "read_file"

    def test_get_tools_without_browser(self) -> None:
        """Test GeneralistAgent.get_tools without browser."""
        agent = GeneralistAgent(CouncilConfig())
        tools = agent.get_tools()
        assert tools == []

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_run(self, mock_from_config: MagicMock) -> None:
        """Test GeneralistAgent.run."""
        agent = GeneralistAgent(CouncilConfig())
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            [
                {
                    "path": "src/main.py",
                    "severity": "low",
                    "category": "general",
                    "body": "issue",
                }
            ]
        )
        mock_llm.invoke.return_value = mock_response
        mock_from_config.return_value = mock_llm

        findings = agent.run(_make_state())
        assert len(findings) == 1
        assert findings[0].category == "general"

    @patch("ai_council_review.agents.base.LLMProviderFactory.from_config")
    def test_run_fallback(self, mock_from_config: MagicMock) -> None:
        """Test GeneralistAgent.run fallback."""
        agent = GeneralistAgent(CouncilConfig())
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = Exception("fail")
        mock_from_config.return_value = mock_llm

        findings = agent.run(_make_state())
        assert findings == []


class TestRouterAgent:
    """Tests for RouterAgent."""

    @patch("ai_council_review.agents.router.load_prompt")
    @patch("ai_council_review.agents.router.LLMProviderFactory.from_config")
    def test_run(self, mock_from_config: MagicMock, mock_load: MagicMock) -> None:
        """Test RouterAgent.run."""
        mock_load.return_value = "router prompt"
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_result = RouterOutput(
            agents_needed=["security", "quality"],
            review_depth="deep",
            reasoning="test",
        )
        mock_structured.invoke.return_value = mock_result
        mock_from_config.return_value = mock_llm

        agent = RouterAgent(CouncilConfig())
        result = agent.run(_make_state())
        assert result.agents_needed == ["security", "quality"]
        assert result.review_depth == "deep"
        mock_load.assert_called_once()

    @patch("ai_council_review.agents.router.load_prompt")
    @patch("ai_council_review.agents.router.LLMProviderFactory.from_config")
    def test_run_fallback(self, mock_from_config: MagicMock, mock_load: MagicMock) -> None:
        """Test RouterAgent.run fallback on error."""
        mock_load.return_value = "router prompt"
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.invoke.side_effect = Exception("fail")
        mock_from_config.return_value = mock_llm

        agent = RouterAgent(CouncilConfig())
        result = agent.run(_make_state())
        assert result.agents_needed == ["security", "quality", "architecture"]
        assert result.review_depth == "standard"

    def test_default_config(self) -> None:
        """Test RouterAgent default config."""
        config = CouncilConfig()
        agent = RouterAgent(config)
        assert agent.agent_config.enabled is True
        assert agent.agent_config.model == "fireworks"


class TestSynthesisAgent:
    """Tests for SynthesisAgent."""

    @patch("ai_council_review.agents.synthesis.load_prompt")
    @patch("ai_council_review.agents.synthesis.LLMProviderFactory.from_config")
    def test_run(self, mock_from_config: MagicMock, mock_load: MagicMock) -> None:
        """Test SynthesisAgent.run."""
        mock_load.return_value = "synthesis prompt"
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_result = SynthesisOutput(
            summary="summary",
            verdict="comment",
            findings=[
                Finding(
                    path="src/main.py", severity=Severity.LOW, category="style", body="test"
                )
            ],
            categories=["style"],
        )
        mock_structured.invoke.return_value = mock_result
        mock_from_config.return_value = mock_llm

        agent = SynthesisAgent(CouncilConfig())
        state = _make_state()
        state.agent_outputs = {
            "security": [
                Finding(
                    path="src/main.py",
                    severity=Severity.HIGH,
                    category="security",
                    body="issue",
                )
            ]
        }
        result = agent.run(state)
        assert result.verdict == "comment"
        assert len(result.findings) == 1
        mock_load.assert_called_once()

    @patch("ai_council_review.agents.synthesis.load_prompt")
    @patch("ai_council_review.agents.synthesis.LLMProviderFactory.from_config")
    def test_run_fallback(self, mock_from_config: MagicMock, mock_load: MagicMock) -> None:
        """Test SynthesisAgent.run fallback on error."""
        mock_load.return_value = "synthesis prompt"
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.invoke.side_effect = Exception("fail")
        mock_from_config.return_value = mock_llm

        agent = SynthesisAgent(CouncilConfig())
        state = _make_state()
        state.agent_outputs = {
            "security": [
                Finding(
                    path="src/main.py",
                    severity=Severity.HIGH,
                    category="security",
                    body="issue",
                )
            ]
        }
        result = agent.run(state)
        assert result.verdict == "comment"
        assert len(result.findings) == 1

    def test_fallback_synthesize_no_findings(self) -> None:
        """Test SynthesisAgent._fallback_synthesize with empty findings."""
        agent = SynthesisAgent(CouncilConfig())
        result = agent._fallback_synthesize([])
        assert result.verdict == "approve"
        assert result.findings == []
        assert "## AI Code Review" in result.summary

    def test_fallback_synthesize_deduplicates(self) -> None:
        """Test SynthesisAgent._fallback_synthesize deduplication."""
        agent = SynthesisAgent(CouncilConfig())
        findings = [
            {
                "path": "a.py",
                "severity": "high",
                "category": "bug",
                "body": "dup",
                "confidence": 0.9,
            },
            {
                "path": "a.py",
                "severity": "high",
                "category": "bug",
                "body": "dup",
                "confidence": 0.9,
            },
            {
                "path": "b.py",
                "severity": "critical",
                "category": "sec",
                "body": "unique",
                "confidence": 0.9,
            },
        ]
        result = agent._fallback_synthesize(findings)
        assert len(result.findings) == 2
        assert result.findings[0].severity == Severity.CRITICAL
        assert result.verdict == "request_changes"

    def test_default_config(self) -> None:
        """Test SynthesisAgent default config."""
        config = CouncilConfig()
        agent = SynthesisAgent(config)
        assert agent.agent_config.enabled is True
        assert agent.agent_config.model == "fireworks"
