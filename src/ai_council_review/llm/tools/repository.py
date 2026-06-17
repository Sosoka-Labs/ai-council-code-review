"""Repository browser tools for AI Council agents.

Tools are created via factory functions that bind a
:class:`~ai_council_review.github.browser.RepositoryBrowser` instance.

Security notes:
    * ``read_file`` truncates responses at ``_MAX_FILE_BYTES`` to prevent large
      binary or generated files from exhausting the LLM context.
    * The agentic tool loop in ``specialist.py`` enforces a ceiling on the total
      number of tool calls per agent (``_MAX_TOOL_CALLS``), so the tools below
      do not need to duplicate that check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from langchain_core.tools import BaseTool, tool

if TYPE_CHECKING:
    from ai_council_review.github.browser import RepositoryBrowser

logger = structlog.get_logger()

# Hard cap on ``read_file`` response size.  Files larger than this are truncated
# with a clear marker so the model knows the content is incomplete.
_MAX_FILE_BYTES: int = 100_000


def make_repository_tools(browser: RepositoryBrowser | None) -> list[BaseTool]:
    """Create repository browser tools bound to a browser instance.

    Args:
        browser: RepositoryBrowser instance. If None, returns an empty list.

    Returns:
        List of LangChain tools: ``read_file``, ``list_files``, ``find_files``.
    """
    if browser is None:
        return []

    tools: list[BaseTool] = [_make_read_file_tool(browser)]

    # list_files and find_files are useful for all tool-enabled agents, not
    # just architecture, so we include them for consistency.
    tools.append(_make_list_files_tool(browser))
    tools.append(_make_find_files_tool(browser))

    return tools


def _make_read_file_tool(browser: RepositoryBrowser) -> BaseTool:
    """Create a ``read_file`` tool bound to *browser*.

    The tool truncates file contents at ``_MAX_FILE_BYTES`` and appends a clear
    marker so the model knows the file was cut short.
    """

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
            File contents as a string (truncated at 100 000 bytes), or an error
            message when the file does not exist.
        """
        result = browser.get_file(path, ref)
        if result is None:
            return f"File not found: {path} at {ref}"
        if len(result) > _MAX_FILE_BYTES:
            logger.debug(
                "read_file truncating large file",
                path=path,
                original_bytes=len(result),
                cap_bytes=_MAX_FILE_BYTES,
            )
            result = result[:_MAX_FILE_BYTES] + (
                f"\n\n[... truncated at {_MAX_FILE_BYTES} bytes — "
                "file continues beyond this point ...]"
            )
        return result

    return read_file


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

    return list_files


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

    return find_files
