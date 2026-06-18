"""Tests for the router agent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_council_review.config import CouncilConfig
from ai_council_review.exceptions import BudgetExceededError
from ai_council_review.llm.agents.router import RouterOutput, build_router_chain, run_router_agent
from ai_council_review.models import FileInfo, PRMetadata, ReviewState
from ai_council_review.skills.models import Skill
from ai_council_review.skills.registry import SkillRegistry


def _make_registry(*names: str) -> SkillRegistry:
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


def _make_state() -> ReviewState:
    """Return a minimal ReviewState for router tests."""
    pr = PRMetadata(
        number=1,
        title="Add feature X",
        state="open",
        author="alice",
        author_association="CONTRIBUTOR",
        base_ref="main",
        base_sha="abc",
        head_ref="feature/x",
        head_sha="def",
        html_url="https://github.com/owner/repo/pull/1",
    )
    files = [FileInfo(filename="src/app.py", status="modified", additions=10, deletions=2)]
    return ReviewState(pr_metadata=pr, changed_files=files)


class TestBuildRouterChain:
    """Tests for build_router_chain."""

    def test_build_router_chain_succeeds(self) -> None:
        """Chain builds without error given a mocked LLM."""
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = MagicMock()

        with patch(
            "ai_council_review.llm.agents.router.LLMProviderFactory.from_config",
            return_value=mock_llm,
        ):
            chain = build_router_chain(CouncilConfig())

        assert chain is not None
        mock_llm.with_structured_output.assert_called_once_with(RouterOutput)

    def test_build_router_chain_injects_skill_catalog_when_registry_provided(self) -> None:
        """apply_skill_catalog (not apply_skills) is called for the router."""
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = MagicMock()
        registry = _make_registry("security-patterns")

        with (
            patch(
                "ai_council_review.llm.agents.router.LLMProviderFactory.from_config",
                return_value=mock_llm,
            ),
            patch(
                "ai_council_review.llm.agents.router.apply_skill_catalog",
                wraps=lambda prompt, skills: prompt,
            ) as mock_catalog,
        ):
            build_router_chain(
                CouncilConfig(default_agent_skills=["security-patterns"]),
                registry=registry,
            )

        mock_catalog.assert_called_once()

    def test_build_router_chain_unchanged_when_registry_is_none(self) -> None:
        """Passing registry=None does not call apply_skill_catalog."""
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = MagicMock()

        with (
            patch(
                "ai_council_review.llm.agents.router.LLMProviderFactory.from_config",
                return_value=mock_llm,
            ),
            patch(
                "ai_council_review.llm.agents.router.apply_skill_catalog",
            ) as mock_catalog,
        ):
            build_router_chain(CouncilConfig(), registry=None)

        mock_catalog.assert_not_called()


class TestRunRouterAgent:
    """Tests for run_router_agent."""

    def test_run_router_agent_returns_router_output(self) -> None:
        """Mock chain.invoke returns RouterOutput; verify return type and fields."""
        expected = RouterOutput(
            agents_needed=["security", "quality"],
            review_depth="standard",
            reasoning="Looks security-sensitive",
        )
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = expected

        with patch(
            "ai_council_review.llm.agents.router.build_router_chain",
            return_value=mock_chain,
        ):
            result = run_router_agent(_make_state(), CouncilConfig())

        assert isinstance(result, RouterOutput)
        assert result.agents_needed == ["security", "quality"]
        assert result.review_depth == "standard"
        assert result.reasoning == "Looks security-sensitive"

    def test_run_router_agent_falls_back_on_exception(self) -> None:
        """When chain.invoke raises a generic Exception, a fallback RouterOutput is returned."""
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = RuntimeError("LLM unavailable")

        with patch(
            "ai_council_review.llm.agents.router.build_router_chain",
            return_value=mock_chain,
        ):
            result = run_router_agent(_make_state(), CouncilConfig())

        from ai_council_review.llm.agents.registry import SPECIALIST_AGENTS

        assert isinstance(result, RouterOutput)
        # Fallback returns all enabled specialists from the registry.
        expected = {spec.name for spec in SPECIALIST_AGENTS if spec.enabled_by_default}
        assert set(result.agents_needed) == expected
        assert result.review_depth == "standard"
        assert "Router failed" in result.reasoning

    def test_run_router_agent_falls_back_when_chain_returns_none(self) -> None:
        """When chain.invoke returns None (reasoning-model behaviour), a safe
        fallback RouterOutput is returned instead of raising AttributeError."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = None

        with patch(
            "ai_council_review.llm.agents.router.build_router_chain",
            return_value=mock_chain,
        ):
            result = run_router_agent(_make_state(), CouncilConfig())

        from ai_council_review.llm.agents.registry import SPECIALIST_AGENTS

        assert isinstance(result, RouterOutput)
        expected = {spec.name for spec in SPECIALIST_AGENTS if spec.enabled_by_default}
        assert set(result.agents_needed) == expected
        assert result.review_depth == "standard"
        assert "None" in result.reasoning

    def test_run_router_agent_propagates_budget_error(self) -> None:
        """BudgetExceededError raised during routing is re-raised immediately.

        The router no longer degrades gracefully on budget errors — it re-raises
        to prevent launching three more expensive specialist agents when the
        budget is already exhausted.
        """
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = BudgetExceededError("over budget")

        with (
            patch(
                "ai_council_review.llm.agents.router.build_router_chain",
                return_value=mock_chain,
            ),
            pytest.raises(BudgetExceededError),
        ):
            run_router_agent(_make_state(), CouncilConfig())
