"""Tests for ai_council_review.skills.resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_council_review.config import AgentConfig, CouncilConfig
from ai_council_review.exceptions import ConfigError
from ai_council_review.skills.models import Skill
from ai_council_review.skills.registry import SkillRegistry
from ai_council_review.skills.resolution import bind_chain_metadata, resolve_skills_for_agent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_skill(name: str, body: str = "# body") -> Skill:
    """Return a minimal Skill fixture."""
    return Skill(
        name=name,
        description=f"Description for {name}.",
        body=body,
        path=Path(f"/fake/{name}/SKILL.md"),
        raw_frontmatter={"name": name, "description": f"Description for {name}."},
    )


def _registry(*names: str) -> SkillRegistry:
    """Return a SkillRegistry pre-populated with skills of the given names."""
    skills = {n: _make_skill(n) for n in names}
    return SkillRegistry(skills)


def _config(
    agent_name: str | None = None,
    agent_skills: object = None,
    default_agent_skills: object = None,
    soft: int = 8000,
    hard: int = 16000,
) -> CouncilConfig:
    """Return a CouncilConfig wired with one optional agent entry."""
    agents = {}
    if agent_name is not None:
        agents[agent_name] = AgentConfig(skills=agent_skills)  # type: ignore[arg-type]
    return CouncilConfig(
        agents=agents,
        default_agent_skills=default_agent_skills,  # type: ignore[arg-type]
        skills_token_budget_soft=soft,
        skills_token_budget_hard=hard,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResolveSkillsForAgent:
    """resolve_skills_for_agent — precedence, sentinel, budget."""

    def test_returns_listed_skills(self) -> None:
        """Returns the Skill objects named in agent.skills."""
        registry = _registry("skill-a", "skill-b", "skill-c")
        config = _config("security", agent_skills=["skill-a", "skill-c"])

        result = resolve_skills_for_agent("security", config, registry)

        assert [s.name for s in result] == ["skill-a", "skill-c"]

    def test_resolves_star_to_all_skills(self) -> None:
        """The '*' sentinel resolves to all skills in the registry, sorted."""
        registry = _registry("skill-b", "skill-a")
        config = _config("security", agent_skills="*")

        result = resolve_skills_for_agent("security", config, registry)

        assert [s.name for s in result] == ["skill-a", "skill-b"]

    def test_empty_registry_returns_empty(self) -> None:
        """With an empty registry, no skills are returned regardless of selector."""
        registry = _registry()  # empty
        config = _config("security", agent_skills="*")

        result = resolve_skills_for_agent("security", config, registry)

        assert result == []

    def test_synthesis_always_empty(self) -> None:
        """Synthesis agent always gets an empty list in Phase 1."""
        registry = _registry("skill-a")
        config = _config("synthesis", agent_skills="*")

        result = resolve_skills_for_agent("synthesis", config, registry)

        assert result == []

    def test_uses_default_when_agent_unset(self) -> None:
        """Falls back to default_agent_skills when agent.skills is None."""
        registry = _registry("default-skill")
        config = _config(default_agent_skills=["default-skill"])

        result = resolve_skills_for_agent("security", config, registry)

        assert [s.name for s in result] == ["default-skill"]

    def test_explicit_empty_list_opts_out(self) -> None:
        """An explicit [] on agent.skills returns empty even with a default set."""
        registry = _registry("default-skill")
        config = _config("security", agent_skills=[], default_agent_skills=["default-skill"])

        result = resolve_skills_for_agent("security", config, registry)

        assert result == []

    def test_no_selector_returns_empty(self) -> None:
        """Returns [] when neither agent.skills nor default_agent_skills is set."""
        registry = _registry("skill-a")
        config = _config()  # no agent entry, no default

        result = resolve_skills_for_agent("security", config, registry)

        assert result == []

    def test_hard_budget_raises(self) -> None:
        """ConfigError is raised when total skill tokens exceed the hard limit."""
        # Body of ~400 chars ≈ 100 estimated tokens; set hard limit to 1.
        big_body = "x" * 400
        registry = SkillRegistry({"big-skill": _make_skill("big-skill", body=big_body)})
        config = _config("security", agent_skills=["big-skill"], hard=1)

        with pytest.raises(ConfigError, match="hard token budget"):
            resolve_skills_for_agent("security", config, registry)

    def test_soft_budget_warns(self) -> None:
        """A warning is emitted (but no exception) when the soft limit is exceeded."""
        from unittest.mock import MagicMock, patch

        # Body of ~400 chars ≈ 100 tokens; set soft=1, hard=99999 so only soft fires.
        big_body = "x" * 400
        registry = SkillRegistry({"big-skill": _make_skill("big-skill", body=big_body)})
        config = _config("security", agent_skills=["big-skill"], soft=1, hard=99999)

        mock_log = MagicMock()
        with patch("ai_council_review.skills.resolution.log", mock_log):
            result = resolve_skills_for_agent("security", config, registry)

        # Run should continue (no exception) and the logger was called with warning.
        assert len(result) == 1
        mock_log.warning.assert_called_once()
        warning_call_kwargs = mock_log.warning.call_args
        assert "soft token budget" in warning_call_kwargs.args[0]


class TestBindChainMetadata:
    """bind_chain_metadata() attaches LangChain tags + metadata for observability."""

    def _runnable(self) -> object:
        """Return a trivial Runnable for wrapping."""
        from langchain_core.runnables import RunnableLambda

        return RunnableLambda(lambda x: x)

    def test_attaches_agent_tag_and_metadata_with_skills(self) -> None:
        """Returned runnable has agent + skills tags and ai_council.* metadata."""
        skills = [_make_skill("oauth-pitfalls", body="some guidance " * 20)]

        bound = bind_chain_metadata(self._runnable(), "security", skills, "bodies")

        cfg = bound.config  # RunnableBinding exposes the bound config
        assert "agent:security" in cfg["tags"]
        assert "skills:bodies" in cfg["tags"]
        meta = cfg["metadata"]
        assert meta["ai_council.agent"] == "security"
        assert meta["ai_council.skills.attached"] == ["oauth-pitfalls"]
        assert meta["ai_council.skills.mode"] == "bodies"
        assert meta["ai_council.skills.total_tokens"] > 0

    def test_attaches_none_mode_when_no_skills(self) -> None:
        """When skills list is empty, mode is 'none' and total_tokens is 0."""
        bound = bind_chain_metadata(self._runnable(), "router", [], "none")

        cfg = bound.config
        assert "agent:router" in cfg["tags"]
        assert "skills:none" in cfg["tags"]
        meta = cfg["metadata"]
        assert meta["ai_council.skills.attached"] == []
        assert meta["ai_council.skills.mode"] == "none"
        assert meta["ai_council.skills.total_tokens"] == 0

    def test_emits_info_log_only_when_skills_attached(self) -> None:
        """The structured INFO log fires only when at least one skill is attached."""
        from unittest.mock import MagicMock, patch

        with patch("ai_council_review.skills.resolution.log") as mock_log:
            bind_chain_metadata(self._runnable(), "security", [], "none")
        mock_log.info.assert_not_called()

        with patch("ai_council_review.skills.resolution.log", MagicMock()) as mock_log:
            bind_chain_metadata(self._runnable(), "security", [_make_skill("s1")], "bodies")
        mock_log.info.assert_called_once()
        kwargs = mock_log.info.call_args.kwargs
        assert kwargs["agent"] == "security"
        assert kwargs["mode"] == "bodies"
        assert kwargs["names"] == ["s1"]
