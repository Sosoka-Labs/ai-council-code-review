"""Generalist agent — single agent that reviews all aspects of a PR."""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.tools import BaseTool

from ai_council_review.github.browser import RepositoryBrowser
from ai_council_review.llm.agents.base import BaseAgent
from ai_council_review.llm.prompts.loader import load_prompt
from ai_council_review.models import Finding, ReviewState

logger = structlog.get_logger()


class GeneralistAgent(BaseAgent):
    """A generalist agent that reviews code quality, security, architecture, and docs."""

    def __init__(self, config: Any, browser: RepositoryBrowser | None = None) -> None:
        """Initialize the generalist agent.

        Args:
            config: CouncilConfig instance.
            browser: RepositoryBrowser for cross-file awareness.
        """
        super().__init__("generalist", config)
        self.browser = browser

    def get_tools(self) -> list[BaseTool]:
        """Return tools available to the generalist agent.

        Returns:
            List of tools. If a browser is configured, includes a file_read tool.
        """
        tools: list[BaseTool] = []

        if self.browser is not None:
            from langchain_core.tools import StructuredTool
            from pydantic import BaseModel, Field

            class ReadFileInput(BaseModel):
                """Input for the read_file tool."""

                path: str = Field(description="Path to the file to read")
                ref: str = Field(default="HEAD", description="Git ref (branch, tag, or commit SHA)")

            def read_file(path: str, ref: str = "HEAD") -> str:
                """Read a file from the repository.

                Args:
                    path: File path relative to repo root.
                    ref: Git ref.

                Returns:
                    File contents or error message.
                """
                if self.browser is None:
                    return "Browser not available"
                result = self.browser.get_file(path, ref)
                if result is None:
                    return f"File not found: {path} at {ref}"
                return result

            tools.append(
                StructuredTool.from_function(
                    name="read_file",
                    func=read_file,
                    description="Read a file from the repository. Use this to check related files, documentation, tests, or configuration for cross-file consistency.",
                    args_schema=ReadFileInput,
                )
            )

        return tools

    def get_prompt(self, state: ReviewState) -> str:
        """Render the generalist prompt.

        Args:
            state: Current review state.

        Returns:
            Rendered prompt text.
        """
        changed_files = state.changed_files
        file_list = "\n".join(
            f"- {f.filename} ({f.status}, +{f.additions}/-{f.deletions})" for f in changed_files
        )

        # Build diff text
        diff_parts: list[str] = []
        for f in changed_files:
            if f.patch:
                diff_parts.append(f"=== {f.filename} ===\n{f.patch}")
        diff_text = "\n\n".join(diff_parts)

        pr = state.pr_metadata
        pr_title = pr.title if pr else ""
        pr_number = pr.number if pr else 0
        repo = pr.html_url if pr else ""

        return load_prompt(
            "generalist",
            repo=repo,
            pr_number=pr_number,
            pr_title=pr_title,
            changed_files=file_list,
            diff=diff_text,
        )

    def run(self, state: ReviewState) -> list[Finding]:
        """Run the generalist agent.

        Args:
            state: Current review state.

        Returns:
            List of findings.
        """
        logger.info("Generalist agent starting")
        prompt = self.get_prompt(state)
        tools = self.get_tools()

        try:
            model = self.llm.bind_tools(tools) if tools else self.llm

            response = model.invoke(prompt)
            text = str(response.content)
            return self._parse_findings(text)
        except Exception as e:
            logger.error("Generalist agent failed", error=str(e))
            return []

    def _parse_findings(self, text: str) -> list[Finding]:
        """Parse findings from agent output.

        Args:
            text: Raw agent output.

        Returns:
            List of findings.
        """
        import json
        import re

        # Try to extract JSON array
        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return [Finding(**item) for item in data if isinstance(item, dict)]
            except Exception:
                pass

        # Fallback: try to parse line-by-line comments
        findings: list[Finding] = []
        return findings
