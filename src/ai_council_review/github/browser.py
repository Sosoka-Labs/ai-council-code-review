"""Repository browser — read files via local git or GitHub API."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path
from typing import Any, cast

import structlog

from ai_council_review.exceptions import GitHubAPIError

logger = structlog.get_logger()

# Refs that refer to the currently checked-out working tree rather than a
# named historical ref.  For these we read the file directly from disk, which
# removes subprocess overhead and any dependency on the ref actually being
# fetched in a shallow clone.
_HEAD_REFS: frozenset[str] = frozenset({"HEAD", ""})


def _is_head_ref(ref: str) -> bool:
    """Return True when *ref* refers to the current working-tree checkout.

    Args:
        ref: Git ref string (may be empty).

    Returns:
        True for HEAD / empty string variants; False for explicit branch/SHA refs.
    """
    return ref in _HEAD_REFS


def _is_within_repo(target: Path, repo_path: Path) -> bool:
    """Return True when *target* is inside *repo_path* (both resolved).

    This guard prevents path-traversal attacks where a diff-provided path such
    as ``../../etc/passwd`` would escape the repo root.

    Args:
        target: Resolved absolute path to the file being read.
        repo_path: Resolved absolute path to the repo root.

    Returns:
        True when *target* is at or below *repo_path*.
    """
    try:
        target.relative_to(repo_path)
        return True
    except ValueError:
        return False


class RepositoryBrowser:
    """Browse repository files, preferring local git, falling back to GitHub API.

    Read priority for any single file:
    1. Filesystem (working tree) — only for HEAD/empty/None refs.
    2. ``git show {ref}:{path}`` — for all other explicit refs.
    3. GitHub Contents API — last resort, only when ``github_client`` is set.
    """

    def __init__(
        self,
        repo_path: str | Path | None = None,
        github_client: Any | None = None,
    ) -> None:
        """Initialize the browser.

        Args:
            repo_path: Path to the local repository. If None, uses
                the current working directory.
            github_client: GitHubClient instance for API fallback.
                Pass ``None`` to disable API calls entirely (preferred in CI
                where the target repo is already checked out on disk).
        """
        self.repo_path = Path(repo_path or Path.cwd()).resolve()
        self.github_client = github_client
        self.api_calls = 0

    def get_file(self, path: str, ref: str | None = "HEAD") -> str | None:
        """Read a file at a specific ref.

        Resolution order:
        1. Filesystem (working tree) when *ref* is HEAD/empty/None.
        2. ``git show`` for explicit non-HEAD refs.
        3. GitHub Contents API when a client is attached and both local paths
           return None.

        Args:
            path: File path relative to repo root.
            ref: Git ref (branch, tag, or commit SHA).  Pass ``"HEAD"``,
                ``""``, or ``None`` to read from the working tree.

        Returns:
            File contents as string, or None if not found.
        """
        # Normalise None to empty string so _is_head_ref works uniformly.
        effective_ref = ref if ref is not None else ""

        if _is_head_ref(effective_ref):
            content = self._get_file_filesystem(path)
            if content is not None:
                return content
        else:
            content = self._get_file_git(path, effective_ref)
            if content is not None:
                return content

        if self.github_client is not None:
            return self._get_file_api(path, effective_ref or "HEAD")

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

    def _get_file_filesystem(self, path: str) -> str | None:
        """Read a file directly from the working-tree checkout.

        This is the preferred path for HEAD reads: no subprocess, no network,
        and it works even in shallow clones where the ref may not be present.

        A path-traversal guard is applied before reading — if the resolved
        absolute path escapes ``repo_path`` the call returns None rather than
        reading an arbitrary file.  Diffs/paths are attacker-controllable and
        must not be trusted without this check.

        Args:
            path: File path relative to repo root.

        Returns:
            File contents as a string, or None if the file does not exist or
            the path would escape the repo root.
        """
        target = (self.repo_path / path).resolve()
        if not _is_within_repo(target, self.repo_path):
            logger.warning(
                "Path traversal attempt blocked",
                path=path,
                repo_path=str(self.repo_path),
            )
            return None

        try:
            return target.read_text(errors="replace")
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            return None

    def _get_file_git(self, path: str, ref: str) -> str | None:
        """Read a file at an explicit non-HEAD ref using ``git show``.

        Use this for base-branch or historical comparisons where the ref is
        meaningful.  For HEAD reads, prefer ``_get_file_filesystem`` which has
        no subprocess overhead and works in shallow clones.

        Args:
            path: File path relative to repo root.
            ref: Git ref (branch, tag, or commit SHA).

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
