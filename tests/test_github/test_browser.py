"""Tests for ai_council_review.github.browser."""

from __future__ import annotations

from subprocess import CalledProcessError
from unittest.mock import MagicMock

from pytest_mock import MockerFixture

from ai_council_review.github.browser import RepositoryBrowser


class TestRepositoryBrowser:
    """Tests for RepositoryBrowser."""

    def test_init_defaults(self) -> None:
        """Test default initialization."""
        browser = RepositoryBrowser()
        assert browser.repo_path is not None
        assert browser.github_client is None
        assert browser.api_calls == 0

    def test_init_with_params(self) -> None:
        """Test initialization with parameters."""
        client = MagicMock()
        browser = RepositoryBrowser(repo_path="/tmp/repo", github_client=client)
        assert str(browser.repo_path) == "/tmp/repo"
        assert browser.github_client is client

    def test_get_file_local(self, mocker: MockerFixture) -> None:
        """Test get_file via local git."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.return_value = MagicMock(stdout="file content", returncode=0)

        browser = RepositoryBrowser(repo_path="/tmp/repo")
        result = browser.get_file("src/main.py", "HEAD")
        assert result == "file content"
        mock_run.assert_called_once()
        args = mock_run.call_args.args[0]
        assert args[0] == "git"
        assert args[1] == "show"
        assert args[2] == "HEAD:src/main.py"

    def test_get_file_local_not_found(self, mocker: MockerFixture) -> None:
        """Test get_file returns None when local file not found."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "git")

        browser = RepositoryBrowser(repo_path="/tmp/repo")
        result = browser.get_file("missing.py", "HEAD")
        assert result is None

    def test_get_file_api(self, mocker: MockerFixture) -> None:
        """Test _get_file_api via GitHub client."""
        client = MagicMock()
        client.get_file_contents.return_value = "api content"
        browser = RepositoryBrowser(github_client=client)
        result = browser._get_file_api("src/main.py", "HEAD")
        assert result == "api content"
        client.get_file_contents.assert_called_once_with("src/main.py", "HEAD")
        assert browser.api_calls == 1

    def test_get_file_api_fallback(self, mocker: MockerFixture) -> None:
        """Test get_file falls back to API when local fails."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "git")

        client = MagicMock()
        client.get_file_contents.return_value = "fallback content"
        browser = RepositoryBrowser(github_client=client)
        result = browser.get_file("src/main.py", "HEAD")
        assert result == "fallback content"
        client.get_file_contents.assert_called_once_with("src/main.py", "HEAD")

    def test_get_file_api_no_client(self) -> None:
        """Test _get_file_api returns None when no client."""
        browser = RepositoryBrowser()
        result = browser._get_file_api("src/main.py", "HEAD")
        assert result is None

    def test_get_file_no_local_no_client(self, mocker: MockerFixture) -> None:
        """Test get_file returns None when local and API both unavailable."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "git")

        browser = RepositoryBrowser()
        result = browser.get_file("src/main.py", "HEAD")
        assert result is None

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

    def test_get_file_at_base(self, mocker: MockerFixture) -> None:
        """Test get_file_at_base wrapper."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.return_value = MagicMock(stdout="base content", returncode=0)

        browser = RepositoryBrowser(repo_path="/tmp/repo")
        result = browser.get_file_at_base("src/main.py", "main")
        assert result == "base content"

    def test_get_file_at_head(self, mocker: MockerFixture) -> None:
        """Test get_file_at_head wrapper."""
        mock_run = mocker.patch("ai_council_review.github.browser.subprocess.run")
        mock_run.return_value = MagicMock(stdout="head content", returncode=0)

        browser = RepositoryBrowser(repo_path="/tmp/repo")
        result = browser.get_file_at_head("src/main.py")
        assert result == "head content"
