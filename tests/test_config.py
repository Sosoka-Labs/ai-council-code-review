"""Tests for ai_council_review.config."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from ai_council_review.config import (
    CANONICAL_AGENTS,
    AgentConfig,
    CouncilConfig,
    load_config,
    validate_config,
)


class TestAgentConfig:
    """Tests for AgentConfig model."""

    def test_default_agent_config(self) -> None:
        """Test default agent config values."""
        config = AgentConfig()
        assert config.enabled is True
        assert config.model == "fireworks"
        assert config.temperature == 0.3
        assert config.max_tokens == 16000


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

        Providing a key for the default provider (fireworks) satisfies all
        canonical agents because AgentConfig defaults to model="fireworks".
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

        # With a fireworks key, validation passes for the default agent config
        monkeypatch.setenv("FIREWORKS_API_KEY", "fw-test-key")
        config_with_key = CouncilConfig()
        validate_config(config_with_key)  # should not raise
