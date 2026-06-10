"""Tests for graph.py hardening features."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ai_council_review.config import CouncilConfig
from ai_council_review.llm.cost_tracker import CostCallbackHandler, CostTracker
from ai_council_review.llm.graph import security_node
from ai_council_review.models import ReviewState


class TestCostTrackerIntegration:
    """Tests for cost tracker integration in graph nodes."""

    def test_cost_tracker_passed_to_agents(self) -> None:
        """Verify security_node invokes run_security_agent with correct args."""
        mock_tracker = MagicMock(spec=CostTracker)
        state = ReviewState()
        config = CouncilConfig()

        with patch("ai_council_review.llm.graph.run_security_agent") as mock_run:
            mock_run.return_value = []

            security_node(state, config, mock_tracker)

            assert mock_run.call_count == 1
            call_args = mock_run.call_args
            assert call_args.args[0] == state
            assert call_args.args[1] == config
            assert "callbacks" in call_args.kwargs
            assert len(call_args.kwargs["callbacks"]) == 1
            assert isinstance(call_args.kwargs["callbacks"][0], CostCallbackHandler)
