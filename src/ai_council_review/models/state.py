"""LangGraph state model for AI Council Code Review."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from ai_council_review.models.pr import FileInfo, PRMetadata
from ai_council_review.models.review import CostRecord, Finding, ReviewComment


def _default_agents_needed() -> list[str]:
    """Return the default agent list derived from the specialist registry.

    Using a factory function avoids a module-level import cycle while still
    keeping the default in sync with ``SPECIALIST_AGENTS`` at runtime.
    """
    from ai_council_review.llm.agents.registry import SPECIALIST_AGENTS

    return [spec.name for spec in SPECIALIST_AGENTS if spec.enabled_by_default]


def _merge_agent_outputs(
    left: dict[str, list[Finding]],
    right: dict[str, list[Finding]],
) -> dict[str, list[Finding]]:
    """Merge agent outputs from parallel agent nodes.

    LangGraph v0.2 requires an Annotated reducer for keys that
    receive concurrent updates from parallel nodes.
    """
    merged = left.copy()
    for key, value in right.items():
        merged[key] = value
    return merged


class ReviewState(BaseModel):
    """The state object passed through the LangGraph review workflow."""

    pr_metadata: PRMetadata | None = None
    changed_files: list[FileInfo] = Field(default_factory=list)
    agent_outputs: Annotated[dict[str, list[Finding]], _merge_agent_outputs] = Field(
        default_factory=dict
    )
    synthesis: str | None = None
    github_comments: list[ReviewComment] = Field(default_factory=list)
    summary: str | None = None
    agents_needed: list[str] = Field(default_factory=_default_agents_needed)
    review_depth: str = "standard"
    verdict: str = "comment"
    skipped: bool = False
    skip_reason: str | None = None
    costs: list[CostRecord] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    api_calls: int = 0
    files_read: list[str] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)
