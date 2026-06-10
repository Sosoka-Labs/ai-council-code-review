"""Cost tracker — estimate and track LLM costs, enforce budget."""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from ai_council_review.config import CouncilConfig
from ai_council_review.exceptions import BudgetExceededError
from ai_council_review.models import CostRecord

logger = structlog.get_logger()

# Conservative pricing per 1M tokens (input, output) in USD
_DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    "accounts/fireworks/routers/kimi-k2p6-turbo": (2.50, 2.50),
    "accounts/fireworks/models/llama-v3p1-70b-instruct": (0.50, 0.50),
    "accounts/fireworks/models/llama-v3p1-8b-instruct": (0.20, 0.20),
    "accounts/fireworks/models/llama-v3p1-405b-instruct": (2.00, 2.00),
    "gpt-4o": (5.00, 15.00),
    "gpt-4o-mini": (0.15, 0.60),
    "claude-3-5-sonnet": (3.00, 12.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-haiku": (0.25, 1.25),
}

# Fallback pricing if model not in map
_FALLBACK_INPUT_PRICE = 0.50
_FALLBACK_OUTPUT_PRICE = 0.50

# Rough heuristic: 1 token ≈ 4 characters
_CHARS_PER_TOKEN = 4


class CostTracker:
    """Tracks estimated and actual costs for LLM calls."""

    def __init__(self, config: CouncilConfig) -> None:
        """Initialize the cost tracker.

        Args:
            config: Council configuration with budget and provider settings.
        """
        self.config = config
        self.records: list[CostRecord] = []
        self.total_cost_usd = 0.0

    def estimate_cost(self, agent: str, model: str, prompt: str, max_tokens: int) -> float:
        """Estimate the cost of an LLM call.

        Uses a conservative estimate based on prompt length and max_tokens.

        Args:
            agent: Agent name.
            model: Model identifier.
            prompt: The prompt text.
            max_tokens: Maximum tokens to generate.

        Returns:
            Estimated cost in USD.
        """
        input_tokens = self._estimate_tokens(prompt)
        output_tokens = max_tokens
        input_price, output_price = self._get_pricing(model)
        estimated = (input_tokens * input_price / 1_000_000) + (
            output_tokens * output_price / 1_000_000
        )
        logger.debug(
            "Estimated cost",
            agent=agent,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated,
        )
        return estimated

    def record_cost(self, record: CostRecord) -> None:
        """Record an actual or estimated cost.

        Args:
            record: Cost record to add.

        Raises:
            BudgetExceededError: If the new total would exceed the budget.
        """
        self.records.append(record)
        self.total_cost_usd += record.estimated_cost_usd
        logger.info(
            "Recorded cost",
            agent=record.agent,
            model=record.model,
            cost_usd=record.estimated_cost_usd,
            total_cost_usd=self.total_cost_usd,
        )
        self.check_budget()

    def check_budget(self, estimated_cost: float = 0.0) -> None:
        """Check if the budget would be exceeded.

        Args:
            estimated_cost: Additional estimated cost to check against.

        Raises:
            BudgetExceededError: If the budget is exceeded.
        """
        if self.total_cost_usd + estimated_cost > self.config.budget_usd:
            msg = (
                f"Budget exceeded: ${self.total_cost_usd + estimated_cost:.4f} "
                f"used of ${self.config.budget_usd:.2f} budget"
            )
            logger.error(
                "Budget exceeded",
                total_cost_usd=self.total_cost_usd,
                estimated_cost=estimated_cost,
                budget_usd=self.config.budget_usd,
            )
            raise BudgetExceededError(msg)

    def _get_pricing(self, model: str) -> tuple[float, float]:
        """Get pricing for a model.

        Args:
            model: Model identifier.

        Returns:
            Tuple of (input_price_per_1m, output_price_per_1m).
        """
        if model in _DEFAULT_PRICING:
            return _DEFAULT_PRICING[model]

        # Partial match for known model families
        if "kimi-k2p6" in model:
            return _DEFAULT_PRICING["accounts/fireworks/routers/kimi-k2p6-turbo"]
        if "llama-v3p1-70b" in model:
            return _DEFAULT_PRICING["accounts/fireworks/models/llama-v3p1-70b-instruct"]
        if "llama-v3p1-8b" in model:
            return _DEFAULT_PRICING["accounts/fireworks/models/llama-v3p1-8b-instruct"]
        if "llama-v3p1-405b" in model:
            return _DEFAULT_PRICING["accounts/fireworks/models/llama-v3p1-405b-instruct"]
        if "gpt-4o-mini" in model:
            return _DEFAULT_PRICING["gpt-4o-mini"]
        if "gpt-4o" in model:
            return _DEFAULT_PRICING["gpt-4o"]
        if "claude-sonnet-4" in model:
            return _DEFAULT_PRICING["claude-sonnet-4-20250514"]
        if "claude-3-5-sonnet" in model:
            return _DEFAULT_PRICING["claude-3-5-sonnet"]
        if "claude-3-5-haiku" in model:
            return _DEFAULT_PRICING["claude-3-5-haiku"]
        if "claude-3-haiku" in model:
            return _DEFAULT_PRICING["claude-3-haiku"]

        return (_FALLBACK_INPUT_PRICE, _FALLBACK_OUTPUT_PRICE)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text length.

        Args:
            text: Text to estimate.

        Returns:
            Estimated token count.
        """
        return len(text) // _CHARS_PER_TOKEN

    def get_summary(self) -> dict[str, float]:
        """Return a cost summary.

        Returns:
            Dictionary with total_cost_usd, budget_usd, remaining_usd.
        """
        return {
            "total_cost_usd": self.total_cost_usd,
            "budget_usd": self.config.budget_usd,
            "remaining_usd": max(0.0, self.config.budget_usd - self.total_cost_usd),
        }


class CostCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler that records LLM costs via a CostTracker.

    Attach this handler to any LangChain chain or agent executor::

        tracker = CostTracker(config)
        handler = CostCallbackHandler(tracker, agent_name="security", model_name="gpt-4o")
        result = chain.invoke(input, config={"callbacks": [handler]})
    """

    def __init__(
        self,
        cost_tracker: CostTracker,
        agent_name: str,
        model_name: str,
        max_tokens: int = 4000,
    ) -> None:
        """Initialize the handler.

        Args:
            cost_tracker: CostTracker instance for recording and budget checks.
            agent_name: Identifier for the agent making the LLM call.
            model_name: Model identifier for pricing lookup.
            max_tokens: Maximum expected output tokens.
        """
        super().__init__()
        self.cost_tracker = cost_tracker
        self.agent_name = agent_name
        self.model_name = model_name
        self.max_tokens = max_tokens
        self._estimated_cost = 0.0

    def on_llm_start(
        self,
        serialized: dict[str, Any] | None,
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Estimate cost before the LLM call and check budget."""
        prompt_text = "\n".join(prompts)
        self._estimated_cost = self.cost_tracker.estimate_cost(
            self.agent_name,
            self.model_name,
            prompt_text,
            self.max_tokens,
        )
        self.cost_tracker.check_budget(self._estimated_cost)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Record actual cost after the LLM call."""
        actual_input: int | None = None
        actual_output: int | None = None

        # Extract usage from the first generation's message
        if response.generations:
            first_gen = response.generations[0][0]
            message = getattr(first_gen, "message", None)
            if message is not None and hasattr(message, "usage_metadata"):
                usage = message.usage_metadata
                if isinstance(usage, dict):
                    actual_input = usage.get("input_tokens") or usage.get("prompt_tokens")
                    actual_output = usage.get("output_tokens") or usage.get("completion_tokens")

        estimated_input = self.cost_tracker._estimate_tokens(
            "\n".join(getattr(response, "prompts", []))
        )

        if actual_input is not None and actual_output is not None:
            input_price, output_price = self.cost_tracker._get_pricing(self.model_name)
            actual_cost = (
                actual_input * input_price / 1_000_000 + actual_output * output_price / 1_000_000
            )
            record = CostRecord(
                agent=self.agent_name,
                model=self.model_name,
                estimated_input_tokens=estimated_input,
                estimated_output_tokens=self.max_tokens,
                actual_input_tokens=actual_input,
                actual_output_tokens=actual_output,
                estimated_cost_usd=actual_cost,
            )
        else:
            record = CostRecord(
                agent=self.agent_name,
                model=self.model_name,
                estimated_input_tokens=estimated_input,
                estimated_output_tokens=self.max_tokens,
                estimated_cost_usd=self._estimated_cost,
            )

        self.cost_tracker.record_cost(record)
        self._estimated_cost = 0.0
