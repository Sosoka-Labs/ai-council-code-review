"""Router agent — decides which specialist agents to run."""

from __future__ import annotations

from typing import Any, cast

import structlog
from pydantic import BaseModel

from ai_council_review.llm.prompts.loader import load_prompt
from ai_council_review.llm.providers.factory import LLMProviderFactory
from ai_council_review.models import ReviewState

logger = structlog.get_logger()


class RouterOutput(BaseModel):
    """Structured output from the router agent."""

    agents_needed: list[str]
    review_depth: str
    reasoning: str


class RouterAgent:
    """Analyzes the PR and decides which agents to invoke."""

    def __init__(self, config: Any) -> None:
        """Initialize the router.

        Args:
            config: CouncilConfig instance.
        """
        self.config = config
        self.agent_config = config.agents.get("router", None)
        if self.agent_config is None:
            # Default router config
            from ai_council_review.config import AgentConfig

            self.agent_config = AgentConfig(
                enabled=True,
                model="fireworks",
                model_name="accounts/fireworks/models/llama-v3p1-70b-instruct",
                temperature=0.1,
                max_tokens=2000,
            )
        self._llm: Any | None = None

    @property
    def llm(self) -> Any:
        """Lazy-load the LLM instance.

        Returns:
            Configured LLM.
        """
        if self._llm is None:
            self._llm = LLMProviderFactory.from_config(self.agent_config, self.config.providers)
        return self._llm

    def run(self, state: ReviewState) -> RouterOutput:
        """Run the router and determine which agents are needed.

        Args:
            state: Current review state.

        Returns:
            RouterOutput with agents_needed, review_depth, and reasoning.
        """
        logger.info("Router agent starting")

        changed_files = state.changed_files
        file_list = "\n".join(
            f"- {f.filename} ({f.status}, +{f.additions}/-{f.deletions})" for f in changed_files
        )

        # Build diff text
        diff_parts: list[str] = []
        for f in changed_files:
            if f.patch:
                diff_parts.append(f"=== {f.filename} ===\n{f.patch}")
        diff_text = "\n\n".join(diff_parts)

        pr = state.pr_metadata
        pr_title = pr.title if pr else ""
        pr_body = pr.body if pr else ""
        pr_number = pr.number if pr else 0
        repo = pr.html_url if pr else ""

        prompt = load_prompt(
            "router",
            repo=repo,
            pr_number=pr_number,
            pr_title=pr_title,
            pr_body=pr_body or "",
            changed_files=file_list,
            diff=diff_text,
        )

        try:
            # Use structured output for reliable JSON parsing
            structured_model = self.llm.with_structured_output(RouterOutput)
            result = structured_model.invoke(prompt)
            router_output = cast(RouterOutput, result)
            logger.info(
                "Router complete",
                agents=router_output.agents_needed,
                depth=router_output.review_depth,
            )
            return router_output
        except Exception as e:
            logger.error("Router failed", error=str(e))
            # Fallback: return all agents
            return RouterOutput(
                agents_needed=["security", "quality", "architecture"],
                review_depth="standard",
                reasoning=f"Router failed ({e}), defaulting to all agents",
            )
