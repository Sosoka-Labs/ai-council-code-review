"""Quality agent — focused on code quality, correctness, and maintainability."""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.runnables import Runnable

from ai_council_review.config import AgentConfig, CouncilConfig
from ai_council_review.github.browser import RepositoryBrowser
from ai_council_review.llm.agents.parsing import parse_findings
from ai_council_review.llm.prompts.loader import load_prompt
from ai_council_review.llm.providers.factory import LLMProviderFactory
from ai_council_review.models import Finding, ReviewState

logger = structlog.get_logger()


def _build_agent_variables(state: ReviewState) -> dict[str, Any]:
    """Build prompt variables from review state.

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
    pr_number = pr.number if pr else 0
    repo = pr.html_url if pr else ""

    return {
        "repo": repo,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "changed_files": file_list,
        "diff": diff_text,
    }


def build_quality_chain(
    config: CouncilConfig,
    browser: RepositoryBrowser | None,
) -> Runnable[dict[str, Any], Any]:
    """Build a simple LLM chain for the quality agent.

    Args:
        config: Global council configuration.
        browser: Repository browser (unused, kept for API compatibility).

    Returns:
        Configured Runnable chain.
    """
    agent_config = config.agents.get("quality", AgentConfig())
    llm = LLMProviderFactory.from_config(agent_config, config.providers)
    prompt = load_prompt("quality")
    return prompt | llm


def run_quality_agent(
    state: ReviewState,
    config: CouncilConfig,
    browser: RepositoryBrowser | None,
    callbacks: list[Any] | None = None,
) -> list[Finding]:
    """Run the quality agent and return findings.

    Args:
        state: Current review state.
        config: Council configuration.
        browser: Repository browser.
        callbacks: Optional LangChain callbacks (e.g., CostCallbackHandler).

    Returns:
        List of findings.
    """
    logger.info("Quality agent starting")
    chain = build_quality_chain(config, browser)

    try:
        variables = _build_agent_variables(state)
        run_config = {"callbacks": callbacks} if callbacks else None
        message = chain.invoke(variables, config=run_config)  # type: ignore[arg-type]
        output = message.content if hasattr(message, "content") else str(message)
        findings = parse_findings(output, agent_name="quality", logger=logger)
        logger.info("Quality agent finished", findings=len(findings))
        if not findings:
            logger.info("Quality agent raw output", raw_output=output)
        return findings
    except Exception as e:
        logger.error("Quality agent failed", error=str(e))
        return []
