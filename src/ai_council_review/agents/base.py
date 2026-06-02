"""Base agent class for AI Council Code Review."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import cast

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from ai_council_review.config import AgentConfig, CouncilConfig
from ai_council_review.llm_provider import LLMProviderFactory
from ai_council_review.models import Finding, ReviewState

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Abstract base class for all review agents."""

    def __init__(
        self,
        name: str,
        config: CouncilConfig,
        agent_config: AgentConfig | None = None,
    ) -> None:
        """Initialize the agent.

        Args:
            name: Agent identifier.
            config: Global council configuration.
            agent_config: Agent-specific configuration. If None, looks up
                `config.agents[name]`.
        """
        self.name = name
        self.config = config
        self.agent_config = agent_config or config.agents.get(name, AgentConfig())
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
        """
        logger.info("Agent starting", agent=self.name)
        prompt = self.get_prompt(state)
        tools = self.get_tools()

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
            logger.error("Agent failed", agent=self.name, error=str(e))
            # Fallback: invoke without structured output and parse manually
            findings = self._fallback_run(prompt, tools)

        logger.info("Agent finished", agent=self.name, findings=len(findings))
        return findings

    def _fallback_run(self, prompt: str, tools: list[BaseTool]) -> list[Finding]:
        """Fallback invocation when structured output fails.

        Args:
            prompt: The system prompt.
            tools: Available tools.

        Returns:
            List of findings.
        """
        try:
            response = self.llm.invoke(prompt)
            text = str(response.content)
            return self._parse_findings(text)
        except Exception as e:
            logger.error("Agent fallback failed", agent=self.name, error=str(e))
            return []

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
