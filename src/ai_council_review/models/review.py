"""Review artifact models for AI Council Code Review."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ai_council_review.models.enums import Severity


class ReviewComment(BaseModel):
    """An inline review comment to post on a PR."""

    path: str
    position: int
    body: str
    side: str = "RIGHT"
    line: int | None = None
    start_line: int | None = None
    start_side: str | None = None


class Finding(BaseModel):
    """A single finding from an agent review."""

    path: str
    position: int | None = None
    severity: Severity
    category: str
    body: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    line: int | None = None
    agent: str | None = None


class CostRecord(BaseModel):
    """Cost record for a single LLM call."""

    agent: str
    model: str
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    actual_input_tokens: int | None = None
    actual_output_tokens: int | None = None
    estimated_cost_usd: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
