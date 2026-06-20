"""Tests for ai_council_review.github.browser."""

from __future__ import annotations

from pathlib import Path
from subprocess import CalledProcessError
from unittest.mock import MagicMock, patch

from pytest_mock import MockerFixture

from ai_council_review.github.browser import (
    RepositoryBrowser,
    _is_head_ref,
    _is_within_repo,
)


class TestHelpers:
    """Unit tests for module-level helper functions."""

    def test_is_head_ref_with_head_uppercase(self) -> None:
        assert _is_head_ref("HEAD") is True

    def test_is_head_ref_with_empty_string(self) -> None:
        assert _is_head_ref("") is True

    def test_is_head_ref_with_lowercase_head(self) -> None:
        # Git refs are case-sensitive; lowercase "head" is not the working tree.
        assert _is_head_ref("head") is False

    def test_is_head_ref_with_branch_name(self) -> None:
        assert _is_head_ref("main") is False

    def test_is_head_ref_with_sha(self) -> None:
        assert _is_head_ref("abc1234") is False

    def test_is_within_repo_inside(self, tmp_path: Path) -> None:
        target = (tmp_path / "src" / "main.py").resolve()
        assert _is_within_repo(target, tmp_path.resolve()) is True

    def test_is_within_repo_at_root(self, tmp_path: Path) -> None:
        # The repo root itself is considered "within"
        assert _is_within_repo(tmp_path.resolve(), tmp_path.resolve()) is True

    def test_is_within_repo_escapes(self, tmp_path: Path) -> None:
        target = (tmp_path.parent / "other.py").resolve()
        assert _is_within_repo(target, tmp_path.resolve()) is False


