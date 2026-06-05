"""GitHub integration package for AI Council Code Review.

Contains API client, PR ingestion, review publishing, and repository browsing.
"""

from __future__ import annotations

from ai_council_review.github.browser import RepositoryBrowser
from ai_council_review.github.client import GitHubClient
from ai_council_review.github.ingestor import PRIngestor
from ai_council_review.github.publisher import Publisher

__all__ = [
    "GitHubClient",
    "PRIngestor",
    "Publisher",
    "RepositoryBrowser",
]
