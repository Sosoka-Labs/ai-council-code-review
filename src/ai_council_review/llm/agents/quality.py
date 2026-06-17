"""Quality agent shim — delegates to the parameterized specialist runner.

This module exists for backwards compatibility.  New code should import
``build_specialist_chain`` / ``run_specialist_agent`` from ``specialist.py``
directly and pass the registry's ``AgentSpec`` for the desired agent.
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import Runnable

from ai_council_review.config import CouncilConfig
from ai_council_review.llm.agents.registry import SPECIALIST_BY_NAME
from ai_council_review.llm.agents.specialist import (
    build_specialist_chain,
    run_specialist_agent,
)
from ai_council_review.models import Finding, ReviewState
from ai_council_review.skills.registry import SkillRegistry

_SPEC = SPECIALIST_BY_NAME["quality"]


def build_quality_chain(
    config: CouncilConfig,
    registry: SkillRegistry | None = None,
) -> Runnable[dict[str, Any], Any]:
    """Build a simple LLM chain for the quality agent.

    Args:
        config: Global council configuration.
        registry: Optional skill registry.

    Returns:
        Configured Runnable chain.
    """
    return build_specialist_chain(_SPEC, config, registry=registry)


def run_quality_agent(
    state: ReviewState,
    config: CouncilConfig,
    callbacks: list[Any] | None = None,
    registry: SkillRegistry | None = None,
) -> list[Finding]:
    """Run the quality agent and return findings.

    Args:
        state: Current review state.
        config: Council configuration.
        callbacks: Optional LangChain callbacks.
        registry: Optional skill registry.

    Returns:
        List of findings.
    """
    return run_specialist_agent(_SPEC, state, config, callbacks=callbacks, registry=registry)
