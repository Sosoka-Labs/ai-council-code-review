"""Tests for ai_council_review.models.enums."""

from __future__ import annotations

from ai_council_review.models.enums import FileStatus, Severity


class TestSeverity:
    """Tests for Severity enum."""

    def test_severity_values(self) -> None:
        """Test severity enum values."""
        assert Severity.CRITICAL == "critical"
        assert Severity.HIGH == "high"
        assert Severity.MEDIUM == "medium"
        assert Severity.LOW == "low"
        assert Severity.INFO == "info"


class TestFileStatus:
    """Tests for FileStatus enum."""

    def test_file_status_enum(self) -> None:
        """Test FileStatus enum values."""
        assert FileStatus.ADDED == "added"
        assert FileStatus.REMOVED == "removed"
        assert FileStatus.MODIFIED == "modified"
        assert FileStatus.RENAMED == "renamed"

    def test_file_status_copied(self) -> None:
        assert FileStatus("copied") == FileStatus.COPIED

    def test_file_status_unchanged(self) -> None:
        assert FileStatus("unchanged") == FileStatus.UNCHANGED
