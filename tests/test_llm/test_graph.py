"""Tests for ai_council_review.graph main flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_council_review.config import CouncilConfig
from ai_council_review.llm.graph import (
    build_graph,
    ingest_node,
    post_node,
    router_node,
)
from ai_council_review.models import (
    FileInfo,
    Finding,
    PRMetadata,
    ReviewComment,
    ReviewState,
    Severity,
)


class TestIngestNode:
    """Tests for ingest_node."""

    def test_ingest_node(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mock PRIngestor and verify state is populated."""
        config = CouncilConfig()
        state = ReviewState()

        pr = PRMetadata(
            number=42,
            title="Test PR",
            state="open",
            author="alice",
            author_association="CONTRIBUTOR",
            base_ref="main",
            base_sha="base",
            head_ref="feat",
            head_sha="abc123",
        )
        files = [FileInfo(filename="src/main.py", status="modified")]

        with patch("ai_council_review.llm.graph.PRIngestor") as mock_ingestor:
            mock_instance = MagicMock()
            mock_instance.ingest.return_value = (pr, files, False, "")
            mock_instance.filter_files.return_value = files
            mock_ingestor.return_value = mock_instance

            monkeypatch.setenv("GITHUB_TOKEN", "token")
            monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")

            with patch("ai_council_review.llm.graph.GitHubClient") as mock_client:
                mock_client_instance = MagicMock()
                mock_client_instance.get_pr_files.return_value = [
                    {
                        "filename": "src/main.py",
                        "status": "modified",
                        "additions": 10,
                        "deletions": 2,
                        "changes": 12,
                        "patch": "@@ -1,5 +1,5 @@",
                    }
                ]
                mock_client.return_value = mock_client_instance

                result = ingest_node(state, config)

        assert result["pr_metadata"] is not None
        assert result["pr_metadata"].number == 42
        assert result["skipped"] is False
        assert len(result["changed_files"]) == 1
        assert result["changed_files"][0].filename == "src/main.py"

    def test_ingest_node_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify skipped state is set when PR is skipped."""
        config = CouncilConfig()
        state = ReviewState()

        pr = PRMetadata(
            number=1,
            title="Draft",
            state="open",
            draft=True,
            author="bob",
            author_association="CONTRIBUTOR",
            base_ref="main",
            base_sha="base",
            head_ref="feat",
            head_sha="head",
        )

        with patch("ai_council_review.llm.graph.PRIngestor") as mock_ingestor:
            mock_instance = MagicMock()
            mock_instance.ingest.return_value = (pr, [], True, "Draft PR")
            mock_ingestor.return_value = mock_instance

            monkeypatch.delenv("GITHUB_TOKEN", raising=False)

            result = ingest_node(state, config)

        assert result["skipped"] is True
        assert result["skip_reason"] == "Draft PR"
        assert result["pr_metadata"] is not None
        assert result["pr_metadata"].number == 1

    def test_ingest_node_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When GITHUB_EVENT_PATH is not set, ingest with None payload."""
        config = CouncilConfig()
        state = ReviewState()

        pr = PRMetadata(
            number=99,
            title="CLI",
            state="open",
            author="cli",
            author_association="CONTRIBUTOR",
            base_ref="main",
            base_sha="base",
            head_ref="feat",
            head_sha="sha",
        )

        with patch("ai_council_review.llm.graph.PRIngestor") as mock_ingestor:
            mock_instance = MagicMock()
            mock_instance.ingest.return_value = (pr, [], False, "")
            mock_ingestor.return_value = mock_instance

            monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
            monkeypatch.delenv("GITHUB_TOKEN", raising=False)

            result = ingest_node(state, config)

        assert result["skipped"] is False
        assert result["pr_metadata"].number == 99


class TestRouterNode:
    """Tests for router_node."""

    def test_router_node(self) -> None:
        """Mock run_router_agent and verify agents_needed is set."""
        config = CouncilConfig()
        state = ReviewState(
            pr_metadata=PRMetadata(
                number=42,
                title="Test",
                state="open",
                author="alice",
                author_association="CONTRIBUTOR",
                base_ref="main",
                base_sha="base",
                head_ref="feat",
                head_sha="head",
            ),
            changed_files=[FileInfo(filename="src/main.py", status="modified")],
        )

        mock_output = MagicMock()
        mock_output.agents_needed = ["security", "quality"]
        mock_output.review_depth = "deep"

        with patch("ai_council_review.llm.graph.run_router_agent") as mock_router:
            mock_router.return_value = mock_output

            result = router_node(state, config)

        assert result["agents_needed"] == ["security", "quality"]
        assert result["review_depth"] == "deep"
        mock_router.assert_called_once_with(state, config, registry=None)

    def test_router_node_skipped(self) -> None:
        """Skipped state returns empty updates."""
        config = CouncilConfig()
        state = ReviewState(skipped=True)

        with patch("ai_council_review.llm.graph.run_router_agent") as mock_router:
            result = router_node(state, config)

        assert result == {}
        mock_router.assert_not_called()

    def test_router_node_no_files(self) -> None:
        """No files returns empty updates."""
        config = CouncilConfig()
        state = ReviewState(
            pr_metadata=PRMetadata(
                number=42,
                title="Test",
                state="open",
                author="alice",
                author_association="CONTRIBUTOR",
                base_ref="main",
                base_sha="base",
                head_ref="feat",
                head_sha="head",
            ),
            changed_files=[],
        )

        with patch("ai_council_review.llm.graph.run_router_agent") as mock_router:
            result = router_node(state, config)

        assert result == {}
        mock_router.assert_not_called()


