"""Repository browser tools for AI Council agents.

Each tool is a LangChain :func:`~langchain_core.tools.tool` decorated function
that operates on a :class:`~ai_council_review.github.browser.RepositoryBrowser`.

Usage::

    from ai_council_review.github.browser import RepositoryBrowser
    from ai_council_review.tools.repository import make_repository_tools

    browser = RepositoryBrowser(...)
    tools = make_repository_tools(browser)
"""

from __future__ import annotations

from ai_council_review.tools.repository import make_repository_tools

__all__ = ["make_repository_tools"]
