"""Tests for graph.py hardening features."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from ai_council_review.config import CouncilConfig
from ai_council_review.cost_tracker import CostTracker
from ai_council_review.graph import (
    _timed_agent_run,
    security_node,
)
from ai_council_review.models import ReviewState


class TestAgentTimeout:
    """Tests for agent timeout handling."""

    def test_agent_timeout_returns_empty(self) -> None:
        """Mock agent that sleeps, verify timeout returns empty findings."""
        mock_agent = MagicMock()
        mock_agent.name = "security"
        mock_agent.run.side_effect = lambda state: time.sleep(0.2)

        state = ReviewState()
        result = _timed_agent_run(mock_agent, state, timeout=0.1)

        assert result["agent_outputs"]["security"] == []
        assert "errors" in result
        assert result["errors"]["security"] == "Timed out after 0.1s"


class TestAgentException:
    """Tests for agent exception handling."""

    def test_agent_exception_returns_empty(self) -> None:
        """Mock agent that raises, verify graceful degradation."""
        mock_agent = MagicMock()
        mock_agent.name = "quality"
        mock_agent.run.side_effect = RuntimeError("Agent crashed")

        state = ReviewState()
        result = _timed_agent_run(mock_agent, state, timeout=5)

        assert result["agent_outputs"]["quality"] == []
        assert "errors" in result
        assert result["errors"]["quality"] == "Failed: Agent crashed"


class TestCostTrackerIntegration:
    """Tests for cost tracker integration in graph nodes."""

    def test_cost_tracker_passed_to_agents(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CostTracker is initialized and passed to agents."""
        mock_tracker = MagicMock(spec=CostTracker)
        state = ReviewState()
        config = CouncilConfig()

        monkeypatch.setattr(
            "ai_council_review.graph._get_browser",
            lambda: None,
        )

        with patch("ai_council_review.graph.SecurityAgent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.run.return_value = []
            mock_agent.name = "security"
            mock_agent_cls.return_value = mock_agent

            security_node(state, config, mock_tracker)

            assert mock_agent.cost_tracker is mock_tracker
            mock_agent.run.assert_called_once_with(state)
