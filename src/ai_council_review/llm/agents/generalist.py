"""Generalist agent — single agent that reviews all aspects of a PR."""

from __future__ import annotations

from typing import Any, cast

import structlog
from langchain.agents import AgentExecutor, create_tool_calling_agent

from ai_council_review.config import AgentConfig, CouncilConfig
from ai_council_review.github.browser import RepositoryBrowser
from ai_council_review.llm.agents.parsing import parse_findings
from ai_council_review.llm.prompts.loader import load_prompt
from ai_council_review.llm.providers.factory import LLMProviderFactory
from ai_council_review.models import Finding, ReviewState
from ai_council_review.tools.repository import make_repository_tools

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


def build_generalist_executor(
    config: CouncilConfig,
    browser: RepositoryBrowser | None,
) -> AgentExecutor:
    """Build an AgentExecutor for the generalist agent.

    Args:
        config: Global council configuration.
        browser: Repository browser for cross-file awareness.

    Returns:
        Configured AgentExecutor.
    """
    agent_config = config.agents.get("generalist", AgentConfig())
    llm = LLMProviderFactory.from_config(agent_config, config.providers)
    tools = make_repository_tools(browser)
    prompt = load_prompt("generalist")

    agent = cast(Any, create_tool_calling_agent(llm, tools, prompt))
    return AgentExecutor(
        agent=agent,
        tools=tools,
        max_execution_time=config.agent_timeout_seconds,
        max_iterations=10,
    )


def run_generalist_agent(
    state: ReviewState,
    config: CouncilConfig,
    browser: RepositoryBrowser | None,
    callbacks: list[Any] | None = None,
) -> list[Finding]:
    """Run the generalist agent and return findings.

    Args:
        state: Current review state.
        config: Council configuration.
        browser: Repository browser.
        callbacks: Optional LangChain callbacks (e.g., CostCallbackHandler).

    Returns:
        List of findings.
    """
    logger.info("Generalist agent starting")
    executor = build_generalist_executor(config, browser)

    try:
        variables = _build_agent_variables(state)
        run_config = {"callbacks": callbacks} if callbacks else None
        result = executor.invoke(variables, config=run_config)  # type: ignore[arg-type]
        findings = parse_findings(result["output"])
        logger.info("Generalist agent finished", findings=len(findings))
        return findings
    except Exception as e:
        logger.error("Generalist agent failed", error=str(e))
        return []
