"""Configuration loader for AI Council Code Review."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseModel):
    """Configuration for a single agent."""

    enabled: bool = True
    model: str = "fireworks"
    model_name: str = "accounts/fireworks/models/llama-v3p1-70b-instruct"
    temperature: float = 0.3
    max_tokens: int = 4000
    system_prompt: str | None = None


class ProviderConfig(BaseModel):
    """Configuration for an LLM provider."""

    api_key: str | None = None
    base_url: str | None = None


class CouncilConfig(BaseModel):
    """Top-level configuration for the AI Council."""

    version: str = "1"
    review_depth: str = "standard"
    max_files: int = 50
    max_lines: int = 2000
    max_diff_size: int = 50000
    comment_on_forks: bool = False
    skip_drafts: bool = True
    skip_labels: list[str] = Field(default_factory=list)
    skip_patterns: list[str] = Field(
        default_factory=lambda: [
            "package-lock.json",
            "yarn.lock",
            "poetry.lock",
            "Cargo.lock",
            "Gemfile.lock",
            "*.snap",
            "dist/",
            "build/",
            "node_modules/",
        ]
    )
    budget_usd: float = 5.0
    agents: dict[str, AgentConfig] = Field(default_factory=dict)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)


class EnvConfig(BaseSettings):
    """Environment-based configuration with AI_COUNCIL__ prefix."""

    model_config = SettingsConfigDict(
        env_prefix="AI_COUNCIL__",
        env_nested_delimiter="__",
        extra="ignore",
    )

    fireworks_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    github_token: str | None = None


def load_config(config_path: str | Path | None = None) -> CouncilConfig:
    """Load configuration from YAML file with environment overrides.

    Args:
        config_path: Path to the YAML config file. If None, looks for
            `.ai-council/config.yaml` in the current working directory.

    Returns:
        A validated CouncilConfig instance.

    Raises:
        ValidationError: If the configuration is invalid.
        FileNotFoundError: If the config file is specified but not found.
    """
    if config_path is None:
        config_path = Path.cwd() / ".ai-council" / "config.yaml"
    else:
        config_path = Path(config_path)

    data: dict[str, Any] = {}

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    env = EnvConfig()
    providers = data.get("providers", {})

    if env.fireworks_api_key and "fireworks" not in providers:
        providers["fireworks"] = {"api_key": env.fireworks_api_key}
    elif env.fireworks_api_key and "fireworks" in providers:
        providers["fireworks"]["api_key"] = env.fireworks_api_key

    if env.openai_api_key and "openai" not in providers:
        providers["openai"] = {"api_key": env.openai_api_key}
    elif env.openai_api_key and "openai" in providers:
        providers["openai"]["api_key"] = env.openai_api_key

    if env.anthropic_api_key and "anthropic" not in providers:
        providers["anthropic"] = {"api_key": env.anthropic_api_key}
    elif env.anthropic_api_key and "anthropic" in providers:
        providers["anthropic"]["api_key"] = env.anthropic_api_key

    data["providers"] = providers

    return CouncilConfig(**data)
