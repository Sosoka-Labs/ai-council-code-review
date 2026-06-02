"""Tests for ai_council_review.publisher."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ai_council_review.github_client import GitHubClient
from ai_council_review.models import FileInfo, ReviewComment
from ai_council_review.publisher import Publisher


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock GitHubClient."""
    client = MagicMock(spec=GitHubClient)
    client.post_review.return_value = {"id": 123}
    client.post_comment.return_value = {"id": 456}
    return client


class TestPublisher:
    """Tests for Publisher."""

    def test_post_review_with_comments(self, mock_client: MagicMock) -> None:
        """Test posting a review with comments."""
        publisher = Publisher(mock_client)
        comments = [
            ReviewComment(path="src/main.py", position=3, body="Add type hints."),
            ReviewComment(path="src/test.py", position=7, body="Missing test case."),
        ]

        publisher.post_review(
            pr_number=42,
            summary="## Review\n\nGood work!",
            comments=comments,
            commit_id="abc123",
        )

        mock_client.post_review.assert_called_once()
        call_args = mock_client.post_review.call_args
        assert call_args.kwargs["number"] == 42
        assert call_args.kwargs["body"] == "## Review\n\nGood work!"
        assert call_args.kwargs["event"] == "COMMENT"
        assert call_args.kwargs["commit_id"] == "abc123"
        assert len(call_args.kwargs["comments"]) == 2

    def test_post_review_without_comments(self, mock_client: MagicMock) -> None:
        """Test posting a review without inline comments."""
        publisher = Publisher(mock_client)
        publisher.post_review(
            pr_number=42,
            summary="LGTM",
            comments=[],
            commit_id="abc123",
        )

        mock_client.post_review.assert_called_once()
        call_args = mock_client.post_review.call_args
        assert call_args.kwargs["comments"] == []

    def test_post_comment(self, mock_client: MagicMock) -> None:
        """Test posting a general PR comment."""
        publisher = Publisher(mock_client)
        publisher.post_comment(42, "Hello from AI")
        mock_client.post_comment.assert_called_once_with(42, "Hello from AI")

    def test_validate_comments(self, mock_client: MagicMock) -> None:
        """Test that comments for unchanged files are dropped."""
        publisher = Publisher(mock_client)
        changed_files = [FileInfo(filename="src/main.py", status="modified")]
        comments = [
            ReviewComment(path="src/main.py", position=1, body="OK"),
            ReviewComment(path="src/other.py", position=1, body="Not changed"),
        ]

        valid = publisher.validate_comments(comments, changed_files)
        assert len(valid) == 1
        assert valid[0].path == "src/main.py"
