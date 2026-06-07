"""Repository browser tools for AI Council agents.

Tools are created via factory functions that bind a
:class:`~ai_council_review.github.browser.RepositoryBrowser` instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.tools import BaseTool, tool

if TYPE_CHECKING:
    from ai_council_review.github.browser import RepositoryBrowser


def make_repository_tools(browser: RepositoryBrowser | None) -> list[BaseTool]:
    """Create repository browser tools bound to a browser instance.

    Args:
        browser: RepositoryBrowser instance. If None, returns an empty list.

    Returns:
        List of LangChain tools.
    """
    if browser is None:
        return []

    tools: list[BaseTool] = [_make_read_file_tool(browser)]

    # list_files and find_files are only used by architecture agent currently,
    # but we include them for all tool-enabled agents for consistency.
    tools.append(_make_list_files_tool(browser))
    tools.append(_make_find_files_tool(browser))

    return tools


def _make_read_file_tool(browser: RepositoryBrowser) -> BaseTool:
    """Create a ``read_file`` tool bound to *browser*."""

    @tool
    def read_file(path: str, ref: str = "HEAD") -> str:
        """Read a file from the repository.

        Use this to check related files, documentation, tests, configuration,
        auth configs, dependency files, security policies, or any file that
        provides context for the review.

        Args:
            path: File path relative to repo root.
            ref: Git ref (branch, tag, or commit SHA). Defaults to HEAD.

        Returns:
            File contents as a string, or an error message.
        """
        result = browser.get_file(path, ref)
        if result is None:
            return f"File not found: {path} at {ref}"
        return result

    return read_file  # type: ignore[return-value]


def _make_list_files_tool(browser: RepositoryBrowser) -> BaseTool:
    """Create a ``list_files`` tool bound to *browser*."""

    @tool
    def list_files(path: str = "", ref: str = "HEAD") -> str:
        """List files in a directory.

        Use this to explore the repository structure, find tests, docs,
        configuration files, or related modules.

        Args:
            path: Directory path relative to repo root. Defaults to root.
            ref: Git ref (branch, tag, or commit SHA). Defaults to HEAD.

        Returns:
            Newline-separated list of files, or an error message.
        """
        result = browser.list_directory(path, ref)
        if result is None:
            return f"Directory not found: {path} at {ref}"
        return "\n".join(result)

    return list_files  # type: ignore[return-value]


def _make_find_files_tool(browser: RepositoryBrowser) -> BaseTool:
    """Create a ``find_files`` tool bound to *browser*."""

    @tool
    def find_files(pattern: str, ref: str = "HEAD") -> str:
        """Find files matching a glob pattern.

        Use this to locate related files, tests, documentation, or configuration
        files by pattern.

        Args:
            pattern: Glob pattern (e.g., "*.py", "tests/**/*.py").
            ref: Git ref (branch, tag, or commit SHA). Defaults to HEAD.

        Returns:
            Newline-separated list of matching files.
        """
        result = browser.find_files(pattern, ref)
        return "\n".join(result)

    return find_files  # type: ignore[return-value]
