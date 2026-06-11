"""Security agent — focused on vulnerabilities and security issues."""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.runnables import Runnable

from ai_council_review.config import AgentConfig, CouncilConfig
from ai_council_review.exceptions import BudgetExceededError
from ai_council_review.llm.agents.output_models import FindingList
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


def build_security_chain(
    config: CouncilConfig,
    registry: SkillRegistry | None = None,
) -> Runnable[dict[str, Any], Any]:
    """Build a simple LLM chain for the security agent.

    Args:
        config: Global council configuration.
        registry: Optional skill registry. When provided, resolved skill bodies
            are appended to the system prompt.

    Returns:
        Configured Runnable chain.
    """
    agent_config = config.agents.get("security", AgentConfig())
    llm = LLMProviderFactory.from_config(agent_config, config.providers)
    prompt = load_prompt("security")
    skills: list[Skill] = []
    skill_mode: SkillMode = "none"
    if registry is not None:
        skills = resolve_skills_for_agent("security", config, registry)
        if skills:
            prompt = apply_skills(prompt, skills)
            skill_mode = "bodies"
    chain = prompt | llm.with_structured_output(FindingList)
    return bind_chain_metadata(chain, "security", skills, skill_mode)


def run_security_agent(
    state: ReviewState,
    config: CouncilConfig,
    callbacks: list[Any] | None = None,
    registry: SkillRegistry | None = None,
) -> list[Finding]:
    """Run the security agent and return findings.

    Args:
        state: Current review state.
        config: Council configuration.
        callbacks: Optional LangChain callbacks (e.g., CostCallbackHandler).
        registry: Optional skill registry for skill injection.

    Returns:
        List of findings.
    """
    logger.info("Security agent starting")
    chain = build_security_chain(config, registry=registry)

    try:
        variables = _build_agent_variables(state)
        run_config = {"callbacks": callbacks} if callbacks else None
        result = chain.invoke(variables, config=run_config)  # type: ignore[arg-type]
        findings = result.findings if isinstance(result, FindingList) else []
        for f in findings:
            f.agent = "security"
        logger.info("Security agent finished", findings=len(findings))
        return findings
    except BudgetExceededError:
        raise
    except Exception as e:
        logger.error("Security agent failed", error=str(e))
        return []
