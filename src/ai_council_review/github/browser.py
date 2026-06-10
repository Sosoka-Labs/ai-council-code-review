"""Repository browser — read files via local git or GitHub API."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path
from typing import Any, cast

import structlog

from ai_council_review.exceptions import GitHubAPIError

logger = structlog.get_logger()


class RepositoryBrowser:
    """Browse repository files, preferring local git, falling back to GitHub API."""

    def __init__(
        self,
        repo_path: str | Path | None = None,
        github_client: Any | None = None,
    ) -> None:
        """Initialize the browser.

        Args:
            repo_path: Path to the local repository. If None, uses
                GITHUB_WORKSPACE or current directory.
            github_client: GitHubClient instance for API fallback.
        """
        self.repo_path = Path(repo_path or Path.cwd())
        self.github_client = github_client
        self.api_calls = 0

    def get_file(self, path: str, ref: str = "HEAD") -> str | None:
        """Read a file at a specific ref.

        Tries local git first, falls back to GitHub API.

        Args:
            path: File path relative to repo root.
            ref: Git ref (branch, tag, or commit SHA).

        Returns:
            File contents as string, or None if not found.
        """
        local = self._get_file_local(path, ref)
        if local is not None:
            return local

        if self.github_client is not None:
            return self._get_file_api(path, ref)

        return None

    def get_file_at_base(self, path: str, base_ref: str) -> str | None:
        """Read a file at the base branch.

        Args:
            path: File path.
            base_ref: Base branch ref.

        Returns:
            File contents or None.
        """
        return self.get_file(path, ref=base_ref)

    def get_file_at_head(self, path: str) -> str | None:
        """Read a file at the HEAD of the current branch.

        Args:
            path: File path.

        Returns:
            File contents or None.
        """
        return self.get_file(path, ref="HEAD")

    def list_directory(self, path: str, ref: str = "HEAD") -> list[str] | None:
        """List files in a directory.

        Args:
            path: Directory path.
            ref: Git ref.

        Returns:
            List of filenames, or None if directory not found.
        """
        try:
            result = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", ref, path],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            files = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            return files
        except subprocess.CalledProcessError:
            return None

    def find_files(self, pattern: str, ref: str = "HEAD") -> list[str]:
        """Find files matching a pattern.

        Args:
            pattern: Glob pattern to search for.
            ref: Git ref.

        Returns:
            List of matching file paths.
        """
        try:
            result = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", ref],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            all_files = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            return [f for f in all_files if fnmatch.fnmatch(f, pattern)]
        except subprocess.CalledProcessError:
            return []

    def file_exists(self, path: str, ref: str = "HEAD") -> bool:
        """Check if a file exists at a given ref.

        Args:
            path: File path.
            ref: Git ref.

        Returns:
            True if the file exists.
        """
        try:
            subprocess.run(
                ["git", "cat-file", "-e", f"{ref}:{path}"],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def _get_file_local(self, path: str, ref: str) -> str | None:
        """Read file using local git.

        Args:
            path: File path.
            ref: Git ref.

        Returns:
            File contents or None.
        """
        try:
            result = subprocess.run(
                ["git", "show", f"{ref}:{path}"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return None

    def _get_file_api(self, path: str, ref: str) -> str | None:
        """Read file using GitHub API.

        Args:
            path: File path.
            ref: Git ref.

        Returns:
            File contents or None.
        """
        if self.github_client is None:
            return None

        try:
            self.api_calls += 1
            result = self.github_client.get_file_contents(path, ref)
            return cast(str | None, result)
        except GitHubAPIError:
            return None
