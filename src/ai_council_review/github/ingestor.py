"""PR ingestor — load event payload, compute stats, filter PRs."""

from __future__ import annotations

import fnmatch
import json
import os
from typing import Any, cast

import structlog

from ai_council_review.config import CouncilConfig
from ai_council_review.exceptions import IngestorError
from ai_council_review.models import FileInfo, PRMetadata

logger = structlog.get_logger()


class PRIngestor:
    """Ingests PR metadata from GitHub event payload or CLI arguments."""

    def __init__(self, config: CouncilConfig) -> None:
        """Initialize with configuration.

        Args:
            config: Council configuration.
        """
        self.config = config

    def load_event_payload(self, event_path: str | None = None) -> dict[str, Any]:
        """Load the GitHub Actions event payload.

        Args:
            event_path: Path to the JSON payload file. If None, uses
                GITHUB_EVENT_PATH environment variable.

        Returns:
            The event payload as a dictionary.

        Raises:
            IngestorError: If the payload cannot be loaded.
        """
        path = event_path or os.environ.get("GITHUB_EVENT_PATH")
        if not path:
            raise IngestorError("GITHUB_EVENT_PATH not set")

        try:
            with open(path, encoding="utf-8") as f:
                return cast(dict[str, Any], json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            raise IngestorError(f"Failed to load event payload: {e}") from e

    def parse_pr_metadata(self, payload: dict[str, Any]) -> PRMetadata:
        """Parse PR metadata from the event payload.

        Args:
            payload: The GitHub event payload.

        Returns:
            PRMetadata object.
        """
        pr = payload.get("pull_request", {})
        head = pr.get("head", {})
        base = pr.get("base", {})
        head_repo = head.get("repo", {})
        base_repo = base.get("repo", {})

        is_fork = head_repo.get("full_name", "") != base_repo.get("full_name", "")
        fork_url = head_repo.get("html_url", "") if is_fork else None

        logger.info(
            "Parsed PR metadata",
            pr_number=pr.get("number", 0),
            is_fork=is_fork,
            fork_url=fork_url,
            head_repo=head_repo.get("full_name", ""),
            base_repo=base_repo.get("full_name", ""),
        )

        return PRMetadata(
            number=pr.get("number", 0),
            title=pr.get("title", ""),
            body=pr.get("body", ""),
            state=pr.get("state", ""),
            draft=pr.get("draft", False),
            author=pr.get("user", {}).get("login", ""),
            author_association=pr.get("author_association", ""),
            base_ref=base.get("ref", ""),
            base_sha=base.get("sha", ""),
            head_ref=head.get("ref", ""),
            head_sha=head.get("sha", ""),
            additions=pr.get("additions", 0),
            deletions=pr.get("deletions", 0),
            changed_files=pr.get("changed_files", 0),
            labels=[label.get("name", "") for label in pr.get("labels", [])],
            html_url=pr.get("html_url", ""),
            diff_url=pr.get("diff_url", ""),
            commits=pr.get("commits", 0),
            created_at=pr.get("created_at"),
            updated_at=pr.get("updated_at"),
            is_fork=is_fork,
        )

    def should_skip(self, pr: PRMetadata) -> tuple[bool, str]:
        """Determine if a PR should be skipped based on config rules.

        Args:
            pr: PR metadata.

        Returns:
            Tuple of (should_skip, reason).
        """
        if self.config.skip_drafts and pr.draft:
            return True, "Draft PR"

        if pr.is_fork and not self.config.comment_on_forks:
            logger.warning(
                "Skipping fork PR",
                pr=pr.number,
                comment_on_forks=self.config.comment_on_forks,
                is_fork=pr.is_fork,
            )
            return True, "Fork PR (comment_on_forks disabled)"

        label_names = {label.lower() for label in pr.labels}
        skip_labels = {label.lower() for label in self.config.skip_labels}
        if label_names & skip_labels:
            return True, f"Skip label present: {label_names & skip_labels}"

        if pr.changed_files > self.config.max_files:
            return True, f"Too many files ({pr.changed_files} > {self.config.max_files})"

        total_lines = pr.additions + pr.deletions
        if total_lines > self.config.max_lines:
            return True, f"Too many lines changed ({total_lines} > {self.config.max_lines})"

        return False, ""

    def filter_files(self, files: list[FileInfo]) -> list[FileInfo]:
        """Filter out generated/unwanted files.

        Args:
            files: List of changed files.

        Returns:
            Filtered list.
        """
        result: list[FileInfo] = []
        for file in files:
            if self._should_skip_file(file.filename):
                logger.info("Skipping file", filename=file.filename)
                continue
            result.append(file)
        return result

    def _should_skip_file(self, filename: str) -> bool:
        """Check if a file should be skipped based on patterns.

        Supports glob-style patterns:
        - Exact match: `package-lock.json`
        - Substring/directory: `dist/` (matches `dist/bundle.js`)
        - Wildcards: `*.snap`, `**/*.pyc`

        Args:
            filename: The file path.

        Returns:
            True if the file should be skipped.
        """
        for pattern in self.config.skip_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
            if pattern in filename:
                return True
        return False

    def ingest(
        self, payload: dict[str, Any] | None = None
    ) -> tuple[PRMetadata, list[FileInfo], bool, str]:
        """Full ingestion pipeline.

        Args:
            payload: Optional pre-loaded payload. If None, loads from
                GITHUB_EVENT_PATH.

        Returns:
            Tuple of (PR metadata, filtered files, should_skip, skip_reason).
        """
        if payload is None:
            payload = self.load_event_payload()

        pr = self.parse_pr_metadata(payload)
        should_skip, reason = self.should_skip(pr)

        if should_skip:
            logger.info("Skipping PR", pr=pr.number, reason=reason)
            return pr, [], True, reason

        logger.info("Ingesting PR", pr=pr.number, title=pr.title)
        return pr, [], False, ""
