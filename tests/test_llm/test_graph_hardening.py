"""Tests for graph.py hardening features."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ai_council_review.config import CouncilConfig
from ai_council_review.llm.cost_tracker import CostCallbackHandler, CostTracker
from ai_council_review.llm.graph import _make_specialist_node
from ai_council_review.models import ReviewState


class TestCostTrackerIntegration:
    """Tests for cost tracker integration in graph nodes."""

    def test_cost_tracker_passed_to_agents(self) -> None:
        """Verify a specialist node invokes run_specialist_agent with cost callbacks."""
        mock_tracker = MagicMock(spec=CostTracker)
        state = ReviewState()
        config = CouncilConfig()

        with patch("ai_council_review.llm.graph.run_specialist_agent") as mock_run:
            mock_run.return_value = []

            node = _make_specialist_node("security", config, mock_tracker, None)
            node(state)

            assert mock_run.call_count == 1
            call_args = mock_run.call_args
            # run_specialist_agent(spec, state, config, callbacks=..., registry=...)
            assert call_args.args[1] == state
            assert call_args.args[2] == config
            assert "callbacks" in call_args.kwargs
            assert len(call_args.kwargs["callbacks"]) == 1
            assert isinstance(call_args.kwargs["callbacks"][0], CostCallbackHandler)
