"""Tests for ai_council_review.github.client retry behavior."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from ai_council_review.github.client import GitHubClient


class TestGitHubClientRetry:
    """Tests for GitHub client retry logic."""

    def _create_client(self) -> GitHubClient:
        """Create a GitHubClient with Github constructor mocked."""
        with patch("ai_council_review.github.client.Github") as mock_github:
            mock_github.return_value.get_repo.return_value = MagicMock()
            return GitHubClient("token", "owner/repo")

    def test_retry_with_jitter(self) -> None:
        """Mock requests to fail twice then succeed, verify retry."""
        client = self._create_client()

        responses = [
            MagicMock(
                status_code=500,
                text="Server Error",
                headers={},
                raise_for_status=MagicMock(side_effect=requests.HTTPError("500")),
            ),
            MagicMock(
                status_code=500,
                text="Server Error",
                headers={},
                raise_for_status=MagicMock(side_effect=requests.HTTPError("500")),
            ),
            MagicMock(
                status_code=200,
                text="OK",
                headers={"X-RateLimit-Remaining": "100"},
                raise_for_status=MagicMock(),
            ),
        ]

        with (
            patch(
                "ai_council_review.github.client.requests.request",
                side_effect=responses,
            ) as mock_request,
            patch("ai_council_review.github.client.time.sleep") as mock_sleep,
            patch(
                "ai_council_review.github.client.random.uniform",
                return_value=0.5,
            ),
        ):
            result = client._request("GET", "https://api.github.com/test")

        assert result.status_code == 200
        assert mock_request.call_count == 3
        assert mock_sleep.call_count == 2

        # Verify jittered delays
        mock_sleep.assert_any_call(1.5)  # 2^0 + 0.5
        mock_sleep.assert_any_call(2.5)  # 2^1 + 0.5

    def test_rate_limit_conservative_mode(self) -> None:
        """Verify conservative_mode is set when rate limit is low."""
        client = self._create_client()
        client.conservative_mode_threshold = 50

        response = MagicMock(
            status_code=200,
            text="OK",
            headers={"X-RateLimit-Remaining": "10"},
            raise_for_status=MagicMock(),
        )

        with (
            patch(
                "ai_council_review.github.client.requests.request",
                return_value=response,
            ),
            patch("ai_council_review.github.client.time.sleep"),
        ):
            client._request("GET", "https://api.github.com/test")

        assert client.conservative_mode is True
