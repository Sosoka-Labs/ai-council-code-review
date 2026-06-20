"""GitHub API client wrapper with retry and rate limit tracking."""

from __future__ import annotations

import random
import time
from typing import Any, cast

import requests
import structlog
from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository

from ai_council_review.exceptions import GitHubAPIError, RateLimitError

logger = structlog.get_logger()

# Maximum number of seconds we are willing to sleep while waiting for a rate-
# limit reset.  If the computed wait exceeds this cap we raise RateLimitError
# immediately rather than hanging the process (the previous unbounded behaviour
# caused a ~14-minute CI timeout on PR #140).
_MAX_RATE_LIMIT_WAIT_SECONDS: int = 30


class GitHubClient:
    """Wrapper around PyGithub and raw REST calls with retry logic."""

    def __init__(
        self,
        token: str,
        repo_name: str,
        conservative_mode_threshold: int = 50,
    ) -> None:
        """Initialize the client.

        Args:
            token: GitHub token.
            repo_name: Repository in "owner/repo" format.
            conservative_mode_threshold: Rate limit remaining threshold below which
                the client enters conservative mode.
        """
        self.token = token
        self.repo_name = repo_name
        self.g = Github(token)
        self.repo: Repository = self.g.get_repo(repo_name)
        self.api_calls = 0
        self.rate_limit_remaining: int | None = None
        self.conservative_mode_threshold = conservative_mode_threshold
        self.conservative_mode: bool = False

    def check_rate_limit(self) -> None:
        """Check rate limit and enter conservative mode if below threshold.

        Conservative mode is a one-way latch — once set it is never cleared
        within the lifetime of this client instance.
        """
        if (
            self.rate_limit_remaining is not None
            and self.rate_limit_remaining < self.conservative_mode_threshold
        ):
            if not self.conservative_mode:
                logger.warning(
                    "Entering conservative mode due to low rate limit",
                    rate_limit_remaining=self.rate_limit_remaining,
                    threshold=self.conservative_mode_threshold,
                )
            self.conservative_mode = True

    def get_pull_request(self, number: int) -> PullRequest:
        """Fetch a pull request by number.

        Args:
            number: PR number.

        Returns:
            PullRequest object.
        """
        self.api_calls += 1
        logger.debug("Fetching pull request", number=number, api_calls=self.api_calls)
        return self.repo.get_pull(number)

    def get_pr_files(self, number: int) -> list[dict[str, Any]]:
        """Fetch changed files for a PR via REST API.

        Args:
            number: PR number.

        Returns:
            List of file dictionaries.
        """
        url = f"https://api.github.com/repos/{self.repo_name}/pulls/{number}/files"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        all_files: list[dict[str, Any]] = []
        page = 1
        while True:
            response = self._request(
                "GET", url, headers=headers, params={"page": page, "per_page": 100}
            )
            data = response.json()
            if not data:
                break
            all_files.extend(data)
            if "next" not in response.links:
                break
            page += 1

        logger.debug(
            "Fetched PR files",
            number=number,
            file_count=len(all_files),
            api_calls=self.api_calls,
        )
        return all_files

    def get_pr_diff(self, number: int) -> str:
        """Fetch the raw unified diff for a PR.

        Args:
            number: PR number.

        Returns:
            Raw diff text.
        """
        url = f"https://api.github.com/repos/{self.repo_name}/pulls/{number}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3.diff",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        response = self._request("GET", url, headers=headers)
        logger.debug("Fetched PR diff", number=number, api_calls=self.api_calls)
        return response.text

    def get_file_contents(self, path: str, ref: str) -> str | None:
        """Read file contents at a specific ref.

        Args:
            path: File path within the repo.
            ref: Branch, tag, or commit SHA.

        Returns:
            File contents as string, or None if not found.
        """
        if self.conservative_mode:
            logger.debug(
                "Skipping file contents in conservative mode",
                path=path,
                ref=ref,
            )
            return None

        url = f"https://api.github.com/repos/{self.repo_name}/contents/{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3.raw",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            response = self._request("GET", url, headers=headers, params={"ref": ref})
            return response.text
        except RateLimitError:
            # Propagate so the fail-fast cap in _request is not silently
            # swallowed — a rate-limit hang is exactly what we are guarding
            # against, not a "file not found".
            raise
        except Exception:
            logger.debug("File not found", path=path, ref=ref)
            return None

    def post_review(
        self,
        number: int,
        body: str,
        comments: list[dict[str, Any]] | None = None,
        event: str = "COMMENT",
        commit_id: str | None = None,
    ) -> dict[str, Any]:
        """Post a PR review with inline comments.

        Args:
            number: PR number.
            body: Review summary body.
            comments: List of inline comment dicts.
            event: Review event type ("COMMENT", "APPROVE", "REQUEST_CHANGES").
            commit_id: SHA of the commit to review.

        Returns:
            Response JSON.
        """
        url = f"https://api.github.com/repos/{self.repo_name}/pulls/{number}/reviews"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        payload: dict[str, Any] = {"body": body, "event": event}
        if comments:
            payload["comments"] = comments
        if commit_id:
            payload["commit_id"] = commit_id

        response = self._request("POST", url, headers=headers, json=payload)
        logger.debug("Posted PR review", number=number, api_calls=self.api_calls)
        return cast(dict[str, Any], response.json())

    def post_comment(self, number: int, body: str) -> dict[str, Any]:
        """Post a general PR comment.

        Args:
            number: PR number.
            body: Comment body.

        Returns:
            Response JSON.
        """
        url = f"https://api.github.com/repos/{self.repo_name}/issues/{number}/comments"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        response = self._request("POST", url, headers=headers, json={"body": body})
        logger.debug("Posted PR comment", number=number, api_calls=self.api_calls)
        return cast(dict[str, Any], response.json())

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Make an HTTP request with rate limit tracking and retry.

        Args:
            method: HTTP method.
            url: Request URL.
            **kwargs: Additional arguments for requests.

        Returns:
            Response object.

        Raises:
            RateLimitError: If rate limit is exceeded and retry fails.
            GitHubAPIError: On other API errors.
        """
        max_retries = 3
        for attempt in range(max_retries):
            self.api_calls += 1
            try:
                response = requests.request(method, url, timeout=30, **kwargs)

                # Track rate limit
                if "X-RateLimit-Remaining" in response.headers:
                    self.rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
                    self.check_rate_limit()

                if response.status_code == 403 and "rate limit" in response.text.lower():
                    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                    wait = reset_time - int(time.time()) + 5
                    if wait > _MAX_RATE_LIMIT_WAIT_SECONDS:
                        # Fail fast rather than hanging the process.  A wait
                        # this long (e.g. ~59 min in the pilot incident) would
                        # stall CI for the remainder of its timeout budget.
                        logger.error(
                            "Rate limit wait exceeds cap; failing fast",
                            wait_seconds=wait,
                            cap_seconds=_MAX_RATE_LIMIT_WAIT_SECONDS,
                        )
                        raise RateLimitError(
                            f"GitHub API rate limit exceeded; reset in {wait}s "
                            f"(cap={_MAX_RATE_LIMIT_WAIT_SECONDS}s)"
                        )
                    if wait > 0 and attempt < max_retries - 1:
                        logger.warning(
                            "Rate limited by GitHub, waiting until reset",
                            attempt=attempt,
                            wait_seconds=wait,
                        )
                        time.sleep(wait)
                        continue
                    raise RateLimitError("GitHub API rate limit exceeded")

                response.raise_for_status()
                logger.debug(
                    "GitHub API request succeeded",
                    method=method,
                    url=url,
                    status_code=response.status_code,
                    api_calls=self.api_calls,
                )
                return response

            except requests.HTTPError as e:
                if attempt < max_retries - 1:
                    delay = min(60, (2**attempt) + random.uniform(0, 1))
                    logger.warning(
                        "Retrying GitHub API call after HTTP error",
                        attempt=attempt,
                        delay=delay,
                        error=str(e),
                    )
                    time.sleep(delay)
                    continue
                raise GitHubAPIError(f"GitHub API error: {e}") from e
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    delay = min(60, (2**attempt) + random.uniform(0, 1))
                    logger.warning(
                        "Retrying GitHub API call after request error",
                        attempt=attempt,
                        delay=delay,
                        error=str(e),
                    )
                    time.sleep(delay)
                    continue
                raise GitHubAPIError(f"GitHub API request failed: {e}") from e

        raise GitHubAPIError("Max retries exceeded")
