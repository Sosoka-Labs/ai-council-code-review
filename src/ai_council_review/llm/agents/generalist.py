"""Generalist agent — single agent that reviews all aspects of a PR."""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.runnables import Runnable, RunnableConfig

from ai_council_review.config import AgentConfig, CouncilConfig
from ai_council_review.exceptions import BudgetExceededError
from ai_council_review.github.browser import RepositoryBrowser
from ai_council_review.llm.agents.parsing import parse_findings
from ai_council_review.llm.prompts.loader import load_prompt
from ai_council_review.llm.providers.factory import LLMProviderFactory
from ai_council_review.models import Finding, ReviewState
from ai_council_review.skills import Skill, apply_skills
from ai_council_review.skills.registry import SkillRegistry
from ai_council_review.skills.resolution import (
    SkillMode,
    bind_chain_metadata,
    resolve_skills_for_agent,
)

logger = structlog.get_logger()


_PR_TITLE_MAX_CHARS = 500


def _build_agent_variables(state: ReviewState, config: CouncilConfig) -> dict[str, Any]:
    """Build prompt variables from review state.

    Applies safety limits on untrusted PR content (title, diff) before
    injecting into LLM prompts.

    Args:
        state: Current review state.
        config: Council configuration (used for max_diff_size).

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

    max_chars = config.max_diff_size
    if len(diff_text) > max_chars:
        diff_text = diff_text[:max_chars] + f"\n\n[... diff truncated at {max_chars} chars ...]"

    pr = state.pr_metadata
    pr_title = (pr.title or "")[:_PR_TITLE_MAX_CHARS] if pr else ""
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
    browser: RepositoryBrowser | None,  # noqa: ARG001
    registry: SkillRegistry | None = None,
) -> Runnable[dict[str, Any], Any]:
    """Build a prompt | llm chain for the generalist agent.

    Args:
        config: Global council configuration.
        browser: Reserved for future tool-based browsing; currently unused.
        registry: Optional skill registry. When provided, resolved skill bodies
            are appended to the system prompt.

    Returns:
        LangChain Runnable (prompt | llm).
    """
    agent_config = config.agents.get("generalist", AgentConfig())
    llm = LLMProviderFactory.from_config(agent_config, config.providers)
    prompt = load_prompt("generalist")
    skills: list[Skill] = []
    skill_mode: SkillMode = "none"
    if registry is not None:
        skills = resolve_skills_for_agent("generalist", config, registry)
        if skills:
            prompt = apply_skills(prompt, skills)
            skill_mode = "bodies"
    chain = prompt | llm
    return bind_chain_metadata(chain, "generalist", skills, skill_mode)


def run_generalist_agent(
    state: ReviewState,
    config: CouncilConfig,
    browser: RepositoryBrowser | None,
    callbacks: list[Any] | None = None,
    registry: SkillRegistry | None = None,
) -> list[Finding]:
    """Run the generalist agent and return findings.

    Args:
        state: Current review state.
        config: Council configuration.
        browser: Repository browser.
        callbacks: Optional LangChain callbacks (e.g., CostCallbackHandler).
        registry: Optional skill registry for skill injection.

    Returns:
        List of findings.
    """
    logger.info("Generalist agent starting")
    chain = build_generalist_executor(config, browser, registry=registry)

    try:
        variables = _build_agent_variables(state, config)
        run_config: RunnableConfig | None = {"callbacks": callbacks} if callbacks else None
        result = chain.invoke(variables, config=run_config)
        output: str = result.content if hasattr(result, "content") else str(result)
        findings = parse_findings(output, agent_name="generalist", logger=logger)
        logger.info("Generalist agent finished", findings=len(findings))
        if not findings:
            logger.info("Generalist agent raw output", raw_output=output)
        return findings
    except BudgetExceededError:
        raise
    except Exception as e:
        logger.error("Generalist agent failed", error=str(e))
        return []
