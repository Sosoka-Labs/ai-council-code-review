"""Agent implementations for AI Council Code Review."""

from __future__ import annotations

from ai_council_review.llm.agents.architecture import (
    build_architecture_executor,
    run_architecture_agent,
)
from ai_council_review.llm.agents.generalist import (
    build_generalist_executor,
    run_generalist_agent,
)
from ai_council_review.llm.agents.quality import (
    build_quality_executor,
    run_quality_agent,
)
from ai_council_review.llm.agents.router import (
    RouterOutput,
    build_router_chain,
    run_router_agent,
)
from ai_council_review.llm.agents.security import (
    build_security_executor,
    run_security_agent,
)
from ai_council_review.llm.agents.synthesis import (
    SynthesisOutput,
    build_synthesis_chain,
    run_synthesis_agent,
)

__all__ = [
    "RouterOutput",
    "SynthesisOutput",
    "build_architecture_executor",
    "build_generalist_executor",
    "build_quality_executor",
    "build_router_chain",
    "build_security_executor",
    "build_synthesis_chain",
    "run_architecture_agent",
    "run_generalist_agent",
    "run_quality_agent",
    "run_router_agent",
    "run_security_agent",
    "run_synthesis_agent",
]
