"""PR-related models for AI Council Code Review."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ai_council_review.models.enums import FileStatus


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
