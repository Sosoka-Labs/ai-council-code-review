"""Domain enums for AI Council Code Review."""

from __future__ import annotations

from enum import Enum


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
    COPIED = "copied"
    UNCHANGED = "unchanged"