class TestPostNode:
    """Tests for post_node."""

    def test_post_node(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mock Publisher and GitHubClient, verify review is posted."""
        config = CouncilConfig()
        state = ReviewState(
            pr_metadata=PRMetadata(
                number=42,
                title="Test",
                state="open",
                author="alice",
                author_association="CONTRIBUTOR",
                base_ref="main",
                base_sha="base",
                head_ref="feat",
                head_sha="abc123",
            ),
            changed_files=[FileInfo(filename="src/main.py", status="modified")],
            agent_outputs={
                "security": [
                    Finding(
                        path="src/main.py",
                        position=3,
                        severity=Severity.HIGH,
                        category="security",
                        body="SQL injection",
                    )
                ]
            },
            summary="## AI Code Review\n\nFound issues.",
            verdict="comment",
        )

        monkeypatch.setenv("GITHUB_TOKEN", "token")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")

        with (
            patch("ai_council_review.llm.graph.GitHubClient"),
            patch("ai_council_review.llm.graph.Publisher") as mock_publisher,
        ):
            mock_publisher_instance = MagicMock()
            mock_publisher_instance.validate_comments.return_value = [
                ReviewComment(path="src/main.py", position=3, body="SQL injection")
            ]
            mock_publisher.return_value = mock_publisher_instance

            result = post_node(state, config)

        assert result["summary"] == "## AI Code Review\n\nFound issues."
        assert result["verdict"] == "comment"
        assert len(result["github_comments"]) == 1
        mock_publisher_instance.post_review.assert_called_once()
        call_kwargs = mock_publisher_instance.post_review.call_args.kwargs
        assert call_kwargs["pr_number"] == 42
        assert call_kwargs["commit_id"] == "abc123"
        assert call_kwargs["comments"] == [
            ReviewComment(path="src/main.py", position=3, body="SQL injection")
        ]

    def test_post_node_no_findings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify 'No issues found' summary is posted when there are no findings."""
        config = CouncilConfig()
        state = ReviewState(
            pr_metadata=PRMetadata(
                number=42,
                title="Test",
                state="open",
                author="alice",
                author_association="CONTRIBUTOR",
                base_ref="main",
                base_sha="base",
                head_ref="feat",
                head_sha="abc123",
            ),
            changed_files=[FileInfo(filename="src/main.py", status="modified")],
            agent_outputs={},
        )

        monkeypatch.setenv("GITHUB_TOKEN", "token")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")

        with (
            patch("ai_council_review.llm.graph.GitHubClient"),
            patch("ai_council_review.llm.graph.Publisher") as mock_publisher,
        ):
            mock_publisher_instance = MagicMock()
            mock_publisher.return_value = mock_publisher_instance

            result = post_node(state, config)

        assert "No issues found" in result["summary"]
        assert result["verdict"] == "approve"
        mock_publisher_instance.post_review.assert_called_once()
        call_kwargs = mock_publisher_instance.post_review.call_args.kwargs
        assert call_kwargs["pr_number"] == 42
        assert call_kwargs["comments"] == []

    def test_post_node_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Skipped state returns empty updates."""
        config = CouncilConfig()
        state = ReviewState(
            skipped=True,
            skip_reason="Draft PR",
        )

        monkeypatch.setenv("GITHUB_TOKEN", "token")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")

        with patch("ai_council_review.llm.graph.Publisher") as mock_publisher:
            result = post_node(state, config)

        assert result == {}
        mock_publisher.assert_not_called()

    def test_post_node_no_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing token returns empty updates."""
        config = CouncilConfig()
        state = ReviewState(
            pr_metadata=PRMetadata(
                number=42,
                title="Test",
                state="open",
                author="alice",
                author_association="CONTRIBUTOR",
                base_ref="main",
                base_sha="base",
                head_ref="feat",
                head_sha="abc123",
            ),
        )

        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        with patch("ai_council_review.llm.graph.Publisher") as mock_publisher:
            result = post_node(state, config)

        assert result == {}
        mock_publisher.assert_not_called()

    def test_post_node_builds_summary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no summary is set, post_node builds one from findings."""
        config = CouncilConfig()
        state = ReviewState(
            pr_metadata=PRMetadata(
                number=42,
                title="Test",
                state="open",
                author="alice",
                author_association="CONTRIBUTOR",
                base_ref="main",
                base_sha="base",
                head_ref="feat",
                head_sha="abc123",
            ),
            changed_files=[FileInfo(filename="src/main.py", status="modified")],
            agent_outputs={
                "security": [
                    Finding(
                        path="src/main.py",
                        position=3,
                        severity=Severity.CRITICAL,
                        category="security",
                        body="RCE",
                    ),
                    Finding(
                        path="src/main.py",
                        position=5,
                        severity=Severity.MEDIUM,
                        category="quality",
                        body="Long function",
                    ),
                ]
            },
        )

        monkeypatch.setenv("GITHUB_TOKEN", "token")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")

        with (
            patch("ai_council_review.llm.graph.GitHubClient"),
            patch("ai_council_review.llm.graph.Publisher") as mock_publisher,
        ):
            mock_publisher_instance = MagicMock()
            mock_publisher.return_value = mock_publisher_instance

            result = post_node(state, config)

        assert result["summary"] is not None
        assert "Critical: 1" in result["summary"]
        assert "Medium: 1" in result["summary"]
        assert "Total findings:** 2" in result["summary"]
        assert result["verdict"] == "comment"


class TestBuildGraph:
    """Tests for build_graph."""

    def test_build_graph(self) -> None:
        """Verify graph compiles successfully."""
        config = CouncilConfig()
        graph = build_graph(config)

        assert graph is not None
