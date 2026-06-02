"""Entry point for AI Council Code Review."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import structlog

from ai_council_review.config import load_config
from ai_council_review.github_client import GitHubClient
from ai_council_review.models import FileInfo
from ai_council_review.pr_ingestor import PRIngestor

logger = structlog.get_logger()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="AI Council Code Review — Multi-agent PR review system"
    )
    parser.add_argument("--pr-number", type=int, required=True, help="Pull request number")
    parser.add_argument("--repo", type=str, required=True, help="Repository in owner/repo format")
    parser.add_argument("--base-sha", type=str, default="", help="Base commit SHA")
    parser.add_argument("--head-sha", type=str, default="", help="Head commit SHA")
    parser.add_argument("--base-ref", type=str, default="", help="Base branch ref")
    parser.add_argument("--head-ref", type=str, default="", help="Head branch ref")
    parser.add_argument("--config", type=str, default=None, help="Path to config YAML file")
    parser.add_argument(
        "--event-path", type=str, default=None, help="Path to GitHub event payload JSON"
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point.

    Returns:
        Exit code.
    """
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
            if os.environ.get("CI")
            else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    args = parse_args()

    try:
        config = load_config(args.config)
        logger.info("Config loaded", config_path=args.config or ".ai-council/config.yaml")

        ingestor = PRIngestor(config)

        # Try to load event payload
        payload: dict[str, Any] | None = None
        if args.event_path:
            payload = ingestor.load_event_payload(args.event_path)
        elif os.environ.get("GITHUB_EVENT_PATH"):
            payload = ingestor.load_event_payload()

        if payload:
            pr, files, skipped, skip_reason = ingestor.ingest(payload)
        else:
            # Build minimal PR metadata from CLI args
            pr = ingestor.parse_pr_metadata(
                {
                    "pull_request": {
                        "number": args.pr_number,
                        "title": "",
                        "body": None,
                        "state": "open",
                        "draft": False,
                        "user": {"login": ""},
                        "author_association": "",
                        "base": {
                            "ref": args.base_ref,
                            "sha": args.base_sha,
                        },
                        "head": {
                            "ref": args.head_ref,
                            "sha": args.head_sha,
                        },
                        "additions": 0,
                        "deletions": 0,
                        "changed_files": 0,
                        "labels": [],
                        "html_url": None,
                        "diff_url": None,
                        "commits": 0,
                    }
                }
            )
            skipped, skip_reason = ingestor.should_skip(pr)
            files = []

        if skipped:
            logger.info("Skipping PR", pr=args.pr_number, reason=skip_reason)
            print(f"Skipping PR #{args.pr_number}: {skip_reason}")
            return 0

        # Fetch changed files from GitHub
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            client = GitHubClient(token, args.repo)
            raw_files = client.get_pr_files(args.pr_number)
            files = [
                FileInfo(
                    filename=f["filename"],
                    status=f["status"],
                    additions=f.get("additions", 0),
                    deletions=f.get("deletions", 0),
                    changes=f.get("changes", 0),
                    patch=f.get("patch"),
                    previous_filename=f.get("previous_filename"),
                    sha=f.get("sha"),
                    raw_url=f.get("raw_url"),
                )
                for f in raw_files
            ]
            files = ingestor.filter_files(files)

        # Print structured output
        output = {
            "pr": pr.model_dump(mode="json"),
            "files": [f.model_dump(mode="json") for f in files],
            "api_calls": getattr(client, "api_calls", 0) if token else 0,
            "skipped": skipped,
            "skip_reason": skip_reason,
        }
        print(json.dumps(output, indent=2))
        return 0

    except Exception as e:
        logger.error("Review failed", error=str(e))
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
