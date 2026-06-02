"""Tests for ai_council_review.models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_council_review.models import (
    FileInfo,
    FileStatus,
    Finding,
    PRMetadata,
    ReviewComment,
    ReviewState,
    Severity,
)


class TestFileInfo:
    """Tests for FileInfo model."""

    def test_create_file_info(self) -> None:
        """Test creating a FileInfo instance."""
        file = FileInfo(
            filename="src/main.py",
            status=FileStatus.MODIFIED,
            additions=10,
            deletions=2,
            changes=12,
        )
        assert file.filename == "src/main.py"
        assert file.status == FileStatus.MODIFIED
        assert file.additions == 10
        assert file.deletions == 2
        assert file.patch is None

    def test_file_status_enum(self) -> None:
        """Test FileStatus enum values."""
        assert FileStatus.ADDED == "added"
        assert FileStatus.REMOVED == "removed"
        assert FileStatus.MODIFIED == "modified"
        assert FileStatus.RENAMED == "renamed"


class TestReviewComment:
    """Tests for ReviewComment model."""

    def test_create_comment(self) -> None:
        """Test creating a ReviewComment."""
        comment = ReviewComment(
            path="src/main.py",
            position=5,
            body="Consider adding type hints.",
        )
        assert comment.path == "src/main.py"
        assert comment.position == 5
        assert comment.side == "RIGHT"


class TestFinding:
    """Tests for Finding model."""

    def test_create_finding(self) -> None:
        """Test creating a Finding."""
        finding = Finding(
            path="src/main.py",
            position=10,
            severity=Severity.HIGH,
            category="security",
            body="Potential SQL injection.",
            confidence=0.95,
        )
        assert finding.path == "src/main.py"
        assert finding.severity == Severity.HIGH
        assert finding.confidence == 0.95

    def test_invalid_confidence(self) -> None:
        """Test that confidence outside [0, 1] raises ValidationError."""
        with pytest.raises(ValidationError):
            Finding(
                path="src/main.py",
                severity=Severity.LOW,
                category="quality",
                body="Test.",
                confidence=1.5,
            )


class TestPRMetadata:
    """Tests for PRMetadata model."""

    def test_create_pr_metadata(self) -> None:
        """Test creating PRMetadata."""
        pr = PRMetadata(
            number=42,
            title="Add feature X",
            state="open",
            draft=False,
            author="octocat",
            author_association="OWNER",
            base_ref="main",
            base_sha="abc123",
            head_ref="feature/x",
            head_sha="def456",
            additions=100,
            deletions=50,
            changed_files=5,
            labels=["enhancement"],
            is_fork=False,
        )
        assert pr.number == 42
        assert pr.title == "Add feature X"
        assert pr.is_fork is False


class TestReviewState:
    """Tests for ReviewState model."""

    def test_create_review_state(self) -> None:
        """Test creating a ReviewState."""
        state = ReviewState(
            pr_metadata=PRMetadata(
                number=1,
                title="Test",
                state="open",
                author="test",
                author_association="OWNER",
                base_ref="main",
                base_sha="abc",
                head_ref="feat",
                head_sha="def",
            ),
        )
        assert state.pr_metadata is not None
        assert state.pr_metadata.number == 1
        assert state.verdict == "comment"
        assert state.skipped is False

    def test_empty_state(self) -> None:
        """Test creating an empty ReviewState."""
        state = ReviewState()
        assert state.pr_metadata is None
        assert state.changed_files == []
        assert state.agent_outputs == {}
        assert state.github_comments == []
