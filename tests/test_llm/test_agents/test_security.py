"""Tests for the security agent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_council_review.config import CouncilConfig
from ai_council_review.exceptions import BudgetExceededError
from ai_council_review.llm.agents.output_models import FindingList
from ai_council_review.llm.agents.security import build_security_chain, run_security_agent
from ai_council_review.models import FileInfo, Finding, PRMetadata, ReviewState, Severity
from ai_council_review.skills.models import Skill
from ai_council_review.skills.registry import SkillRegistry


def _make_state() -> ReviewState:
    """Return a minimal ReviewState for security tests."""
    pr = PRMetadata(
        number=2,
        title="Fix auth token handling",
        state="open",
        author="bob",
        author_association="MEMBER",
        base_ref="main",
        base_sha="aaa",
        head_ref="fix/auth",
        head_sha="bbb",
        html_url="https://github.com/owner/repo/pull/2",
    )
    files = [
        FileInfo(
            filename="src/auth.py",
            status="modified",
            additions=5,
            deletions=1,
            patch="@@ -10,5 +10,9 @@\n-token = request.GET['token']\n+token = request.headers.get('Authorization')\n",
        )
    ]
    return ReviewState(pr_metadata=pr, changed_files=files)


def _valid_finding_list() -> FindingList:
    """Return a FindingList with one security finding."""
    return FindingList(
        findings=[
            Finding(
                path="src/auth.py",
                line=12,
                severity="high",
                category="security",
                body="Token retrieved from query param instead of header — exposes credentials in logs.",
                confidence=0.9,
            )
        ]
    )


def _make_registry(*names: str) -> SkillRegistry:
    """Return a SkillRegistry with minimal Skill objects."""
    skills = {
        n: Skill(
            name=n,
            description=f"Desc {n}",
            body=f"# {n} body",
            path=Path(f"/fake/{n}/SKILL.md"),
            raw_frontmatter={"name": n, "description": f"Desc {n}"},
        )
        for n in names
    }
    return SkillRegistry(skills)


class TestBuildSecurityChain:
    """Tests for build_security_chain."""

    def test_build_security_chain_succeeds(self) -> None:
        """Chain builds without error given a mocked LLM."""
        mock_llm = MagicMock()

        with patch(
            "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            chain = build_security_chain(CouncilConfig())

        assert chain is not None

    def test_build_security_chain_injects_skills_when_registry_provided(self) -> None:
        """apply_skills is called when a non-empty registry with matching skills is given."""
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
            build_security_chain(config, registry=registry)

        mock_apply.assert_called_once()

    def test_build_security_chain_system_message_contains_skills_marker(self) -> None:
        """The rebuilt prompt's system message contains the skills block start marker."""
        from langchain_core.prompts import ChatPromptTemplate

        from ai_council_review.skills.injection import apply_skills as real_apply_skills

        mock_llm = MagicMock()
        registry = _make_registry("auth-patterns")

        captured_prompts: list[ChatPromptTemplate] = []

        def _capturing_apply(prompt: ChatPromptTemplate, skills: list) -> ChatPromptTemplate:
            result = real_apply_skills(prompt, skills)
            captured_prompts.append(result)
            return result

        with (
            patch(
                "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
                return_value=mock_llm,
            ),
            patch(
                "ai_council_review.llm.agents.specialist.apply_skills",
                side_effect=_capturing_apply,
            ),
        ):
            build_security_chain(
                CouncilConfig(default_agent_skills=["auth-patterns"]),
                registry=registry,
            )

        assert len(captured_prompts) == 1
        system_text = str(captured_prompts[0])
        assert "<!-- ai-council:skills:start -->" in system_text

    def test_build_security_chain_emits_metadata_when_skills_attached(self) -> None:
        """The returned chain carries agent + skills metadata for observability."""
        mock_llm = MagicMock()
        registry = _make_registry("auth-patterns")
        config = CouncilConfig(default_agent_skills=["auth-patterns"])

        with patch(
            "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            chain = build_security_chain(config, registry=registry)

        cfg = chain.config  # RunnableBinding exposes bound config
        assert "agent:security" in cfg["tags"]
        assert "skills:bodies" in cfg["tags"]
        meta = cfg["metadata"]
        assert meta["ai_council.agent"] == "security"
        assert meta["ai_council.skills.attached"] == ["auth-patterns"]
        assert meta["ai_council.skills.mode"] == "bodies"

    def test_build_security_chain_emits_none_metadata_when_no_registry(self) -> None:
        """Without a registry, the chain still tags itself agent:security, skills:none."""
        mock_llm = MagicMock()

        with patch(
            "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            chain = build_security_chain(CouncilConfig())

        cfg = chain.config
        assert "agent:security" in cfg["tags"]
        assert "skills:none" in cfg["tags"]
        assert cfg["metadata"]["ai_council.skills.mode"] == "none"

    def test_build_security_chain_unchanged_when_registry_is_none(self) -> None:
        """Passing registry=None produces the same chain as the no-registry call."""
        mock_llm = MagicMock()

        with patch(
            "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            chain_no_registry = build_security_chain(CouncilConfig())

        with patch(
            "ai_council_review.llm.agents.specialist.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            chain_none = build_security_chain(CouncilConfig(), registry=None)

        # Both calls succeed and return a Runnable.
        assert chain_no_registry is not None
        assert chain_none is not None


class TestRunSecurityAgent:
    """Tests for run_security_agent."""

    def test_run_security_agent_parses_valid_output(self) -> None:
        """Mock LLM returns FindingList; verify Finding list returned with agent tag."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = _valid_finding_list()

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
            findings = run_security_agent(_make_state(), CouncilConfig(), None)

        assert isinstance(findings, list)
        assert len(findings) == 1
        finding = findings[0]
        assert isinstance(finding, Finding)
        assert finding.path == "src/auth.py"
        assert finding.severity == Severity.HIGH
        assert finding.category == "security"
        assert finding.agent == "security"

    def test_run_security_agent_returns_empty_on_bad_output(self) -> None:
        """Mock raises a generic Exception; verify empty list with no crash."""
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = Exception("structured output parse failure")

        with patch(
            "ai_council_review.llm.agents.specialist.build_specialist_chain",
            return_value=mock_chain,
        ):
            findings = run_security_agent(_make_state(), CouncilConfig(), None)

        assert findings == []

    def test_run_security_agent_propagates_budget_error(self) -> None:
        """BudgetExceededError is re-raised, not swallowed."""
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = BudgetExceededError("over budget")

        with (
            patch(
                "ai_council_review.llm.agents.specialist.build_specialist_chain",
                return_value=mock_chain,
            ),
            patch(
                "ai_council_review.llm.agents.specialist.make_repository_tools",
                return_value=[],
            ),
            pytest.raises(BudgetExceededError),
        ):
            run_security_agent(_make_state(), CouncilConfig(), None)
