"""Structured output models for specialist agents."""

from __future__ import annotations

from pydantic import BaseModel

from ai_council_review.models.review import Finding


class FindingList(BaseModel):
    """Wrapper model for structured LLM output from specialist agents."""

    findings: list[Finding]
