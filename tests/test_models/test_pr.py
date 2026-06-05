"""Tests for ai_council_review.models.pr."""

from __future__ import annotations

from ai_council_review.models.enums import FileStatus
from ai_council_review.models.pr import FileInfo, PRMetadata


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
