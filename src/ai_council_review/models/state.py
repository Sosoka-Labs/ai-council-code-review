"""LangGraph state model for AI Council Code Review."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ai_council_review.models.pr import FileInfo, PRMetadata
from ai_council_review.models.review import CostRecord, Finding, ReviewComment


class ReviewState(BaseModel):
    """The state object passed through the LangGraph review workflow."""

    pr_metadata: PRMetadata | None = None
    changed_files: list[FileInfo] = Field(default_factory=list)
    agent_outputs: dict[str, list[Finding]] = Field(default_factory=dict)
    synthesis: str | None = None
    github_comments: list[ReviewComment] = Field(default_factory=list)
    summary: str | None = None
    verdict: str = "comment"
    skipped: bool = False
    skip_reason: str | None = None
    costs: list[CostRecord] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    api_calls: int = 0
    files_read: list[str] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)
