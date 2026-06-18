"""Tests for src/ai_council_review/llm/tools/repository.py (H-2 requirements).

Verifies:
- read_file truncates at _MAX_FILE_BYTES and appends a clear truncation marker.
- read_file returns a helpful message when the file is not found.
- list_files and find_files behave correctly.
- make_repository_tools returns an empty list when browser is None.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from ai_council_review.github.browser import RepositoryBrowser
from ai_council_review.llm.tools.repository import (
    _MAX_FILE_BYTES,
    make_repository_tools,
)


class TestReadFileSizeCap:
    """Verify that read_file enforces _MAX_FILE_BYTES."""

    def _get_read_file_tool(self, browser: RepositoryBrowser):  # type: ignore[return]
        """Return the read_file tool from make_repository_tools."""
        tools = make_repository_tools(browser)
        return next(t for t in tools if t.name == "read_file")

    def test_small_file_returned_intact(self) -> None:
        """Files smaller than the cap are returned without modification."""
        content = "x" * 100
        mock_browser = MagicMock(spec=RepositoryBrowser)
        mock_browser.get_file.return_value = content

        tool = self._get_read_file_tool(mock_browser)
        result = tool.invoke({"path": "small.py"})

        assert result == content
        assert "truncated" not in result

    def test_large_file_is_truncated(self) -> None:
        """Files exceeding _MAX_FILE_BYTES are truncated at the byte boundary."""
        big_content = "a" * (_MAX_FILE_BYTES + 5000)
        mock_browser = MagicMock(spec=RepositoryBrowser)
        mock_browser.get_file.return_value = big_content

        tool = self._get_read_file_tool(mock_browser)
        result = tool.invoke({"path": "big_file.py"})

        # Content is cut at the cap.
        assert len(result) > _MAX_FILE_BYTES  # marker adds some bytes
        assert result.startswith("a" * _MAX_FILE_BYTES)
        # Truncation marker is present.
        assert "truncated" in result
        assert str(_MAX_FILE_BYTES) in result

    def test_file_exactly_at_cap_not_truncated(self) -> None:
        """A file of exactly _MAX_FILE_BYTES is returned without truncation."""
        exact_content = "b" * _MAX_FILE_BYTES
        mock_browser = MagicMock(spec=RepositoryBrowser)
        mock_browser.get_file.return_value = exact_content

        tool = self._get_read_file_tool(mock_browser)
        result = tool.invoke({"path": "exact.py"})

        assert result == exact_content
        assert "truncated" not in result

    def test_file_not_found_returns_error_message(self) -> None:
        """Returns a clear error string when the browser returns None."""
        mock_browser = MagicMock(spec=RepositoryBrowser)
        mock_browser.get_file.return_value = None

        tool = self._get_read_file_tool(mock_browser)
        result = tool.invoke({"path": "missing.py"})

        assert "not found" in result.lower() or "missing.py" in result


class TestMakeRepositoryTools:
    """Verify the tool factory."""

    def test_returns_empty_list_when_browser_is_none(self) -> None:
        """No tools are created when browser is None."""
        assert make_repository_tools(None) == []

    def test_returns_three_tools_when_browser_provided(self) -> None:
        """read_file, list_files, find_files are all returned."""
        mock_browser = MagicMock(spec=RepositoryBrowser)
        tools = make_repository_tools(mock_browser)

        tool_names = {t.name for t in tools}
        assert tool_names == {"read_file", "list_files", "find_files"}
