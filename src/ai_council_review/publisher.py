"""Publisher — post reviews and comments to GitHub."""

from __future__ import annotations

from typing import Any

import structlog

from ai_council_review.exceptions import GitHubAPIError
from ai_council_review.github_client import GitHubClient
from ai_council_review.models import FileInfo, ReviewComment

logger = structlog.get_logger()

# GitHub allows max 100 comments per review
MAX_COMMENTS_PER_REVIEW = 100


class Publisher:
    """Publishes review comments and summary to GitHub."""

    def __init__(self, client: GitHubClient) -> None:
        """Initialize the publisher.

        Args:
            client: GitHub API client.
        """
        self.client = client

    def post_review(
        self,
        pr_number: int,
        summary: str,
        comments: list[ReviewComment],
        commit_id: str | None = None,
    ) -> None:
        """Post a PR review with inline comments.

        Handles batching if there are more than 100 comments.

        Args:
            pr_number: PR number.
            summary: Review summary body.
            comments: List of inline comments.
            commit_id: SHA of the commit to review.
        """
        if not comments:
            logger.info("Posting summary review (no inline comments)")
            self._post_single_review(pr_number, summary, [], "COMMENT", commit_id)
            return

        # Batch comments
        for i in range(0, len(comments), MAX_COMMENTS_PER_REVIEW):
            batch = comments[i : i + MAX_COMMENTS_PER_REVIEW]
            is_first = i == 0
            batch_summary = (
                summary
                if is_first
                else f"Additional comments (batch {i // MAX_COMMENTS_PER_REVIEW + 1})"
            )

            self._post_single_review(
                pr_number,
                batch_summary,
                [self._comment_to_dict(c) for c in batch],
                "COMMENT",
                commit_id,
            )
            logger.info(
                "Posted review batch",
                batch_size=len(batch),
                batch_number=i // MAX_COMMENTS_PER_REVIEW + 1,
            )

    def post_comment(self, pr_number: int, body: str) -> None:
        """Post a general PR comment.

        Args:
            pr_number: PR number.
            body: Comment body.
        """
        try:
            self.client.post_comment(pr_number, body)
            logger.info("Posted general PR comment")
        except GitHubAPIError:
            logger.error("Failed to post general comment")
            raise

    def _post_single_review(
        self,
        pr_number: int,
        body: str,
        comments: list[dict[str, Any]],
        event: str,
        commit_id: str | None,
    ) -> None:
        """Post a single review.

        Args:
            pr_number: PR number.
            body: Review body.
            comments: Comment dicts.
            event: Review event.
            commit_id: Commit SHA.
        """
        try:
            self.client.post_review(
                number=pr_number,
                body=body,
                comments=comments,
                event=event,
                commit_id=commit_id,
            )
        except GitHubAPIError:
            logger.error("Failed to post review")
            raise

    def _comment_to_dict(self, comment: ReviewComment) -> dict[str, Any]:
        """Convert a ReviewComment to a dict for the GitHub API.

        Args:
            comment: ReviewComment instance.

        Returns:
            API-compatible dict.
        """
        result: dict[str, Any] = {
            "path": comment.path,
            "position": comment.position,
            "body": comment.body,
            "side": comment.side,
        }
        if comment.line is not None:
            result["line"] = comment.line
        if comment.start_line is not None:
            result["start_line"] = comment.start_line
        if comment.start_side is not None:
            result["start_side"] = comment.start_side
        return result

    def validate_comments(
        self, comments: list[ReviewComment], changed_files: list[FileInfo]
    ) -> list[ReviewComment]:
        """Validate that comments reference files that were actually changed.

        Args:
            comments: Proposed comments.
            changed_files: List of changed files.

        Returns:
            Filtered list of valid comments.
        """
        valid_paths = {f.filename for f in changed_files}
        valid: list[ReviewComment] = []

        for comment in comments:
            if comment.path not in valid_paths:
                logger.warning(
                    "Dropping comment for unchanged file",
                    path=comment.path,
                )
                continue
            valid.append(comment)

        return valid
