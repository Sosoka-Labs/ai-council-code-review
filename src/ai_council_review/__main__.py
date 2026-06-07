"""Entry point for AI Council Code Review."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
from typing import Any

import structlog

from ai_council_review.config import load_config
from ai_council_review.github.client import GitHubClient
from ai_council_review.github.ingestor import PRIngestor
from ai_council_review.llm.graph import build_graph
from ai_council_review.models import FileInfo, ReviewState
from ai_council_review.utils.debug import dump_state

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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without posting to GitHub",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Dump debug artifacts after the review",
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

        # Build initial state
        state = ReviewState()

        # Load PR metadata from event payload or CLI args
        ingestor = PRIngestor(config)
        payload: dict[str, Any] | None = None
        if args.event_path:
            payload = ingestor.load_event_payload(args.event_path)
        elif os.environ.get("GITHUB_EVENT_PATH"):
            payload = ingestor.load_event_payload()

        if payload:
            pr, files, skipped, skip_reason = ingestor.ingest(payload)
        else:
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

        state.pr_metadata = pr
        state.skipped = skipped
        state.skip_reason = skip_reason
        state.changed_files = files

        # Debug: log head_sha and actual git HEAD
        import subprocess

        try:
            git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        except Exception:
            git_head = "unknown"
        logger.info(
            "PR metadata",
            head_sha=pr.head_sha if pr else None,
            git_head=git_head,
            base_sha=pr.base_sha if pr else None,
        )

        if skipped:
            logger.info("Skipping PR", pr=args.pr_number, reason=skip_reason)
            print(f"Skipping PR #{args.pr_number}: {skip_reason}")
            if args.debug or os.environ.get("AI_COUNCIL__DEBUG") == "1":
                dump_state(state)
            return 0

        # Fetch changed files from GitHub if not already loaded
        token = os.environ.get("GITHUB_TOKEN")
        if token and not state.changed_files:
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
            state.changed_files = ingestor.filter_files(files)

        # Build and run the graph
        if args.dry_run:
            logger.info("Dry run mode — not posting to GitHub")
            # In dry-run mode, we skip the post step by not running the graph
            # Just print the state
            dry_run_output = {
                "pr": state.pr_metadata.model_dump(mode="json") if state.pr_metadata else None,
                "files": [f.model_dump(mode="json") for f in state.changed_files],
                "skipped": state.skipped,
                "skip_reason": state.skip_reason,
            }
            print(json.dumps(dry_run_output, indent=2))
            if args.debug or os.environ.get("AI_COUNCIL__DEBUG") == "1":
                dump_state(state)
            return 0

        graph = build_graph(config)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(graph.invoke, state)
            try:
                result = future.result(timeout=config.total_timeout_seconds)
            except concurrent.futures.TimeoutError:
                logger.error(
                    "Overall graph timeout",
                    timeout=config.total_timeout_seconds,
                )
                if args.debug or os.environ.get("AI_COUNCIL__DEBUG") == "1":
                    dump_state(state)
                return 1

        # LangGraph v0.2 returns a dict or StateSnapshot; convert to ReviewState
        if isinstance(result, dict):
            final_state = ReviewState(**result)
        else:
            final_state = ReviewState(**result.model_dump())

        # Dump debug state if requested
        if args.debug or os.environ.get("AI_COUNCIL__DEBUG") == "1":
            dump_state(final_state)

        # Print summary
        summary_output: dict[str, Any] = {
            "pr": final_state.pr_metadata.model_dump(mode="json")
            if final_state.pr_metadata
            else None,
            "files_reviewed": len(final_state.changed_files),
            "findings": sum(len(f) for f in final_state.agent_outputs.values()),
            "verdict": final_state.verdict,
            "summary": final_state.summary,
            "skipped": final_state.skipped,
            "skip_reason": final_state.skip_reason,
            "errors": final_state.errors,
        }
        print(json.dumps(summary_output, indent=2))
        return 0

    except Exception as e:
        logger.error("Review failed", error=str(e))
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
