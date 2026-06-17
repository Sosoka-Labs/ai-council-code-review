"""Tests for ai_council_review.llm.cost_tracker."""

from __future__ import annotations

import pytest

from ai_council_review.config import CouncilConfig
from ai_council_review.exceptions import BudgetExceededError
from ai_council_review.llm.cost_tracker import CostTracker
from ai_council_review.models import CostRecord


class TestCostTracker:
    """Tests for CostTracker."""

    def test_estimate_cost_basic(self) -> None:
        """Estimate cost for a known model."""
        config = CouncilConfig(budget_usd=5.0)
        tracker = CostTracker(config)

        prompt = "a" * 400  # 100 tokens at 4 chars per token
        cost = tracker.estimate_cost(
            agent="security",
            model="accounts/fireworks/models/llama-v3p1-70b-instruct",
            prompt=prompt,
            max_tokens=1000,
        )

        expected = (100 * 0.50 / 1_000_000) + (1000 * 0.50 / 1_000_000)
        assert cost == pytest.approx(expected)

    def test_estimate_cost_fallback(self) -> None:
        """Estimate cost for unknown model uses fallback."""
        config = CouncilConfig(budget_usd=5.0)
        tracker = CostTracker(config)

        prompt = "test"
        cost = tracker.estimate_cost(
            agent="security",
            model="unknown-model-v42",
            prompt=prompt,
            max_tokens=500,
        )

        expected = (1 * 0.50 / 1_000_000) + (500 * 0.50 / 1_000_000)
        assert cost == pytest.approx(expected)

    def test_record_cost_updates_total(self) -> None:
        """Recording cost updates total."""
        config = CouncilConfig(budget_usd=5.0)
        tracker = CostTracker(config)

        record = CostRecord(
            agent="security",
            model="gpt-4o",
            estimated_cost_usd=1.25,
        )
        tracker.record_cost(record)

        assert tracker.total_cost_usd == 1.25
        assert len(tracker.records) == 1

    def test_check_budget_raises_when_exceeded(self) -> None:
        """BudgetExceededError raised when budget is exceeded."""
        config = CouncilConfig(budget_usd=1.0)
        tracker = CostTracker(config)
        tracker.total_cost_usd = 1.5

        with pytest.raises(BudgetExceededError):
            tracker.check_budget()

    def test_check_budget_passes_when_under(self) -> None:
        """No error when under budget."""
        config = CouncilConfig(budget_usd=5.0)
        tracker = CostTracker(config)
        tracker.total_cost_usd = 1.0

        tracker.check_budget()

    def test_get_summary(self) -> None:
        """Returns correct dict."""
        config = CouncilConfig(budget_usd=10.0)
        tracker = CostTracker(config)
        tracker.total_cost_usd = 3.5

        summary = tracker.get_summary()

        assert summary["total_cost_usd"] == 3.5
        assert summary["budget_usd"] == 10.0
        assert summary["remaining_usd"] == 6.5

    def test_partial_model_match(self) -> None:
        """Partial model name matches pricing."""
        config = CouncilConfig(budget_usd=5.0)
        tracker = CostTracker(config)

        prompt = "a" * 400
        cost = tracker.estimate_cost(
            agent="security",
            model="llama-v3p1-70b-instruct",  # partial match
            prompt=prompt,
            max_tokens=1000,
        )

        # Should match the 70b pricing, not fallback
        expected = (100 * 0.50 / 1_000_000) + (1000 * 0.50 / 1_000_000)
        assert cost == pytest.approx(expected)

    def test_gpt_4_1_pricing(self) -> None:
        """gpt-4.1 alias resolves to its own pricing entry, not fallback."""
        config = CouncilConfig(budget_usd=10.0)
        tracker = CostTracker(config)

        # 400 chars → 100 tokens; max_tokens=1000
        prompt = "a" * 400
        cost = tracker.estimate_cost(
            agent="quality",
            model="gpt-4.1",
            prompt=prompt,
            max_tokens=1000,
        )

        # gpt-4.1: $2.00 input / $8.00 output per 1M tokens
        expected = (100 * 2.00 / 1_000_000) + (1000 * 8.00 / 1_000_000)
        assert cost == pytest.approx(expected)

    def test_gpt_4_1_mini_pricing(self) -> None:
        """gpt-4.1-mini alias resolves to its own pricing entry, not gpt-4.1's."""
        config = CouncilConfig(budget_usd=10.0)
        tracker = CostTracker(config)

        prompt = "a" * 400
        cost = tracker.estimate_cost(
            agent="quality",
            model="gpt-4.1-mini",
            prompt=prompt,
            max_tokens=1000,
        )

        # gpt-4.1-mini: $0.40 input / $1.60 output per 1M tokens
        expected = (100 * 0.40 / 1_000_000) + (1000 * 1.60 / 1_000_000)
        assert cost == pytest.approx(expected)

    def test_gpt_4_1_mini_does_not_match_gpt_4_1_pricing(self) -> None:
        """gpt-4.1-mini must not be priced as gpt-4.1 (substring order guard)."""
        config = CouncilConfig(budget_usd=10.0)
        tracker = CostTracker(config)

        prompt = "a" * 400
        mini_cost = tracker.estimate_cost("q", "gpt-4.1-mini", prompt, 1000)
        full_cost = tracker.estimate_cost("q", "gpt-4.1", prompt, 1000)

        # mini should be cheaper than the full model
        assert mini_cost < full_cost
