"""Base agent class for AI Council Code Review."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import cast

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool

from ai_council_review.config import AgentConfig, CouncilConfig
from ai_council_review.exceptions import BudgetExceededError
from ai_council_review.llm.cost_tracker import CostTracker
from ai_council_review.llm.providers.factory import LLMProviderFactory
from ai_council_review.models import CostRecord, Finding, ReviewState

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Abstract base class for all review agents."""

    def __init__(
        self,
        name: str,
        config: CouncilConfig,
        agent_config: AgentConfig | None = None,
        cost_tracker: CostTracker | None = None,
    ) -> None:
        """Initialize the agent.

        Args:
            name: Agent identifier.
            config: Global council configuration.
            agent_config: Agent-specific configuration. If None, looks up
                `config.agents[name]`.
            cost_tracker: Optional cost tracker for budget enforcement.
        """
        self.name = name
        self.config = config
        self.agent_config = agent_config or config.agents.get(name, AgentConfig())
        self.cost_tracker = cost_tracker
        self._llm: BaseChatModel | None = None

    @property
    def llm(self) -> BaseChatModel:
        """Lazy-load the LLM instance.

        Returns:
            Configured BaseChatModel.
        """
        if self._llm is None:
            self._llm = LLMProviderFactory.from_config(self.agent_config, self.config.providers)
        return self._llm

    @abstractmethod
    def get_tools(self) -> list[BaseTool]:
        """Return the tools available to this agent.

        Returns:
            List of LangChain tools.
        """
        ...

    @abstractmethod
    def get_prompt(self, state: ReviewState) -> str:
        """Render the system prompt for this agent.

        Args:
            state: Current review state.

        Returns:
            The rendered prompt text.
        """
        ...

    def run(self, state: ReviewState) -> list[Finding]:
        """Run the agent and return findings.

        Args:
            state: Current review state.

        Returns:
            List of findings from this agent.

        Raises:
            BudgetExceededError: If the budget would be exceeded.
        """
        logger.info("Agent starting", agent=self.name)
        prompt = self.get_prompt(state)
        tools = self.get_tools()

        estimated_cost = 0.0
        if self.cost_tracker:
            estimated_cost = self.cost_tracker.estimate_cost(
                self.name,
                self.agent_config.model_name,
                prompt,
                self.agent_config.max_tokens,
            )
            self.cost_tracker.check_budget(estimated_cost)

        findings: list[Finding] = []
        try:
            model = self.llm.bind_tools(tools) if tools else self.llm

            # Use structured output if the model supports it
            from pydantic import BaseModel

            class AgentOutput(BaseModel):
                """Structured output from the agent."""

                findings: list[Finding]

            structured_model = model.with_structured_output(AgentOutput)  # type: ignore[attr-defined]
            result = structured_model.invoke(prompt)
            findings = cast(list[Finding], result.findings)
        except Exception as e:
            if isinstance(e, BudgetExceededError):
                raise
            logger.error("Agent failed", agent=self.name, error=str(e))
            # Fallback: invoke without structured output and parse manually
            findings = self._fallback_run(prompt, tools)
        else:
            if self.cost_tracker:
                self._record_cost(prompt, estimated_cost=estimated_cost)

        logger.info("Agent finished", agent=self.name, findings=len(findings))
        return findings

    def _fallback_run(self, prompt: str, tools: list[BaseTool]) -> list[Finding]:
        """Fallback invocation when structured output fails.

        Args:
            prompt: The system prompt.
            tools: Available tools.

        Returns:
            List of findings.

        Raises:
            BudgetExceededError: If the budget would be exceeded.
        """
        estimated_cost = 0.0
        if self.cost_tracker:
            estimated_cost = self.cost_tracker.estimate_cost(
                self.name,
                self.agent_config.model_name,
                prompt,
                self.agent_config.max_tokens,
            )
            self.cost_tracker.check_budget(estimated_cost)

        try:
            response = self.llm.invoke(prompt)
            text = str(response.content)
        except Exception as e:
            if isinstance(e, BudgetExceededError):
                raise
            logger.error("Agent fallback failed", agent=self.name, error=str(e))
            return []
        else:
            if self.cost_tracker:
                self._record_cost(prompt, response=response, estimated_cost=estimated_cost)
            return self._parse_findings(text)

    def _record_cost(
        self,
        prompt: str,
        response: BaseMessage | None = None,
        estimated_cost: float | None = None,
    ) -> None:
        """Record cost for an LLM invocation.

        Args:
            prompt: The prompt text.
            response: Optional LLM response message with usage metadata.
            estimated_cost: Pre-computed estimated cost.
        """
        if self.cost_tracker is None:
            return

        model = self.agent_config.model_name
        estimated_input = self.cost_tracker._estimate_tokens(prompt)
        estimated_output = self.agent_config.max_tokens

        if estimated_cost is None:
            estimated_cost = self.cost_tracker.estimate_cost(
                self.name,
                model,
                prompt,
                estimated_output,
            )

        actual_input: int | None = None
        actual_output: int | None = None

        if response is not None and hasattr(response, "usage_metadata"):
            usage = response.usage_metadata
            if isinstance(usage, dict):
                actual_input = usage.get("input_tokens")
                if actual_input is None:
                    actual_input = usage.get("prompt_tokens")
                actual_output = usage.get("output_tokens")
                if actual_output is None:
                    actual_output = usage.get("completion_tokens")

        if actual_input is not None and actual_output is not None:
            input_price, output_price = self.cost_tracker._get_pricing(model)
            actual_cost = (
                actual_input * input_price / 1_000_000 + actual_output * output_price / 1_000_000
            )
            record = CostRecord(
                agent=self.name,
                model=model,
                estimated_input_tokens=estimated_input,
                estimated_output_tokens=estimated_output,
                actual_input_tokens=actual_input,
                actual_output_tokens=actual_output,
                estimated_cost_usd=actual_cost,
            )
        else:
            record = CostRecord(
                agent=self.name,
                model=model,
                estimated_input_tokens=estimated_input,
                estimated_output_tokens=estimated_output,
                estimated_cost_usd=estimated_cost,
            )

        self.cost_tracker.record_cost(record)

    def _parse_findings(self, text: str) -> list[Finding]:
        """Parse findings from unstructured text.

        Args:
            text: Raw agent output.

        Returns:
            List of parsed findings.
        """
        import json
        import re

        # Try to extract JSON array
        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return [Finding(**item) for item in data if isinstance(item, dict)]
            except Exception:
                pass
        return []
