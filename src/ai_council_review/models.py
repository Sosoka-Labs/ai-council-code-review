"""Pydantic models for AI Council Code Review."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    """Severity levels for review findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FileStatus(str, Enum):
    """GitHub file change status."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    RENAMED = "renamed"


class FileInfo(BaseModel):
    """Information about a file changed in a PR."""

    filename: str
    status: FileStatus
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None
    previous_filename: str | None = None
    sha: str | None = None
    raw_url: str | None = None


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


class PRMetadata(BaseModel):
    """Metadata about a pull request."""

    number: int
    title: str
    body: str | None = None
    state: str
    draft: bool = False
    author: str
    author_association: str
    base_ref: str
    base_sha: str
    head_ref: str
    head_sha: str
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    labels: list[str] = Field(default_factory=list)
    html_url: str | None = None
    diff_url: str | None = None
    commits: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_fork: bool = False


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
    costs: dict[str, Any] = Field(default_factory=dict)
    api_calls: int = 0
    files_read: list[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)
