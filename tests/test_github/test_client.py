"""Tests for ai_council_review.github.client main methods."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest

from ai_council_review.github.client import GitHubClient


@pytest.fixture
def client() -> GitHubClient:
    """Create a GitHubClient with PyGithub constructor mocked."""
    with patch("ai_council_review.github.client.Github") as mock_github:
        mock_github.return_value.get_repo.return_value = MagicMock()
        yield GitHubClient("test-token", "owner/repo")


class TestGetPullRequest:
    """Tests for get_pull_request."""

    def test_get_pull_request(self, client: GitHubClient) -> None:
        """Mock Github.get_repo().get_pull() and verify return value."""
        mock_pr = MagicMock()
        mock_pr.number = 42
        client.repo.get_pull = MagicMock(return_value=mock_pr)

        result = client.get_pull_request(42)

        assert result is mock_pr
        client.repo.get_pull.assert_called_once_with(42)
        assert client.api_calls == 1


class TestGetPrFiles:
    """Tests for get_pr_files."""

    def test_get_pr_files(self, client: GitHubClient) -> None:
        """Mock requests.request for files API with pagination."""
        page1 = MagicMock()
        page1.status_code = 200
        page1.json.return_value = [
            {"filename": "a.py", "status": "modified"},
            {"filename": "b.py", "status": "added"},
        ]
        page1.headers = {"X-RateLimit-Remaining": "100"}
        page1.links = {
            "next": {"url": "https://api.github.com/repos/owner/repo/pulls/42/files?page=2"}
        }
        page1.raise_for_status = MagicMock()

        page2 = MagicMock()
        page2.status_code = 200
        page2.json.return_value = [{"filename": "c.py", "status": "removed"}]
        page2.headers = {"X-RateLimit-Remaining": "99"}
        page2.links = {}
        page2.raise_for_status = MagicMock()

        with (
            patch(
                "ai_council_review.github.client.requests.request", side_effect=[page1, page2]
            ) as mock_request,
            patch("ai_council_review.github.client.time.sleep"),
        ):
            files = client.get_pr_files(42)

        assert len(files) == 3
        assert files[0]["filename"] == "a.py"
        assert files[1]["filename"] == "b.py"
        assert files[2]["filename"] == "c.py"
        assert mock_request.call_count == 2

    def test_get_pr_files_empty(self, client: GitHubClient) -> None:
        """Mock requests.request returning empty list."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = []
        response.headers = {"X-RateLimit-Remaining": "100"}
        response.links = {}
        response.raise_for_status = MagicMock()

        with (
            patch(
                "ai_council_review.github.client.requests.request", return_value=response
            ) as mock_request,
            patch("ai_council_review.github.client.time.sleep"),
        ):
            files = client.get_pr_files(42)

        assert files == []
        assert mock_request.call_count == 1


class TestGetPrDiff:
    """Tests for get_pr_diff."""

    def test_get_pr_diff(self, client: GitHubClient) -> None:
        """Mock requests.request for diff API."""
        diff_text = "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py"
        response = MagicMock()
        response.status_code = 200
        response.text = diff_text
        response.headers = {"X-RateLimit-Remaining": "100"}
        response.raise_for_status = MagicMock()

        with (
            patch(
                "ai_council_review.github.client.requests.request", return_value=response
            ) as mock_request,
            patch("ai_council_review.github.client.time.sleep"),
        ):
            result = client.get_pr_diff(42)

        assert result == diff_text
        assert mock_request.call_count == 1


