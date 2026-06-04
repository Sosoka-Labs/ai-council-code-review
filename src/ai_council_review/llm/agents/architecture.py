"""Architecture agent — focused on cross-file impact, API design, and structural consistency."""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.tools import BaseTool

from ai_council_review.github.browser import RepositoryBrowser
from ai_council_review.llm.agents.base import BaseAgent
from ai_council_review.llm.prompts.loader import load_prompt
from ai_council_review.models import ReviewState

logger = structlog.get_logger()


class ArchitectureAgent(BaseAgent):
    """Architecture-focused agent that reviews for cross-file impact and system-level concerns."""

    def __init__(self, config: Any, browser: RepositoryBrowser | None = None) -> None:
        """Initialize the architecture agent.

        Args:
            config: CouncilConfig instance.
            browser: RepositoryBrowser for cross-file awareness.
        """
        super().__init__("architecture", config)
        self.browser = browser

    def get_tools(self) -> list[BaseTool]:
        """Return tools available to the architecture agent.

        Returns:
            List of tools. Includes file_read tool for checking docs,
            related files, configuration, and API surfaces.
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

            def list_files(path: str = "", ref: str = "HEAD") -> str:
                """List files in a directory.

                Args:
                    path: Directory path.
                    ref: Git ref.

                Returns:
                    List of files.
                """
                if self.browser is None:
                    return "Browser not available"
                result = self.browser.list_directory(path, ref)
                if result is None:
                    return f"Directory not found: {path} at {ref}"
                return "\n".join(result)

            def find_files(pattern: str, ref: str = "HEAD") -> str:
                """Find files matching a pattern.

                Args:
                    pattern: Glob pattern.
                    ref: Git ref.

                Returns:
                    List of matching files.
                """
                if self.browser is None:
                    return "Browser not available"
                result = self.browser.find_files(pattern, ref)
                return "\n".join(result)

            tools.append(
                StructuredTool.from_function(
                    name="read_file",
                    func=read_file,
                    description="Read a file from the repository. Use this to check docs, related files, configuration, or API surfaces.",
                    args_schema=ReadFileInput,
                )
            )
            tools.append(
                StructuredTool.from_function(
                    name="list_files",
                    func=list_files,
                    description="List files in a directory. Use this to explore the repository structure.",
                    args_schema=ReadFileInput,
                )
            )
            tools.append(
                StructuredTool.from_function(
                    name="find_files",
                    func=find_files,
                    description="Find files matching a pattern. Use this to locate related files, tests, or documentation.",
                    args_schema=ReadFileInput,
                )
            )

        return tools

    def get_prompt(self, state: ReviewState) -> str:
        """Render the architecture prompt.

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
            "architecture",
            repo=repo,
            pr_number=pr_number,
            pr_title=pr_title,
            changed_files=file_list,
            diff=diff_text,
        )

    def run(self, state: ReviewState) -> Any:
        """Run the architecture agent.

        Args:
            state: Current review state.

        Returns:
            List of findings.
        """
        logger.info("Architecture agent starting")
        prompt = self.get_prompt(state)
        tools = self.get_tools()

        try:
            model = self.llm.bind_tools(tools) if tools else self.llm
            response = model.invoke(prompt)
            text = str(response.content)
            return self._parse_findings(text)
        except Exception as e:
            logger.error("Architecture agent failed", error=str(e))
            return []
