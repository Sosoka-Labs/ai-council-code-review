"""Tests for ai_council_review.models.state."""

from __future__ import annotations

from ai_council_review.models.pr import PRMetadata
from ai_council_review.models.state import ReviewState


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
