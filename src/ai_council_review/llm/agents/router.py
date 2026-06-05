"""Router agent — decides which specialist agents to run."""

from __future__ import annotations

from typing import Any, cast

import structlog
from pydantic import BaseModel

from ai_council_review.config import AgentConfig, CouncilConfig
from ai_council_review.llm.prompts.loader import load_prompt
from ai_council_review.llm.providers.factory import LLMProviderFactory
from ai_council_review.models import ReviewState

logger = structlog.get_logger()


class RouterOutput(BaseModel):
    """Structured output from the router agent."""

    agents_needed: list[str]
    review_depth: str
    reasoning: str


def _build_router_variables(state: ReviewState) -> dict[str, Any]:
    """Build prompt variables for the router agent.

    Args:
        state: Current review state.

    Returns:
        Dict of prompt template variables.
    """
    changed_files = state.changed_files
    file_list = "\n".join(
        f"- {f.filename} ({f.status}, +{f.additions}/-{f.deletions})" for f in changed_files
    )

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

    return {
        "repo": repo,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "pr_body": pr_body or "",
        "changed_files": file_list,
        "diff": diff_text,
    }


def build_router_chain(config: CouncilConfig) -> Any:
    """Build an LCEL chain for the router agent.

    Args:
        config: Global council configuration.

    Returns:
        Runnable chain that outputs RouterOutput.
    """
    agent_config = config.agents.get("router", None)
    if agent_config is None:
        agent_config = AgentConfig(
            enabled=True,
            model="fireworks",
            model_name="accounts/fireworks/models/llama-v3p1-70b-instruct",
            temperature=0.1,
            max_tokens=2000,
        )

    llm = LLMProviderFactory.from_config(agent_config, config.providers)
    prompt = load_prompt("router")
    return prompt | llm.with_structured_output(RouterOutput)


def run_router_agent(
    state: ReviewState,
    config: CouncilConfig,
    callbacks: list[Any] | None = None,
) -> RouterOutput:
    """Run the router agent and determine which agents are needed.

    Args:
        state: Current review state.
        config: Council configuration.
        callbacks: Optional LangChain callbacks (e.g., CostCallbackHandler).

    Returns:
        RouterOutput with agents_needed, review_depth, and reasoning.
    """
    logger.info("Router agent starting")
    chain = build_router_chain(config)

    try:
        variables = _build_router_variables(state)
        run_config = {"callbacks": callbacks} if callbacks else None
        result = chain.invoke(variables, config=run_config)
        router_output = cast(RouterOutput, result)
        logger.info(
            "Router complete",
            agents=router_output.agents_needed,
            depth=router_output.review_depth,
        )
        return router_output
    except Exception as e:
        logger.error("Router failed", error=str(e))
        return RouterOutput(
            agents_needed=["security", "quality", "architecture"],
            review_depth="standard",
            reasoning=f"Router failed ({e}), defaulting to all agents",
        )
