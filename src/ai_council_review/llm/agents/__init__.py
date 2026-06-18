"""Agent implementations for AI Council Code Review."""

from __future__ import annotations

from ai_council_review.llm.agents.architecture import (
    build_architecture_chain,
    run_architecture_agent,
)
from ai_council_review.llm.agents.generalist import (
    build_generalist_executor,
    run_generalist_agent,
)
from ai_council_review.llm.agents.quality import (
    build_quality_chain,
    run_quality_agent,
)
from ai_council_review.llm.agents.registry import (
    SPECIALIST_AGENTS,
    SPECIALIST_BY_NAME,
    AgentSpec,
)
from ai_council_review.llm.agents.router import (
    RouterOutput,
    build_router_chain,
    run_router_agent,
)
from ai_council_review.llm.agents.security import (
    build_security_chain,
    run_security_agent,
)
from ai_council_review.llm.agents.specialist import (
    build_specialist_chain,
    run_specialist_agent,
)
from ai_council_review.llm.agents.synthesis import (
    SynthesisOutput,
    build_synthesis_chain,
    run_synthesis_agent,
)

__all__ = [
    # Registry
    "AgentSpec",
    "SPECIALIST_AGENTS",
    "SPECIALIST_BY_NAME",
    # Router
    "RouterOutput",
    "build_router_chain",
    "run_router_agent",
    # Generic specialist runner
    "build_specialist_chain",
    "run_specialist_agent",
    # Shim functions for backwards compatibility
    "build_architecture_chain",
    "build_quality_chain",
    "build_security_chain",
    "run_architecture_agent",
    "run_quality_agent",
    "run_security_agent",
    # Generalist (kept for backwards compatibility)
    "build_generalist_executor",
    "run_generalist_agent",
    # Synthesis
    "SynthesisOutput",
    "build_synthesis_chain",
    "run_synthesis_agent",
]
