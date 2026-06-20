"""Tests for ai_council_review.github.client retry behavior."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from ai_council_review.exceptions import RateLimitError
from ai_council_review.github.client import _MAX_RATE_LIMIT_WAIT_SECONDS, GitHubClient


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


class TestRateLimitCap:
    """Tests for the _MAX_RATE_LIMIT_WAIT_SECONDS fast-fail behaviour."""

    def _create_client(self) -> GitHubClient:
        """Create a GitHubClient with Github constructor mocked."""
        with patch("ai_council_review.github.client.Github") as mock_github:
            mock_github.return_value.get_repo.return_value = MagicMock()
            return GitHubClient("token", "owner/repo")

    def _make_rate_limit_response(self, reset_offset_seconds: int) -> MagicMock:
        """Build a 403 rate-limit response whose reset is *offset* seconds away."""
        future_reset = int(time.time()) + reset_offset_seconds
        response = MagicMock()
        response.status_code = 403
        response.text = "API rate limit exceeded"
        response.headers = {"X-RateLimit-Reset": str(future_reset)}
        response.raise_for_status = MagicMock()
        return response

    def test_far_future_reset_raises_immediately_without_sleeping(self) -> None:
        """A reset far in the future must raise RateLimitError without sleeping.

        This is the fix for the pilot incident where a ~59-minute wait caused CI
        to hang until the 15-minute job timeout killed it.
        """
        client = self._create_client()
        # Use a wait that comfortably exceeds the cap.
        response = self._make_rate_limit_response(
            reset_offset_seconds=_MAX_RATE_LIMIT_WAIT_SECONDS + 300
        )

        with (
            patch(
                "ai_council_review.github.client.requests.request",
                return_value=response,
            ),
            patch("ai_council_review.github.client.time.sleep") as mock_sleep,
            pytest.raises(RateLimitError),
        ):
            client._request("GET", "https://api.github.com/test")

        # The critical assertion: we must NOT have slept a long time.
        mock_sleep.assert_not_called()

    def test_within_cap_reset_sleeps_and_retries(self) -> None:
        """A reset within the cap sleeps and retries (normal backoff path)."""
        client = self._create_client()
        # Pin the client's clock so the computed wait is deterministic:
        # wait = reset_time - now + 5 = (now + 5) - now + 5 = 10.
        fixed_now = 1_000_000
        rate_limit_response = MagicMock(
            status_code=403,
            text="API rate limit exceeded",
            headers={"X-RateLimit-Reset": str(fixed_now + 5)},
            raise_for_status=MagicMock(),
        )
        success_response = MagicMock(
            status_code=200,
            text="OK",
            headers={"X-RateLimit-Remaining": "50"},
            raise_for_status=MagicMock(),
        )

        with (
            patch(
                "ai_council_review.github.client.requests.request",
                side_effect=[rate_limit_response, success_response],
            ) as mock_request,
            patch("ai_council_review.github.client.time.time", return_value=fixed_now),
            patch("ai_council_review.github.client.time.sleep") as mock_sleep,
        ):
            result = client._request("GET", "https://api.github.com/test")

        # Request was retried after the short sleep.
        assert mock_request.call_count == 2
        assert result.status_code == 200
        # sleep was called with the exact computed wait (within the cap).
        assert mock_sleep.call_count == 1
        assert mock_sleep.call_args.args[0] == 10
