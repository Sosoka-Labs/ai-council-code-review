"""Router agent — decides which specialist agents to run."""

from __future__ import annotations

from typing import Any, cast

import structlog
from pydantic import BaseModel

from ai_council_review.config import AgentConfig, CouncilConfig
from ai_council_review.exceptions import BudgetExceededError
from ai_council_review.llm.agents.registry import SPECIALIST_AGENTS
from ai_council_review.llm.prompts.loader import load_prompt
from ai_council_review.llm.providers.factory import LLMProviderFactory
from ai_council_review.models import ReviewState
from ai_council_review.skills import Skill, apply_skill_catalog
from ai_council_review.skills.registry import SkillRegistry
from ai_council_review.skills.resolution import (
    SkillMode,
    bind_chain_metadata,
    resolve_skills_for_agent,
)

logger = structlog.get_logger()


class RouterOutput(BaseModel):
    """Structured output from the router agent."""

    agents_needed: list[str]
    review_depth: str
    reasoning: str


_PR_TITLE_MAX_CHARS = 500
_PR_BODY_MAX_CHARS = 2000

# Default fallback list: all enabled specialists, derived from the registry.
_DEFAULT_AGENTS: list[str] = [spec.name for spec in SPECIALIST_AGENTS if spec.enabled_by_default]


def _build_router_variables(state: ReviewState, config: CouncilConfig) -> dict[str, Any]:
    """Build prompt variables for the router agent.

    Applies safety limits on untrusted PR content (title, body, diff) before
    injecting into LLM prompts.  Also populates ``{{ agent_catalog }}`` from the
    registry so the router prompt auto-adapts when agents are added.

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
    pr_body = ((pr.body or "")[:_PR_BODY_MAX_CHARS]) if pr else ""
    pr_number = pr.number if pr else 0
    repo = pr.html_url if pr else ""

    # Build agent catalog from registry for Jinja2 slot injection.
    catalog_lines: list[str] = []
    for spec in SPECIALIST_AGENTS:
        catalog_lines.append(f"- **{spec.name}** — {spec.router_hint}")
    agent_catalog = "\n".join(catalog_lines)

    return {
        "repo": repo,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "pr_body": pr_body,
        "changed_files": file_list,
        "diff": diff_text,
        "agent_catalog": agent_catalog,
    }


def build_router_chain(config: CouncilConfig, registry: SkillRegistry | None = None) -> Any:
    """Build an LCEL chain for the router agent.

    Args:
        config: Global council configuration.
        registry: Optional skill registry. When provided, a descriptions-only
            catalog is appended to the router's system prompt so it can factor
            domain-skill coverage into its routing decision.

    Returns:
        Runnable chain that outputs RouterOutput.
    """
    agent_config = config.agents.get("router", AgentConfig(temperature=0.1, max_tokens=2000))

    llm = LLMProviderFactory.from_config(agent_config, config.providers)
    prompt = load_prompt("router")
    skills: list[Skill] = []
    skill_mode: SkillMode = "none"
    if registry is not None:
        skills = resolve_skills_for_agent("router", config, registry)
        if skills:
            prompt = apply_skill_catalog(prompt, skills)
            skill_mode = "catalog"
    chain = prompt | llm.with_structured_output(RouterOutput)
    return bind_chain_metadata(chain, "router", skills, skill_mode)


def run_router_agent(
    state: ReviewState,
    config: CouncilConfig,
    callbacks: list[Any] | None = None,
    registry: SkillRegistry | None = None,
) -> RouterOutput:
    """Run the router agent and determine which agents are needed.

    Args:
        state: Current review state.
        config: Council configuration.
        callbacks: Optional LangChain callbacks (e.g., CostCallbackHandler).
        registry: Optional skill registry for catalog injection.

    Returns:
        RouterOutput with agents_needed, review_depth, and reasoning.
    """
    logger.info("Router agent starting")
    chain = build_router_chain(config, registry=registry)

    try:
        variables = _build_router_variables(state, config)
        run_config = {"callbacks": callbacks} if callbacks else None
        result = chain.invoke(variables, config=run_config)
        router_output = cast(RouterOutput, result)
        logger.info(
            "Router complete",
            agents=router_output.agents_needed,
            depth=router_output.review_depth,
        )
        return router_output
    except BudgetExceededError:
        raise  # Budget exceeded during routing — do not start more agents
    except Exception as e:
        logger.error("Router failed", error=str(e))
        return RouterOutput(
            agents_needed=_DEFAULT_AGENTS,
            review_depth="standard",
            reasoning=f"Router failed ({e}), defaulting to all agents",
        )
