"""Publisher — post reviews and comments to GitHub."""

from __future__ import annotations

from typing import Any

import structlog

from ai_council_review.exceptions import GitHubAPIError
from ai_council_review.github.client import GitHubClient
from ai_council_review.models import FileInfo, ReviewComment

logger = structlog.get_logger()

# GitHub allows up to 100 comments per review; we keep batches small to
# avoid 502 Bad Gateway errors from oversized payloads.
MAX_COMMENTS_PER_REVIEW = 30


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

        Handles batching if there are more than ``MAX_COMMENTS_PER_REVIEW`` comments.

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
        except GitHubAPIError as e:
            # 422 often means an inline comment is invalid. Fall back to a
            # body-only review so the findings are not lost entirely.
            error_msg = str(e)
            if comments and "422" in error_msg:
                logger.warning(
                    "Inline review failed with 422; retrying as body-only review",
                    pr_number=pr_number,
                    comment_count=len(comments),
                )
                fallback_body = body + "\n\n**Inline comments (fall-back):**\n"
                for c in comments:
                    fallback_body += f"\n- `{c['path']}:{c.get('line', '?')}` — {c['body'][:200]}"
                try:
                    self.client.post_review(
                        number=pr_number,
                        body=fallback_body,
                        comments=[],
                        event=event,
                        commit_id=commit_id,
                    )
                    logger.info("Posted body-only fallback review")
                    return
                except GitHubAPIError:
                    logger.error("Fallback review also failed")
                    raise
            logger.error(
                "Failed to post review",
                pr_number=pr_number,
                commit_id=commit_id,
                comment_count=len(comments),
                first_comment=comments[0] if comments else None,
            )
            raise

    def _comment_to_dict(self, comment: ReviewComment) -> dict[str, Any]:
        """Convert a ReviewComment to a dict for the GitHub API.

        Uses line + side (the modern API) instead of the deprecated position.

        Args:
            comment: ReviewComment instance.

        Returns:
            API-compatible dict.
        """
        result: dict[str, Any] = {
            "path": comment.path,
            "body": comment.body,
        }
        # Prefer line + side over the deprecated position parameter.
        if comment.line is not None:
            result["line"] = comment.line
            result["side"] = comment.side
        elif comment.position is not None:
            # Fallback for older callers that still set position
            result["position"] = comment.position
        if comment.start_line is not None:
            result["start_line"] = comment.start_line
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
