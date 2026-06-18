"""Tests for ai_council_review.config."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from ai_council_review.config import (
    ALL_SKILLS,
    CANONICAL_AGENTS,
    AgentConfig,
    CouncilConfig,
    load_config,
    resolve_agent_skills_selector,
    validate_config,
    validate_skill_budgets,
    validate_skill_references,
)
from ai_council_review.exceptions import ConfigError


class TestAgentConfig:
    """Tests for AgentConfig model."""

    def test_default_agent_config(self) -> None:
        """Test default agent config values."""
        config = AgentConfig()
        assert config.enabled is True
        assert config.model == "openai"
        assert config.temperature == 0.3
        assert config.max_tokens == 16000

    def test_zero_config_resolves_to_openai_gpt41mini(self) -> None:
        """Zero-config AgentConfig() defaults to openai provider + gpt-4.1-mini model."""
        config = AgentConfig()
        assert config.model == "openai"
        assert config.model_name == "gpt-4.1-mini"

    def test_model_name_default_for_fireworks(self) -> None:
        """Provider default fills in when model_name is not specified."""
        config = AgentConfig(model="fireworks")
        assert config.model_name == "accounts/fireworks/models/kimi-k2p6"

    def test_model_name_default_for_openai(self) -> None:
        """OpenAI provider gets gpt-4.1-mini default when model_name omitted."""
        config = AgentConfig(model="openai")
        assert config.model_name == "gpt-4.1-mini"

    def test_model_name_default_for_anthropic(self) -> None:
        """Anthropic provider gets a haiku default when model_name omitted."""
        config = AgentConfig(model="anthropic")
        assert config.model_name == "claude-3-5-haiku-20241022"

    def test_explicit_model_name_overrides_default(self) -> None:
        """User-supplied model_name is respected even when a default exists."""
        config = AgentConfig(model="openai", model_name="gpt-4o")
        assert config.model_name == "gpt-4o"

    def test_alias_resolution_still_works(self) -> None:
        """Alias form is resolved to the current canonical model id.

        The retired llama-3.1-70b alias now maps to kimi-k2p6-turbo so that
        configs written against the old Fireworks model IDs keep working.
        """
        config = AgentConfig(model="fireworks", model_name="fireworks/llama-3.1-70b")
        assert config.model_name == "accounts/fireworks/routers/kimi-k2p6-turbo"

    def test_unknown_provider_raises_when_model_name_missing(self) -> None:
        """A provider without a default and no model_name yields a clear error."""
        with pytest.raises(ValidationError, match="No default model_name"):
            AgentConfig(model="unknown-provider")


class TestCouncilConfig:
    """Tests for CouncilConfig model."""

    def test_default_council_config(self) -> None:
        """Test default council config values."""
        config = CouncilConfig()
        assert config.version == "1"
        assert config.review_depth == "standard"
        assert config.max_files == 50
        assert config.max_lines == 2000
        assert config.budget_usd == 5.0
        assert config.skip_drafts is True
        assert config.comment_on_forks is False
        assert "package-lock.json" in config.skip_patterns

    def test_custom_config(self) -> None:
        """Test creating custom config."""
        config = CouncilConfig(
            max_files=10,
            skip_labels=["wip"],
            agents={
                "security": AgentConfig(enabled=True, model="openai"),
            },
        )
        assert config.max_files == 10
        assert config.skip_labels == ["wip"]
        assert config.agents["security"].model == "openai"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_from_file(self, tmp_path: Path) -> None:
        """Test loading config from YAML file."""
        config_dir = tmp_path / ".ai-council"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"

        data = {
            "version": "1",
            "max_files": 25,
            "agents": {
                "security": {
                    "enabled": True,
                    "model": "anthropic",
                    "model_name": "claude-3-sonnet",
                }
            },
        }
        config_file.write_text(yaml.dump(data))

        config = load_config(config_file)
        assert config.max_files == 25
        assert config.agents["security"].model == "anthropic"

    def test_load_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that env vars override config."""
        config_dir = tmp_path / ".ai-council"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(yaml.dump({"version": "1"}))

        monkeypatch.setenv("AI_COUNCIL__FIREWORKS_API_KEY", "fw-test-key")
        monkeypatch.setenv("AI_COUNCIL__OPENAI_API_KEY", "sk-test-key")

        config = load_config(config_file)
        assert config.providers["fireworks"].api_key == "fw-test-key"
        assert config.providers["openai"].api_key == "sk-test-key"

    def test_invalid_config_raises(self, tmp_path: Path) -> None:
        """Test that invalid config raises ValidationError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"max_files": "not_a_number"}))

        with pytest.raises(ValidationError):
            load_config(config_file)

    def test_missing_file_uses_defaults(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that missing config file uses defaults."""
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config.max_files == 50
        assert config.agents == {}

    def test_explicit_missing_path_raises(self) -> None:
        """Test that an explicit path that doesn't exist raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config("/nonexistent/path/config.yaml")

    def test_env_config_override_existing_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that env vars override existing provider config."""
        config_dir = tmp_path / ".ai-council"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(yaml.dump({"providers": {"fireworks": {"api_key": "existing-key"}}}))

        monkeypatch.setenv("AI_COUNCIL__FIREWORKS_API_KEY", "new-key")

        config = load_config(config_file)
        assert config.providers["fireworks"].api_key == "new-key"


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_validate_config_raises_when_missing_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raise ConfigError when an enabled agent's provider has no API key."""
        from ai_council_review.exceptions import ConfigError

        # Ensure none of the bare env vars are set
        for var in ("FIREWORKS_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        for var in (
            "AI_COUNCIL__FIREWORKS_API_KEY",
            "AI_COUNCIL__OPENAI_API_KEY",
            "AI_COUNCIL__ANTHROPIC_API_KEY",
        ):
            monkeypatch.delenv(var, raising=False)

        config = CouncilConfig(
            agents={"security": AgentConfig(enabled=True, model="openai")},
        )

        with pytest.raises(ConfigError, match="No LLM API key found"):
            validate_config(config)

    def test_validate_config_passes_with_key_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No exception when the enabled agent's provider has an API key."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        config = CouncilConfig(
            agents={"quality": AgentConfig(enabled=True, model="openai")},
        )

        # Should not raise
        validate_config(config)

    def test_validate_config_uses_canonical_agents_when_none_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no agents are configured, CANONICAL_AGENTS are used for validation.

        Providing a key for the default provider (openai) satisfies all
        canonical agents because AgentConfig defaults to model="openai".
        """
        # Clear any leaked keys first
        for var in ("FIREWORKS_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        for var in (
            "AI_COUNCIL__FIREWORKS_API_KEY",
            "AI_COUNCIL__OPENAI_API_KEY",
            "AI_COUNCIL__ANTHROPIC_API_KEY",
        ):
            monkeypatch.delenv(var, raising=False)

        # With no key set, all canonical agents should be missing
        from ai_council_review.exceptions import ConfigError

        config_no_key = CouncilConfig()
        with pytest.raises(ConfigError) as exc_info:
            validate_config(config_no_key)

        error_message = str(exc_info.value)
        for agent_name in CANONICAL_AGENTS:
            assert agent_name in error_message

        # With an OpenAI key, validation passes for the default agent config
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        config_with_key = CouncilConfig()
        validate_config(config_with_key)  # should not raise

    def test_validate_config_includes_all_six_specialists_when_zero_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """C-2: validate_config checks ALL registry agents (including the three new
        ones: performance, documentation, devops) when no agents are configured.

        With no API keys at all, all canonical agents (defaulting to 'openai')
        must appear in the error message.
        """
        from ai_council_review.config import get_canonical_agents
        from ai_council_review.exceptions import ConfigError

        # Clear all provider keys.
        for var in ("FIREWORKS_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        for var in (
            "AI_COUNCIL__FIREWORKS_API_KEY",
            "AI_COUNCIL__OPENAI_API_KEY",
            "AI_COUNCIL__ANTHROPIC_API_KEY",
        ):
            monkeypatch.delenv(var, raising=False)

        config = CouncilConfig()
        with pytest.raises(ConfigError) as exc_info:
            validate_config(config)

        error_message = str(exc_info.value)
        canonical = get_canonical_agents()

        # All six specialists plus router/synthesis must appear in the error.
        for agent_name in canonical:
            assert agent_name in error_message, (
                f"Expected agent '{agent_name}' in error message but it was missing.\n"
                f"This means get_canonical_agents() is not being used in validate_config. "
                f"Error: {error_message[:200]}"
            )

        # Specifically, the three new agents must be validated.
        for new_agent in ("performance", "documentation", "devops"):
            assert new_agent in error_message, (
                f"New agent '{new_agent}' not validated — stale CANONICAL_AGENTS still in use."
            )

    def test_validate_config_openai_only_key_passes_for_openai_default_agents(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """C-2 integration: a single OPENAI_API_KEY satisfies zero-config validation.

        All default agents now use model='openai', so OPENAI_API_KEY alone is
        sufficient to pass validation when no explicit agent config is supplied.
        """
        # Set only the OpenAI key; clear all others.
        for var in ("FIREWORKS_API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        for var in ("AI_COUNCIL__FIREWORKS_API_KEY", "AI_COUNCIL__ANTHROPIC_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test-key")

        config = CouncilConfig()  # no explicit agents — uses all defaults
        validate_config(config)  # should not raise


class TestSkillSelector:
    """Tests for SkillSelector-related config fields and helpers."""

    # --- AgentConfig.skills ---

    def test_agent_skills_default_is_none(self) -> None:
        """AgentConfig.skills defaults to None (inherit from default_agent_skills)."""
        config = AgentConfig()
        assert config.skills is None

    def test_agent_skills_accepts_list(self) -> None:
        """AgentConfig.skills accepts a list of skill names."""
        config = AgentConfig(skills=["oauth-flows", "jwt-pitfalls"])
        assert config.skills == ["oauth-flows", "jwt-pitfalls"]

    def test_agent_skills_accepts_star_sentinel(self) -> None:
        """AgentConfig.skills accepts the '*' all-skills sentinel."""
        config = AgentConfig(skills=ALL_SKILLS)
        assert config.skills == "*"

    def test_agent_skills_rejects_other_strings(self) -> None:
        """AgentConfig.skills rejects bare strings that are not '*'."""
        with pytest.raises(ValidationError, match="must be None"):
            AgentConfig(skills="all")  # type: ignore[arg-type]

        with pytest.raises(ValidationError, match="must be None"):
            AgentConfig(skills="everything")  # type: ignore[arg-type]

    # --- CouncilConfig.default_agent_skills ---

    def test_council_default_agent_skills_default_is_none(self) -> None:
        """CouncilConfig.default_agent_skills defaults to None."""
        config = CouncilConfig()
        assert config.default_agent_skills is None

    def test_council_default_agent_skills_accepts_list(self) -> None:
        """CouncilConfig.default_agent_skills accepts a list."""
        config = CouncilConfig(default_agent_skills=["domain-glossary"])
        assert config.default_agent_skills == ["domain-glossary"]

    def test_council_default_agent_skills_accepts_star(self) -> None:
        """CouncilConfig.default_agent_skills accepts '*'."""
        config = CouncilConfig(default_agent_skills="*")
        assert config.default_agent_skills == "*"

    def test_council_default_agent_skills_rejects_other_strings(self) -> None:
        """CouncilConfig.default_agent_skills rejects non-sentinel strings."""
        with pytest.raises(ValidationError, match="must be None"):
            CouncilConfig(default_agent_skills="all")  # type: ignore[arg-type]

    # --- resolve_agent_skills_selector ---

    def test_resolve_agent_skills_selector_uses_agent_when_set(self) -> None:
        """Agent-level selector takes precedence over council default."""
        agent = AgentConfig(skills=["jwt-pitfalls"])
        council = CouncilConfig(default_agent_skills=["domain-glossary"])
        result = resolve_agent_skills_selector(agent, council)
        assert result == ["jwt-pitfalls"]

    def test_resolve_agent_skills_selector_falls_back_to_default(self) -> None:
        """When agent.skills is None, council.default_agent_skills is returned."""
        agent = AgentConfig()
        council = CouncilConfig(default_agent_skills=["domain-glossary"])
        result = resolve_agent_skills_selector(agent, council)
        assert result == ["domain-glossary"]

    def test_resolve_agent_skills_selector_explicit_empty_list_opts_out(self) -> None:
        """An explicit [] on agent.skills opts out, even when a default is set."""
        agent = AgentConfig(skills=[])
        council = CouncilConfig(default_agent_skills=["domain-glossary"])
        result = resolve_agent_skills_selector(agent, council)
        assert result == []

    def test_resolve_agent_skills_selector_no_default_returns_none(self) -> None:
        """When both are None, None is returned."""
        agent = AgentConfig()
        council = CouncilConfig()
        result = resolve_agent_skills_selector(agent, council)
        assert result is None

    # --- validate_skill_references ---

    def test_validate_skill_references_passes_when_all_known(self) -> None:
        """No exception when all named skills are present in the registry."""
        from unittest.mock import MagicMock

        registry = MagicMock()
        registry.__contains__ = lambda self, name: name == "known-skill"
        registry.names.return_value = ["known-skill"]

        config = CouncilConfig(
            default_agent_skills=["known-skill"],
            agents={"security": AgentConfig(skills=["known-skill"])},
        )
        validate_skill_references(config, registry)  # should not raise

    def test_validate_skill_references_raises_on_missing(self) -> None:
        """ConfigError is raised listing all (context, skill) pairs that are missing."""
        from unittest.mock import MagicMock

        from ai_council_review.exceptions import ConfigError

        registry = MagicMock()
        registry.__contains__ = lambda self, name: False  # nothing found
        registry.names.return_value = []

        config = CouncilConfig(
            default_agent_skills=["missing-skill"],
        )
        with pytest.raises(ConfigError, match="missing-skill"):
            validate_skill_references(config, registry)

    def test_validate_skill_references_star_always_valid(self) -> None:
        """The '*' sentinel is never checked against the registry."""
        from unittest.mock import MagicMock

        registry = MagicMock()
        registry.__contains__ = lambda self, name: False  # nothing found
        registry.names.return_value = []

        config = CouncilConfig(
            default_agent_skills="*",
            agents={"security": AgentConfig(skills="*")},
        )
        validate_skill_references(config, registry)  # should not raise

    # --- validate_skill_budgets ---

    def test_validate_skill_budgets_raises_at_startup_when_hard_exceeded(self) -> None:
        """Hard budget violations fail fast at config load, not at chain build."""
        from pathlib import Path

        from ai_council_review.skills.models import Skill
        from ai_council_review.skills.registry import SkillRegistry

        # 5000 chars -> ~1250 tokens via len/4 heuristic. Two of them = 2500
        # tokens — over a hard cap set to 1000.
        big_body = "x" * 5000
        skill = Skill(
            name="huge",
            description="A heavy skill.",
            body=big_body,
            path=Path("/fake/huge/SKILL.md"),
            raw_frontmatter={"name": "huge", "description": "A heavy skill."},
        )
        registry = SkillRegistry({"huge": skill})

        config = CouncilConfig(
            skills_token_budget_soft=500,
            skills_token_budget_hard=1000,
            agents={"security": AgentConfig(skills=["huge"])},
        )

        with pytest.raises(ConfigError, match="hard token budget"):
            validate_skill_budgets(config, registry)

    def test_validate_skill_budgets_passes_when_under_hard(self) -> None:
        """Under the hard cap, validation succeeds (soft warn is non-fatal)."""
        from pathlib import Path

        from ai_council_review.skills.models import Skill
        from ai_council_review.skills.registry import SkillRegistry

        skill = Skill(
            name="small",
            description="A small skill.",
            body="tiny",
            path=Path("/fake/small/SKILL.md"),
            raw_frontmatter={"name": "small", "description": "A small skill."},
        )
        registry = SkillRegistry({"small": skill})

        config = CouncilConfig(agents={"security": AgentConfig(skills=["small"])})
        validate_skill_budgets(config, registry)  # should not raise
