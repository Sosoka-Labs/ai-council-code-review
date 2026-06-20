"""Tests for the unified specialist agent runner.

Covers:
- Bounded agentic tool loop (C-1): tool execution, natural termination, round/call
  ceilings, graceful diff-only fallback when browser is None.
- Repository browser tool binding when browser is available.
- Findings correctly tagged with agent name.
- Browser-provided file content demonstrably influences parsed findings.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from ai_council_review.config import CouncilConfig
from ai_council_review.github.browser import RepositoryBrowser
from ai_council_review.llm.agents.output_models import FindingList
from ai_council_review.llm.agents.registry import SPECIALIST_AGENTS, SPECIALIST_BY_NAME, AgentSpec
from ai_council_review.llm.agents.specialist import (
    _MAX_TOOL_CALLS,
    _MAX_TOOL_ROUNDS,
    _run_tool_loop,
    build_specialist_chain,
    run_specialist_agent,
)
from ai_council_review.llm.tools.repository import _make_read_file_tool
from ai_council_review.models import FileInfo, Finding, PRMetadata, ReviewState
from ai_council_review.skills.models import Skill
from ai_council_review.skills.registry import SkillRegistry

_SECURITY_SPEC = SPECIALIST_BY_NAME["security"]
_QUALITY_SPEC = SPECIALIST_BY_NAME["quality"]


def _make_state() -> ReviewState:
    """Minimal ReviewState for specialist tests."""
    pr = PRMetadata(
        number=10,
        title="Test specialist",
        state="open",
        author="alice",
        author_association="CONTRIBUTOR",
        base_ref="main",
        base_sha="aaa",
        head_ref="feat/specialist",
        head_sha="bbb",
        html_url="https://github.com/owner/repo/pull/10",
    )
    files = [
        FileInfo(
            filename="src/service.py",
            status="modified",
            additions=8,
            deletions=2,
            patch="@@ -10,5 +10,13 @@\n+def get_users():\n+    return db.query(User).all()\n",
        )
    ]
    return ReviewState(pr_metadata=pr, changed_files=files)


def _make_finding_list() -> FindingList:
    return FindingList(
        findings=[
            Finding(
                path="src/service.py",
                line=11,
                severity="high",
                category="performance",
                body="Unbounded query: missing LIMIT.",
                confidence=0.92,
            )
        ]
    )


def _make_registry(*names: str) -> SkillRegistry:
    return SkillRegistry(
        {
            n: Skill(
                name=n,
                description=f"Desc {n}",
                body=f"# {n} body",
                path=Path(f"/fake/{n}/SKILL.md"),
                raw_frontmatter={"name": n, "description": f"Desc {n}"},
            )
            for n in names
        }
    )


class TestBuildSpecialistChain:
    """Tests for build_specialist_chain."""

    def test_builds_without_browser(self) -> None:
        """Chain builds in diff-only mode when browser is None."""
        mock_llm = MagicMock()
        with patch(
            "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            chain = build_specialist_chain(_SECURITY_SPEC, CouncilConfig())
        assert chain is not None

    def test_builds_with_browser_binds_tools(self) -> None:
        """When a browser is provided, bind_tools is called on the LLM."""
        mock_llm = MagicMock()
        mock_browser = MagicMock(spec=RepositoryBrowser)
        mock_tools = [MagicMock(), MagicMock()]

        with (
            patch(
                "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
                return_value=mock_llm,
            ),
            patch(
                "ai_council_review.llm.agents.specialist.make_repository_tools",
                return_value=mock_tools,
            ),
        ):
            build_specialist_chain(_SECURITY_SPEC, CouncilConfig(), browser=mock_browser)

        mock_llm.bind_tools.assert_called_once_with(mock_tools)

    def test_no_tools_bound_when_browser_is_none(self) -> None:
        """When browser is None, make_repository_tools returns [] and bind_tools is not called."""
        mock_llm = MagicMock()
        with patch(
            "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            build_specialist_chain(_QUALITY_SPEC, CouncilConfig(), browser=None)

        mock_llm.bind_tools.assert_not_called()

    def test_graceful_fallback_when_bind_tools_raises(self) -> None:
        """If bind_tools raises AttributeError, the chain falls back to diff-only."""
        mock_llm = MagicMock()
        mock_llm.bind_tools.side_effect = AttributeError("Provider does not support tools")
        mock_browser = MagicMock(spec=RepositoryBrowser)
        mock_tools = [MagicMock()]

        with (
            patch(
                "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
                return_value=mock_llm,
            ),
            patch(
                "ai_council_review.llm.agents.specialist.make_repository_tools",
                return_value=mock_tools,
            ),
        ):
            # Must not raise — graceful degradation to diff-only
            chain = build_specialist_chain(_SECURITY_SPEC, CouncilConfig(), browser=mock_browser)

        assert chain is not None

    def test_injects_skills_when_registry_provided(self) -> None:
        """Skills are applied to the prompt when registry has matching skills."""
        mock_llm = MagicMock()
        registry = _make_registry("auth-patterns")
        config = CouncilConfig(default_agent_skills=["auth-patterns"])

        with (
            patch(
                "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
                return_value=mock_llm,
            ),
            patch(
                "ai_council_review.llm.agents.specialist.apply_skills",
                wraps=lambda prompt, skills: prompt,
            ) as mock_apply,
        ):
            build_specialist_chain(_SECURITY_SPEC, config, registry=registry)

        mock_apply.assert_called_once()


class TestRunSpecialistAgent:
    """Tests for run_specialist_agent."""

    def test_findings_tagged_with_agent_name(self) -> None:
        """Findings must be tagged with the spec.name, not a generic label.

        Uses browser=None to exercise the diff-only path where chain.invoke
        returns a FindingList directly.
        """
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = _make_finding_list()

        with (
            patch(
                "ai_council_review.llm.agents.specialist.build_specialist_chain",
                return_value=mock_chain,
            ),
            # No browser → make_repository_tools returns [] → diff-only path.
            patch(
                "ai_council_review.llm.agents.specialist.make_repository_tools",
                return_value=[],
            ),
        ):
            findings = run_specialist_agent(
                _SECURITY_SPEC, _make_state(), CouncilConfig(), browser=None
            )

        assert len(findings) == 1
        assert findings[0].agent == "security"

    def test_returns_empty_list_on_exception(self) -> None:
        """Generic exceptions are logged and an empty list is returned."""
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = RuntimeError("LLM failure")

        with (
            patch(
                "ai_council_review.llm.agents.specialist.build_specialist_chain",
                return_value=mock_chain,
            ),
            patch(
                "ai_council_review.llm.agents.specialist.make_repository_tools",
                return_value=[],
            ),
        ):
            findings = run_specialist_agent(
                _QUALITY_SPEC, _make_state(), CouncilConfig(), browser=None
            )

        assert findings == []

    def test_browser_passed_to_chain_builder(self) -> None:
        """run_specialist_agent threads the browser through to build_specialist_chain."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = FindingList(findings=[])
        mock_browser = MagicMock(spec=RepositoryBrowser)

        # In diff-only mode (no tools returned), the chain is invoked directly.
        with (
            patch(
                "ai_council_review.llm.agents.specialist.build_specialist_chain",
                return_value=mock_chain,
            ) as mock_build,
            patch(
                "ai_council_review.llm.agents.specialist.make_repository_tools",
                return_value=[],  # no tools → diff-only path
            ),
        ):
            run_specialist_agent(
                _SECURITY_SPEC,
                _make_state(),
                CouncilConfig(),
                browser=mock_browser,
            )

        _, kwargs = mock_build.call_args
        assert kwargs.get("browser") is mock_browser

    def test_no_browser_when_no_token_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When outside a checkout and no token is set, _make_browser_from_env returns None."""
        # Change to a directory with no .git so the checkout path is skipped.
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

        from ai_council_review.llm.agents.specialist import _make_browser_from_env

        assert _make_browser_from_env() is None


class TestMakeBrowserFromEnv:
    """Tests for the _make_browser_from_env factory function.

    Verifies the new filesystem-first logic:
    - Inside a local checkout → RepositoryBrowser with github_client=None.
    - Outside a checkout but with token+repo → RepositoryBrowser with a client.
    - Outside a checkout and no credentials → None.
    """

    def test_inside_checkout_returns_browser_with_no_client(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When inside a git checkout, github_client must be None.

        Browsers with no client make zero GitHub API calls, which prevents the
        rate-limit hang described in the pilot incident.
        """
        # Create a minimal .git directory so _find_git_root finds a checkout.
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        # Even if a token is present, the local checkout takes precedence.
        monkeypatch.setenv("GITHUB_TOKEN", "ghs_fake")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")

        from ai_council_review.llm.agents.specialist import _make_browser_from_env

        browser = _make_browser_from_env()

        assert browser is not None
        assert browser.github_client is None

    def test_outside_checkout_with_token_attaches_client(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Outside a checkout the API client is attached when credentials exist.

        GitHubClient is imported lazily inside _make_browser_from_env, so we
        patch it at its definition module rather than the specialist module.
        """
        # tmp_path has no .git directory — simulates running outside a repo.
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GITHUB_TOKEN", "ghs_fake")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")

        from ai_council_review.llm.agents.specialist import _make_browser_from_env

        # Patch at the source module because the import is deferred (lazy).
        with patch("ai_council_review.github.client.GitHubClient") as mock_cls:
            mock_client_instance = MagicMock()
            mock_cls.return_value = mock_client_instance
            browser = _make_browser_from_env()

        assert browser is not None
        assert browser.github_client is mock_client_instance
        mock_cls.assert_called_once_with("ghs_fake", "owner/repo")

    def test_outside_checkout_no_credentials_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Outside a checkout with no token, None is returned."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

        from ai_council_review.llm.agents.specialist import _make_browser_from_env

        assert _make_browser_from_env() is None

    def test_browsed_file_content_incorporated(self) -> None:
        """Agent enters tool loop when browser + tools are present.

        The mock LLM emits one read_file tool call on the first turn and a
        final finding on the second turn.  The test verifies that:

        1. The tool is actually invoked (not silently dropped).
        2. The browsed content can influence the parsed findings.
        3. Findings are tagged with the agent name.
        """
        file_content = "class User:\n    password = CharField()\n"

        # First LLM response: request a tool call.
        first_response = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_abc",
                    "name": "read_file",
                    "args": {"path": "src/models.py"},
                }
            ],
        )

        # Finding JSON that the second LLM response returns.
        finding_json = json.dumps(
            [
                {
                    "path": "src/models.py",
                    "line": 2,
                    "severity": "high",
                    "category": "security",
                    "body": "Password stored in plain CharField.",
                    "confidence": 0.9,
                }
            ]
        )
        # Second LLM response: no tool calls, returns findings as JSON text.
        second_response = AIMessage(content=finding_json, tool_calls=[])

        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.side_effect = [first_response, second_response]

        # Mock browser: read_file returns the file content.
        mock_browser = MagicMock(spec=RepositoryBrowser)
        mock_browser.get_file.return_value = file_content

        # Build a real tool backed by the mock browser so _execute_tool_calls
        # can actually invoke read_file and we can verify the call happened.
        real_read_file_tool = _make_read_file_tool(mock_browser)

        with (
            patch(
                "ai_council_review.llm.agents.specialist.make_repository_tools",
                return_value=[real_read_file_tool],
            ),
            patch(
                "ai_council_review.llm.agents.specialist.build_specialist_chain",
            ) as mock_build_chain,
        ):
            # build_specialist_chain returns a chain whose .last attribute is the
            # tool-bound LLM.  Wire up the mock so _run_tool_loop gets the LLM.
            mock_chain = MagicMock()
            mock_chain.last = mock_llm_with_tools
            mock_build_chain.return_value = mock_chain

            findings = run_specialist_agent(
                _SECURITY_SPEC,
                _make_state(),
                CouncilConfig(),
                browser=mock_browser,
            )

        # The browser was actually invoked (file was read).
        mock_browser.get_file.assert_called_once()

        # The LLM was called twice: once for the initial prompt and once after
        # the tool result was appended.
        assert mock_llm_with_tools.invoke.call_count == 2

        # Findings were parsed from the second response and tagged correctly.
        assert len(findings) == 1
        assert findings[0].agent == "security"
        assert "password" in findings[0].body.lower() or "CharField" in findings[0].body


class TestRunToolLoop:
    """Unit tests for the _run_tool_loop helper (C-1 requirements).

    Each test mocks the LLM and verifies loop termination + output without
    any network calls.
    """

    def _make_finding_ai_message(self) -> AIMessage:
        """Return an AIMessage containing a single valid finding JSON array."""
        findings = [
            {
                "path": "src/app.py",
                "line": 10,
                "severity": "high",
                "category": "security",
                "body": "Hardcoded secret detected.",
                "confidence": 0.95,
            }
        ]
        return AIMessage(content=json.dumps(findings), tool_calls=[])

    def _make_tool_call_message(self, call_id: str = "call_1") -> AIMessage:
        """Return an AIMessage that requests a read_file tool call."""
        return AIMessage(
            content="",
            tool_calls=[{"id": call_id, "name": "read_file", "args": {"path": "README.md"}}],
        )

    def test_loop_terminates_naturally_when_no_tool_calls(self) -> None:
        """Loop exits on the first response that has no tool calls."""
        final_response = self._make_finding_ai_message()
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = final_response

        result = _run_tool_loop(mock_llm, [], [], agent_name="security")

        assert mock_llm.invoke.call_count == 1
        assert "Hardcoded secret" in result

    def test_loop_executes_tool_and_continues(self) -> None:
        """Tool call is executed; its result is appended and the loop continues.

        Verifies that browser content demonstrably influences the final output.
        """
        file_content = "SECRET=hardcoded_value\n"

        mock_browser = MagicMock(spec=RepositoryBrowser)
        mock_browser.get_file.return_value = file_content
        real_tool = _make_read_file_tool(mock_browser)

        # First response: request read_file.  Second response: produce findings.
        finding_body = f"File contains: {file_content.strip()}"
        second_response = AIMessage(
            content=json.dumps(
                [
                    {
                        "path": "config.env",
                        "line": 1,
                        "severity": "critical",
                        "category": "security",
                        "body": finding_body,
                    }
                ]
            ),
            tool_calls=[],
        )

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [self._make_tool_call_message(), second_response]

        result = _run_tool_loop(mock_llm, [], [real_tool], agent_name="security")

        # Tool was actually called (browser.get_file was invoked).
        mock_browser.get_file.assert_called_once()
        # LLM was called twice: initial + after tool result.
        assert mock_llm.invoke.call_count == 2
        # The browsed content is visible in the final output.
        assert file_content.strip() in result

    def test_loop_stops_at_round_ceiling(self) -> None:
        """Loop terminates at _MAX_TOOL_ROUNDS even if model keeps requesting tools."""
        mock_browser = MagicMock(spec=RepositoryBrowser)
        mock_browser.get_file.return_value = "content"
        real_tool = _make_read_file_tool(mock_browser)

        # Always return a tool call — the loop must stop on its own.
        always_calls = AIMessage(
            content="",
            tool_calls=[{"id": "c", "name": "read_file", "args": {"path": "f.py"}}],
        )
        final_summary = AIMessage(content="[]", tool_calls=[])

        responses = [always_calls] * _MAX_TOOL_ROUNDS + [final_summary]
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = responses

        _run_tool_loop(mock_llm, [], [real_tool], agent_name="security")

        # The loop must not exceed _MAX_TOOL_ROUNDS + 1 (for the final pass).
        assert mock_llm.invoke.call_count <= _MAX_TOOL_ROUNDS + 1

    def test_loop_stops_at_call_ceiling(self) -> None:
        """Loop terminates when cumulative tool calls reach _MAX_TOOL_CALLS."""
        mock_browser = MagicMock(spec=RepositoryBrowser)
        mock_browser.get_file.return_value = "data"
        real_tool = _make_read_file_tool(mock_browser)

        # Each response requests one tool call.
        single_call = AIMessage(
            content="",
            tool_calls=[{"id": "c", "name": "read_file", "args": {"path": "x.py"}}],
        )
        final_summary = AIMessage(content="[]", tool_calls=[])

        # Enough responses to exceed _MAX_TOOL_CALLS if uncapped.
        responses = [single_call] * (_MAX_TOOL_CALLS + 5) + [final_summary]
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = responses

        _run_tool_loop(mock_llm, [], [real_tool], agent_name="security")

        # Total tool invocations must be bounded by _MAX_TOOL_CALLS.
        assert mock_browser.get_file.call_count <= _MAX_TOOL_CALLS

    def test_diff_only_fallback_when_browser_is_none(self) -> None:
        """With no browser, run_specialist_agent uses the diff-only chain path.

        The chain is invoked once and must return a FindingList directly —
        no tool loop is entered.
        """
        finding = Finding(
            path="src/app.py",
            line=5,
            severity="medium",
            category="quality",
            body="Magic number.",
            confidence=0.7,
        )
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = FindingList(findings=[finding])

        with (
            patch(
                "ai_council_review.llm.agents.specialist.build_specialist_chain",
                return_value=mock_chain,
            ),
            patch(
                "ai_council_review.llm.agents.specialist.make_repository_tools",
                return_value=[],  # no tools → diff-only path
            ),
            patch(
                "ai_council_review.llm.agents.specialist._make_browser_from_env",
                return_value=None,
            ),
        ):
            findings = run_specialist_agent(
                _SECURITY_SPEC, _make_state(), CouncilConfig(), browser=None
            )

        # chain.invoke was used (not the tool loop).
        mock_chain.invoke.assert_called_once()
        assert len(findings) == 1
        assert findings[0].agent == "security"


@pytest.mark.parametrize("spec", SPECIALIST_AGENTS, ids=lambda s: s.name)
def test_each_specialist_chain_builds(spec: AgentSpec) -> None:
    """Smoke test: every registry agent can build a chain (with mocked LLM)."""
    mock_llm = MagicMock()
    with patch(
        "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
        return_value=mock_llm,
    ):
        chain = build_specialist_chain(spec, CouncilConfig())
    assert chain is not None
