"""Tests for ai_council_review.models.review."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_council_review.models.enums import Severity
from ai_council_review.models.review import Finding, ReviewComment


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