class TestGetFileContents:
    """Tests for get_file_contents."""

    def test_get_file_contents(self, client: GitHubClient) -> None:
        """Mock requests.request for contents API with base64 response."""
        content = "Hello, world!"
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"content": encoded}
        response.headers = {"X-RateLimit-Remaining": "100"}
        response.raise_for_status = MagicMock()

        with (
            patch(
                "ai_council_review.github.client.requests.request", return_value=response
            ) as mock_request,
            patch("ai_council_review.github.client.time.sleep"),
        ):
            result = client.get_file_contents("src/main.py", "main")

        assert result == content
        assert mock_request.call_count == 1
        call_kwargs = mock_request.call_args.kwargs
        assert call_kwargs["params"]["ref"] == "main"

    def test_get_file_contents_not_found(self, client: GitHubClient) -> None:
        """Returns None on 404 without raising."""
        import requests

        response = MagicMock()
        response.status_code = 404
        response.text = "Not Found"
        response.headers = {}
        response.raise_for_status.side_effect = requests.HTTPError("404")

        with (
            patch(
                "ai_council_review.github.client.requests.request", return_value=response
            ) as mock_request,
            patch("ai_council_review.github.client.time.sleep"),
        ):
            result = client.get_file_contents("src/missing.py", "main")

        assert result is None
        assert mock_request.call_count == 3  # retries

    def test_conservative_mode_skips_file_contents(self, client: GitHubClient) -> None:
        """When conservative_mode=True, get_file_contents returns None without API call."""
        client.conservative_mode = True

        with patch("ai_council_review.github.client.requests.request") as mock_request:
            result = client.get_file_contents("src/main.py", "main")

        assert result is None
        assert mock_request.call_count == 0


class TestPostReview:
    """Tests for post_review."""

    def test_post_review(self, client: GitHubClient) -> None:
        """Mock requests.request for review API."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"id": 123, "state": "COMMENT"}
        response.headers = {"X-RateLimit-Remaining": "99"}
        response.raise_for_status = MagicMock()

        with (
            patch(
                "ai_council_review.github.client.requests.request", return_value=response
            ) as mock_request,
            patch("ai_council_review.github.client.time.sleep"),
        ):
            result = client.post_review(
                number=42,
                body="Great PR!",
                comments=[{"path": "a.py", "position": 1, "body": "Nice"}],
                event="COMMENT",
                commit_id="abc123",
            )

        assert result["id"] == 123
        assert mock_request.call_count == 1
        call_kwargs = mock_request.call_args.kwargs
        payload = call_kwargs["json"]
        assert payload["body"] == "Great PR!"
        assert payload["event"] == "COMMENT"
        assert payload["comments"] == [{"path": "a.py", "position": 1, "body": "Nice"}]
        assert payload["commit_id"] == "abc123"

    def test_post_review_no_comments(self, client: GitHubClient) -> None:
        """Mock requests.request for review without comments."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"id": 124}
        response.headers = {"X-RateLimit-Remaining": "98"}
        response.raise_for_status = MagicMock()

        with (
            patch(
                "ai_council_review.github.client.requests.request", return_value=response
            ) as mock_request,
            patch("ai_council_review.github.client.time.sleep"),
        ):
            result = client.post_review(
                number=42,
                body="LGTM",
                comments=None,
                event="APPROVE",
            )

        assert result["id"] == 124
        assert mock_request.call_count == 1
        call_kwargs = mock_request.call_args.kwargs
        payload = call_kwargs["json"]
        assert payload["body"] == "LGTM"
        assert payload["event"] == "APPROVE"
        assert "comments" not in payload
        assert "commit_id" not in payload


class TestPostComment:
    """Tests for post_comment."""

    def test_post_comment(self, client: GitHubClient) -> None:
        """Mock requests.request for comment API."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"id": 456}
        response.headers = {"X-RateLimit-Remaining": "97"}
        response.raise_for_status = MagicMock()

        with (
            patch(
                "ai_council_review.github.client.requests.request", return_value=response
            ) as mock_request,
            patch("ai_council_review.github.client.time.sleep"),
        ):
            result = client.post_comment(42, "Hello from AI")

        assert result["id"] == 456
        assert mock_request.call_count == 1
        call_kwargs = mock_request.call_args.kwargs
        payload = call_kwargs["json"]
        assert payload["body"] == "Hello from AI"
