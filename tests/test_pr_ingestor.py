"""Tests for ai_council_review.pr_ingestor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ai_council_review.config import CouncilConfig
from ai_council_review.exceptions import IngestorError
from ai_council_review.models import FileInfo
from ai_council_review.pr_ingestor import PRIngestor


@pytest.fixture
def config() -> CouncilConfig:
    """Default council config."""
    return CouncilConfig()


@pytest.fixture
def ingestor(config: CouncilConfig) -> PRIngestor:
    """PRIngestor with default config."""
    return PRIngestor(config)


@pytest.fixture
def realistic_payload() -> dict[str, Any]:
    """A realistic GitHub PR event payload."""
    return {
        "pull_request": {
            "number": 42,
            "title": "Add feature X",
            "body": "This PR adds feature X.",
            "state": "open",
            "draft": False,
            "user": {"login": "alice"},
            "author_association": "CONTRIBUTOR",
            "additions": 120,
            "deletions": 30,
            "changed_files": 5,
            "labels": [{"name": "enhancement"}],
            "html_url": "https://github.com/owner/repo/pull/42",
            "diff_url": "https://github.com/owner/repo/pull/42.diff",
            "commits": 3,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "head": {
                "ref": "feature/x",
                "sha": "abc123",
                "repo": {
                    "full_name": "owner/repo",
                    "html_url": "https://github.com/owner/repo",
                },
            },
            "base": {
                "ref": "main",
                "sha": "def456",
                "repo": {
                    "full_name": "owner/repo",
                    "html_url": "https://github.com/owner/repo",
                },
            },
        },
    }


class TestLoadEventPayload:
    """Tests for load_event_payload."""

    def test_load_event_payload(self, tmp_path: Path, ingestor: PRIngestor) -> None:
        """Create a temp JSON file and load it."""
        payload = {"action": "opened", "number": 1}
        event_file = tmp_path / "event.json"
        event_file.write_text(json.dumps(payload))

        result = ingestor.load_event_payload(str(event_file))

        assert result == payload

    def test_load_event_payload_missing(self, ingestor: PRIngestor, monkeypatch: pytest.MonkeyPatch) -> None:
        """Raise IngestorError when path is missing and env var is not set."""
        monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

        with pytest.raises(IngestorError, match="GITHUB_EVENT_PATH not set"):
            ingestor.load_event_payload()

    def test_load_event_payload_from_env(self, tmp_path: Path, ingestor: PRIngestor, monkeypatch: pytest.MonkeyPatch) -> None:
        """Load from GITHUB_EVENT_PATH environment variable."""
        payload = {"action": "opened"}
        event_file = tmp_path / "event.json"
        event_file.write_text(json.dumps(payload))
        monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))

        result = ingestor.load_event_payload()

        assert result == payload

    def test_load_event_payload_invalid_json(self, tmp_path: Path, ingestor: PRIngestor) -> None:
        """Raise IngestorError on invalid JSON."""
        event_file = tmp_path / "event.json"
        event_file.write_text("not json")

        with pytest.raises(IngestorError, match="Failed to load event payload"):
            ingestor.load_event_payload(str(event_file))


class TestParsePrMetadata:
    """Tests for parse_pr_metadata."""

    def test_parse_pr_metadata(self, ingestor: PRIngestor, realistic_payload: dict[str, Any]) -> None:
        """Parse a realistic payload dict."""
        pr = ingestor.parse_pr_metadata(realistic_payload)

        assert pr.number == 42
        assert pr.title == "Add feature X"
        assert pr.body == "This PR adds feature X."
        assert pr.state == "open"
        assert pr.draft is False
        assert pr.author == "alice"
        assert pr.author_association == "CONTRIBUTOR"
        assert pr.base_ref == "main"
        assert pr.base_sha == "def456"
        assert pr.head_ref == "feature/x"
        assert pr.head_sha == "abc123"
        assert pr.additions == 120
        assert pr.deletions == 30
        assert pr.changed_files == 5
        assert pr.labels == ["enhancement"]
        assert pr.html_url == "https://github.com/owner/repo/pull/42"
        assert pr.diff_url == "https://github.com/owner/repo/pull/42.diff"
        assert pr.commits == 3
        assert pr.is_fork is False

    def test_parse_pr_metadata_fork(self, ingestor: PRIngestor) -> None:
        """Parse a payload from a fork PR."""
        payload = {
            "pull_request": {
                "number": 1,
                "title": "Fork PR",
                "state": "open",
                "draft": False,
                "user": {"login": "bob"},
                "author_association": "NONE",
                "head": {
                    "ref": "patch-1",
                    "sha": "aaa",
                    "repo": {
                        "full_name": "fork-owner/repo",
                        "html_url": "https://github.com/fork-owner/repo",
                    },
                },
                "base": {
                    "ref": "main",
                    "sha": "bbb",
                    "repo": {
                        "full_name": "owner/repo",
                        "html_url": "https://github.com/owner/repo",
                    },
                },
            },
        }

        pr = ingestor.parse_pr_metadata(payload)

        assert pr.is_fork is True


class TestShouldSkip:
    """Tests for should_skip logic."""

    def _make_pr(self, **kwargs: Any) -> Any:
        """Build a PRMetadata with required fields."""
        from ai_council_review.models import PRMetadata
        defaults = {
            "number": 1,
            "title": "T",
            "state": "open",
            "author": "x",
            "author_association": "CONTRIBUTOR",
            "base_ref": "main",
            "base_sha": "b",
            "head_ref": "feat",
            "head_sha": "h",
        }
        defaults.update(kwargs)
        return PRMetadata(**defaults)

    def test_should_skip_draft(self, ingestor: PRIngestor) -> None:
        """Draft PR is skipped when skip_drafts is True."""
        pr = self._make_pr(draft=True)

        skipped, reason = ingestor.should_skip(pr)

        assert skipped is True
        assert reason == "Draft PR"

    def test_should_skip_fork(self, ingestor: PRIngestor) -> None:
        """Fork PR is skipped when comment_on_forks is False."""
        pr = self._make_pr(is_fork=True)
        ingestor.config.comment_on_forks = False

        skipped, reason = ingestor.should_skip(pr)

        assert skipped is True
        assert "Fork PR" in reason

    def test_should_skip_fork_allowed(self, ingestor: PRIngestor) -> None:
        """Fork PR is NOT skipped when comment_on_forks is True."""
        pr = self._make_pr(is_fork=True)
        ingestor.config.comment_on_forks = True

        skipped, reason = ingestor.should_skip(pr)

        assert skipped is False
        assert reason == ""

    def test_should_skip_too_many_files(self, ingestor: PRIngestor) -> None:
        """Too many files skipped."""
        pr = self._make_pr(changed_files=100)
        ingestor.config.max_files = 50

        skipped, reason = ingestor.should_skip(pr)

        assert skipped is True
        assert "Too many files" in reason

    def test_should_skip_too_many_lines(self, ingestor: PRIngestor) -> None:
        """Too many lines skipped."""
        pr = self._make_pr(additions=1500, deletions=1000)
        ingestor.config.max_lines = 2000

        skipped, reason = ingestor.should_skip(pr)

        assert skipped is True
        assert "Too many lines" in reason

    def test_should_skip_labels(self, ingestor: PRIngestor) -> None:
        """Skip label present."""
        pr = self._make_pr(labels=["skip-review", "bug"])
        ingestor.config.skip_labels = ["skip-review"]

        skipped, reason = ingestor.should_skip(pr)

        assert skipped is True
        assert "Skip label present" in reason

    def test_should_not_skip_normal_pr(self, ingestor: PRIngestor) -> None:
        """Normal PR should not be skipped."""
        pr = self._make_pr(changed_files=5, additions=10, deletions=5)

        skipped, reason = ingestor.should_skip(pr)

        assert skipped is False
        assert reason == ""


class TestFilterFiles:
    """Tests for filter_files."""

    def test_filter_files(self, ingestor: PRIngestor) -> None:
        """Filters out lock files, node_modules, dist, build, etc."""
        files = [
            FileInfo(filename="package-lock.json", status="modified"),
            FileInfo(filename="yarn.lock", status="modified"),
            FileInfo(filename="poetry.lock", status="modified"),
            FileInfo(filename="Cargo.lock", status="modified"),
            FileInfo(filename="Gemfile.lock", status="modified"),
            FileInfo(filename="dist/bundle.js", status="added"),
            FileInfo(filename="build/output.css", status="added"),
            FileInfo(filename="node_modules/lodash/index.js", status="modified"),
            FileInfo(filename="src/main.py", status="modified"),
            FileInfo(filename="README.md", status="modified"),
        ]

        result = ingestor.filter_files(files)
        filenames = [f.filename for f in result]

        assert "src/main.py" in filenames
        assert "README.md" in filenames
        assert "package-lock.json" not in filenames
        assert "yarn.lock" not in filenames
        assert "poetry.lock" not in filenames
        assert "Cargo.lock" not in filenames
        assert "Gemfile.lock" not in filenames
        assert "dist/bundle.js" not in filenames
        assert "build/output.css" not in filenames
        assert "node_modules/lodash/index.js" not in filenames

    def test_filter_files_custom_patterns(self, ingestor: PRIngestor) -> None:
        """Custom skip patterns filter correctly."""
        ingestor.config.skip_patterns = [".pyc", "vendor/"]
        files = [
            FileInfo(filename="app.py", status="modified"),
            FileInfo(filename="helpers.pyc", status="modified"),
            FileInfo(filename="vendor/lib.py", status="added"),
        ]

        result = ingestor.filter_files(files)
        filenames = [f.filename for f in result]

        assert "app.py" in filenames
        assert "helpers.pyc" not in filenames
        assert "vendor/lib.py" not in filenames


class TestIngestFull:
    """Tests for full ingest pipeline."""

    def test_ingest_full(self, ingestor: PRIngestor, realistic_payload: dict[str, Any]) -> None:
        """End-to-end with mock payload."""
        pr, files, skipped, reason = ingestor.ingest(realistic_payload)

        assert pr.number == 42
        assert pr.title == "Add feature X"
        assert skipped is False
        assert reason == ""
        assert files == []

    def test_ingest_full_skipped(self, ingestor: PRIngestor) -> None:
        """End-to-end with draft PR that gets skipped."""
        payload = {
            "pull_request": {
                "number": 1,
                "title": "Draft",
                "state": "open",
                "draft": True,
                "user": {"login": "alice"},
                "author_association": "CONTRIBUTOR",
                "head": {"ref": "draft", "sha": "aaa", "repo": {"full_name": "owner/repo"}},
                "base": {"ref": "main", "sha": "bbb", "repo": {"full_name": "owner/repo"}},
            },
        }

        pr, files, skipped, reason = ingestor.ingest(payload)

        assert skipped is True
        assert "Draft PR" in reason
        assert files == []

    def test_ingest_full_loads_payload(self, tmp_path: Path, ingestor: PRIngestor, monkeypatch: pytest.MonkeyPatch) -> None:
        """End-to-end loading from GITHUB_EVENT_PATH."""
        payload = {
            "pull_request": {
                "number": 7,
                "title": "From env",
                "state": "open",
                "draft": False,
                "user": {"login": "bob"},
                "author_association": "MEMBER",
                "head": {"ref": "env", "sha": "ccc", "repo": {"full_name": "owner/repo"}},
                "base": {"ref": "main", "sha": "ddd", "repo": {"full_name": "owner/repo"}},
            },
        }
        event_file = tmp_path / "event.json"
        event_file.write_text(json.dumps(payload))
        monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))

        pr, files, skipped, reason = ingestor.ingest()

        assert pr.number == 7
        assert pr.title == "From env"
        assert skipped is False
