"""GitHub API client wrapper with retry and rate limit tracking."""

from __future__ import annotations

import time
from typing import Any, cast

import requests
from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository

from ai_council_review.exceptions import GitHubAPIError, RateLimitError


class GitHubClient:
    """Wrapper around PyGithub and raw REST calls with retry logic."""

    def __init__(self, token: str, repo_name: str) -> None:
        """Initialize the client.

        Args:
            token: GitHub token.
            repo_name: Repository in "owner/repo" format.
        """
        self.token = token
        self.repo_name = repo_name
        self.g = Github(token)
        self.repo: Repository = self.g.get_repo(repo_name)
        self.api_calls = 0
        self.rate_limit_remaining: int | None = None

    def get_pull_request(self, number: int) -> PullRequest:
        """Fetch a pull request by number.

        Args:
            number: PR number.

        Returns:
            PullRequest object.
        """
        self.api_calls += 1
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
        return response.text

    def get_file_contents(self, path: str, ref: str) -> str | None:
        """Read file contents at a specific ref.

        Args:
            path: File path within the repo.
            ref: Branch, tag, or commit SHA.

        Returns:
            File contents as string, or None if not found.
        """
        url = f"https://api.github.com/repos/{self.repo_name}/contents/{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.raw+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            response = self._request("GET", url, headers=headers, params={"ref": ref})
            data = response.json()
            import base64

            return base64.b64decode(data["content"]).decode("utf-8")
        except Exception:
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
            try:
                response = requests.request(method, url, timeout=30, **kwargs)

                # Track rate limit
                if "X-RateLimit-Remaining" in response.headers:
                    self.rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])

                if response.status_code == 403 and "rate limit" in response.text.lower():
                    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                    wait = reset_time - int(time.time()) + 5
                    if wait > 0 and attempt < max_retries - 1:
                        time.sleep(wait)
                        continue
                    raise RateLimitError("GitHub API rate limit exceeded")

                response.raise_for_status()
                self.api_calls += 1
                return response

            except requests.HTTPError as e:
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise GitHubAPIError(f"GitHub API error: {e}") from e
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise GitHubAPIError(f"GitHub API request failed: {e}") from e

        raise GitHubAPIError("Max retries exceeded")