class TestRepositoryBrowser:
    """Tests for RepositoryBrowser."""

    def test_init_defaults(self) -> None:
        """Test default initialization."""
        browser = RepositoryBrowser()
        assert browser.repo_path is not None
        assert browser.github_client is None
        assert browser.api_calls == 0

    def test_init_with_params(self, tmp_path: Path) -> None:
        """Test initialization with parameters."""
        client = MagicMock()
        browser = RepositoryBrowser(repo_path=tmp_path, github_client=client)
        assert browser.repo_path == tmp_path.resolve()
        assert browser.github_client is client

    def test_init_resolves_repo_path(self, tmp_path: Path) -> None:
        """repo_path is always stored as a resolved absolute Path."""
        browser = RepositoryBrowser(repo_path=str(tmp_path))
        assert browser.repo_path == tmp_path.resolve()

    # ------------------------------------------------------------------
    # Filesystem (working-tree) reads for HEAD ref
    # ------------------------------------------------------------------

    def test_get_file_head_reads_from_filesystem(self, tmp_path: Path) -> None:
        """get_file("HEAD") reads from disk — no subprocess, no API call."""
        (tmp_path / "src").mkdir()
        target = tmp_path / "src" / "main.py"
        target.write_text("filesystem content")

        browser = RepositoryBrowser(repo_path=tmp_path)
        with patch("ai_council_review.github.browser.subprocess.run") as mock_run:
            result = browser.get_file("src/main.py", "HEAD")

        assert result == "filesystem content"
        mock_run.assert_not_called()

    def test_get_file_empty_ref_reads_from_filesystem(self, tmp_path: Path) -> None:
        """get_file with empty ref also uses filesystem path."""
        (tmp_path / "a.py").write_text("empty ref content")
        browser = RepositoryBrowser(repo_path=tmp_path)
        result = browser.get_file("a.py", "")
        assert result == "empty ref content"

    def test_get_file_none_ref_reads_from_filesystem(self, tmp_path: Path) -> None:
        """Passing ref=None is treated the same as HEAD."""
        (tmp_path / "b.py").write_text("none ref content")
        browser = RepositoryBrowser(repo_path=tmp_path)
        result = browser.get_file("b.py", ref=None)
        assert result == "none ref content"

    def test_get_file_head_missing_returns_none(self, tmp_path: Path) -> None:
        """Filesystem miss for HEAD ref returns None (no fallback to git/API)."""
        browser = RepositoryBrowser(repo_path=tmp_path)
        with patch("ai_council_review.github.browser.subprocess.run") as mock_run:
            result = browser.get_file("nonexistent.py", "HEAD")
        assert result is None
        mock_run.assert_not_called()

    def test_get_file_head_falls_back_to_api_when_client_present(self, tmp_path: Path) -> None:
        """When filesystem miss + client attached, API is the last resort."""
        client = MagicMock()
        client.get_file_contents.return_value = "api content"
        browser = RepositoryBrowser(repo_path=tmp_path, github_client=client)

        result = browser.get_file("missing.py", "HEAD")

        assert result == "api content"
        client.get_file_contents.assert_called_once_with("missing.py", "HEAD")

    # ------------------------------------------------------------------
    # Path-traversal guard
    # ------------------------------------------------------------------

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        """A path that escapes repo_path returns None."""
        browser = RepositoryBrowser(repo_path=tmp_path)
        result = browser._get_file_filesystem("../../etc/passwd")
        assert result is None

    def test_path_traversal_blocked_via_get_file(self, tmp_path: Path) -> None:
        """get_file with a traversal path returns None for HEAD ref."""
        browser = RepositoryBrowser(repo_path=tmp_path)
        result = browser.get_file("../../etc/passwd", "HEAD")
        assert result is None

    # ------------------------------------------------------------------
    # Non-HEAD refs use git show
    # ------------------------------------------------------------------

    def test_get_file_explicit_ref_uses_git_show(self, mocker: MockerFixture) -> None:
        """Explicit branch ref triggers git show (not filesystem)."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.return_value = MagicMock(stdout="branch content", returncode=0)

        browser = RepositoryBrowser(repo_path="/tmp/repo")
        result = browser.get_file("src/main.py", "main")

        assert result == "branch content"
        args = mock_run.call_args.args[0]
        assert args == ["git", "show", "main:src/main.py"]

    def test_get_file_sha_ref_uses_git_show(self, mocker: MockerFixture) -> None:
        """A commit SHA ref goes through git show."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.return_value = MagicMock(stdout="sha content", returncode=0)

        browser = RepositoryBrowser(repo_path="/tmp/repo")
        result = browser.get_file("README.md", "abc1234")

        assert result == "sha content"
        args = mock_run.call_args.args[0]
        assert args == ["git", "show", "abc1234:README.md"]

    def test_get_file_explicit_ref_git_miss_falls_back_to_api(self, mocker: MockerFixture) -> None:
        """git show miss for a non-HEAD ref falls back to the API."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "git")

        client = MagicMock()
        client.get_file_contents.return_value = "api fallback"
        browser = RepositoryBrowser(repo_path="/tmp/repo", github_client=client)

        result = browser.get_file("src/main.py", "main")

        assert result == "api fallback"
        client.get_file_contents.assert_called_once_with("src/main.py", "main")

    def test_get_file_explicit_ref_no_client_returns_none(self, mocker: MockerFixture) -> None:
        """git show miss + no client returns None."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "git")

        browser = RepositoryBrowser(repo_path="/tmp/repo")
        result = browser.get_file("src/main.py", "main")

        assert result is None

    # ------------------------------------------------------------------
    # _get_file_api direct tests
    # ------------------------------------------------------------------

    def test_get_file_api(self) -> None:
        """_get_file_api delegates to the GitHub client."""
        client = MagicMock()
        client.get_file_contents.return_value = "api content"
        browser = RepositoryBrowser(github_client=client)
        result = browser._get_file_api("src/main.py", "HEAD")
        assert result == "api content"
        client.get_file_contents.assert_called_once_with("src/main.py", "HEAD")
        assert browser.api_calls == 1

    def test_get_file_api_no_client(self) -> None:
        """_get_file_api returns None when no client is attached."""
        browser = RepositoryBrowser()
        result = browser._get_file_api("src/main.py", "HEAD")
        assert result is None

    # ------------------------------------------------------------------
    # Convenience wrappers
    # ------------------------------------------------------------------

    def test_get_file_at_base(self, mocker: MockerFixture) -> None:
        """get_file_at_base uses git show for base ref."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.return_value = MagicMock(stdout="base content", returncode=0)

        browser = RepositoryBrowser(repo_path="/tmp/repo")
        result = browser.get_file_at_base("src/main.py", "main")

        assert result == "base content"

    def test_get_file_at_head(self, tmp_path: Path) -> None:
        """get_file_at_head reads from the filesystem."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("head content")

        browser = RepositoryBrowser(repo_path=tmp_path)
        result = browser.get_file_at_head("src/main.py")

        assert result == "head content"

    # ------------------------------------------------------------------
    # list_directory / find_files / file_exists (unchanged behaviour)
    # ------------------------------------------------------------------

    def test_list_directory(self, mocker: MockerFixture) -> None:
        """Test list_directory."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.return_value = MagicMock(stdout="a.py\nb.py\n", returncode=0)

        browser = RepositoryBrowser(repo_path="/tmp/repo")
        result = browser.list_directory("src", "HEAD")
        assert result == ["a.py", "b.py"]

    def test_list_directory_not_found(self, mocker: MockerFixture) -> None:
        """Test list_directory returns None when directory not found."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "git")

        browser = RepositoryBrowser(repo_path="/tmp/repo")
        result = browser.list_directory("missing", "HEAD")
        assert result is None

    def test_find_files(self, mocker: MockerFixture) -> None:
        """Test find_files."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.return_value = MagicMock(
            stdout="src/a.py\nsrc/b.py\ntests/test_a.py\n", returncode=0
        )

        browser = RepositoryBrowser(repo_path="/tmp/repo")
        result = browser.find_files("src/*.py", "HEAD")
        assert result == ["src/a.py", "src/b.py"]

    def test_find_files_git_fails(self, mocker: MockerFixture) -> None:
        """Test find_files returns empty list when git fails."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "git")

        browser = RepositoryBrowser(repo_path="/tmp/repo")
        result = browser.find_files("*.py", "HEAD")
        assert result == []

    def test_file_exists(self, mocker: MockerFixture) -> None:
        """Test file_exists when file is present."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        browser = RepositoryBrowser(repo_path="/tmp/repo")
        result = browser.file_exists("src/main.py", "HEAD")
        assert result is True

    def test_file_exists_not_found(self, mocker: MockerFixture) -> None:
        """Test file_exists when file is absent."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "git")

        browser = RepositoryBrowser(repo_path="/tmp/repo")
        result = browser.file_exists("missing.py", "HEAD")
        assert result is False

    # ------------------------------------------------------------------
    # No API when no client (regression guard)
    # ------------------------------------------------------------------

    def test_get_file_no_client_no_api_call(self, tmp_path: Path) -> None:
        """With github_client=None, api_calls is never incremented."""
        browser = RepositoryBrowser(repo_path=tmp_path, github_client=None)
        browser.get_file("nonexistent.py", "HEAD")
        assert browser.api_calls == 0
