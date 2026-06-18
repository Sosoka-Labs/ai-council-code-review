"""Configuration loader for AI Council Code Review."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_canonical_agents() -> list[str]:
    """Return the canonical agent list derived from the specialist registry.

    Includes the non-specialist fixed nodes (router, synthesis) plus every
    specialist defined in ``SPECIALIST_AGENTS``.  Called lazily to avoid an
    import cycle at module load time (config → llm.agents.registry → config).
    """
    from ai_council_review.llm.agents.registry import SPECIALIST_AGENTS  # noqa: PLC0415

    specialist_names = [spec.name for spec in SPECIALIST_AGENTS]
    return ["router", *specialist_names, "synthesis"]


# Populated at first access via the public accessor; kept as a module-level
# list so existing call sites (``from ai_council_review.config import CANONICAL_AGENTS``)
# continue to work.  Do NOT call _get_canonical_agents() here — it would create
# a circular import because config.py is loaded before the llm sub-package.
CANONICAL_AGENTS: list[str] = ["router", "security", "quality", "architecture", "synthesis"]


def get_canonical_agents() -> list[str]:
    """Return the up-to-date canonical agent list from the registry.

    Preferred over the module-level ``CANONICAL_AGENTS`` constant when called
    after all packages are initialized (e.g., in ``validate_skill_budgets``).
    """
    return _get_canonical_agents()


# Sentinel string that resolves to "all discovered skills" at runtime.
ALL_SKILLS = "*"

# None  → inherit from default_agent_skills (or no skills if that's also None)
# []    → explicit opt-out: no skills even if default_agent_skills is set
# [...]  → explicit list of skill names to bind
# "*"   → bind all skills in the registry
SkillSelector = list[str] | Literal["*"] | None

MODEL_ALIASES: dict[str, str] = {
    # Fireworks aliases — retired llama-v3p1-* paths kept for back-compat but
    # now map to the current kimi-k2p6-turbo router; users should update configs.
    "fireworks/llama-3.1-70b": "accounts/fireworks/routers/kimi-k2p6-turbo",
    "fireworks/llama-3.1-8b": "accounts/fireworks/routers/kimi-k2p6-turbo",
    "fireworks/kimi-k2p6": "accounts/fireworks/routers/kimi-k2p6-turbo",
    # OpenAI aliases
    "openai/gpt-4o": "gpt-4o",
    "openai/gpt-4.1": "gpt-4.1",
    "openai/gpt-4.1-mini": "gpt-4.1-mini",
    # Anthropic aliases
    "anthropic/claude-sonnet": "claude-sonnet-4-20250514",
    "anthropic/claude-haiku": "claude-3-5-haiku-20241022",
}

# One sensible default per provider, used when the user picks a provider but
# does not specify a model_name. Users remain free to override on any agent.
DEFAULT_MODELS_BY_PROVIDER: dict[str, str] = {
    "fireworks": "accounts/fireworks/models/kimi-k2p6",
    "openai": "gpt-4.1-mini",
    "anthropic": "claude-3-5-haiku-20241022",
}

_BARE_ENV_VARS: dict[str, str] = {
    "fireworks": "FIREWORKS_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


class AgentConfig(BaseModel):
    """Configuration for a single agent.

    ``model`` is the provider name (fireworks, openai, anthropic).
    ``model_name`` is the model identifier. If unset, a sensible default for the
    chosen provider is filled in from DEFAULT_MODELS_BY_PROVIDER — users are
    encouraged to override per agent.

    ``skills`` controls which domain-knowledge skill files are injected into
    this agent's system prompt. None (default) means "inherit from
    CouncilConfig.default_agent_skills". [] is an explicit opt-out. A list of
    names binds those specific skills. "*" binds all discovered skills.
    """

    enabled: bool = True
    model: str = "openai"
    model_name: str | None = None
    temperature: float = 0.3
    max_tokens: int = 16000
    system_prompt: str | None = None
    skills: SkillSelector = None

    @field_validator("skills", mode="before")
    @classmethod
    def _validate_skills(cls, value: object) -> object:
        """Reject bare strings other than the '*' sentinel.

        Accepted forms: None, "*", [], ["name1", "name2"].
        Strings like "all" or "everything" are rejected with a clear message.
        """
        if isinstance(value, str) and value != ALL_SKILLS:
            raise ValueError(
                f"skills must be None, '*', or a list of skill names — got string {value!r}. "
                "To bind all skills use '*'."
            )
        return value

    @field_validator("model_name", mode="before")
    @classmethod
    def _resolve_alias(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return MODEL_ALIASES.get(value, value)

    @model_validator(mode="after")
    def _fill_default_model_name(self) -> AgentConfig:
        if self.model_name is None:
            provider = self.model.lower()
            default = DEFAULT_MODELS_BY_PROVIDER.get(provider)
            if default is None:
                raise ValueError(
                    f"No default model_name available for provider '{self.model}'. "
                    f"Set model_name explicitly. Supported providers with defaults: "
                    f"{sorted(DEFAULT_MODELS_BY_PROVIDER)}."
                )
            self.model_name = default
        return self


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
            "**/*.pyc",
        ]
    )
    budget_usd: float = 5.0
    agent_timeout_seconds: int = 300
    total_timeout_seconds: int = 600
    debug: bool = False
    rate_limit_threshold: int = 50
    agents: dict[str, AgentConfig] = Field(default_factory=dict)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    skills_path: str = ".ai-council/skills"
    default_agent_skills: SkillSelector = None
    skills_token_budget_soft: int = 8000
    skills_token_budget_hard: int = 16000

    @field_validator("default_agent_skills", mode="before")
    @classmethod
    def _validate_default_agent_skills(cls, value: object) -> object:
        """Reject bare strings other than the '*' sentinel."""
        if isinstance(value, str) and value != ALL_SKILLS:
            raise ValueError(
                f"default_agent_skills must be None, '*', or a list of skill names — "
                f"got string {value!r}. To bind all skills use '*'."
            )
        return value


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
    explicit_path = config_path is not None
    config_path = (
        Path(config_path) if config_path is not None else Path.cwd() / ".ai-council" / "config.yaml"
    )

    data: dict[str, Any] = {}

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    elif explicit_path:
        raise FileNotFoundError(
            f"Config file not found: {config_path}. "
            "Check the --config path and ensure the file exists."
        )
    # else: auto-discovery found nothing, use defaults silently

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


def _provider_has_key(provider_name: str, provider_cfg: ProviderConfig) -> bool:
    """Check whether a provider has a usable API key.

    Checks the config key and the bare env var (e.g. FIREWORKS_API_KEY).
    The AI_COUNCIL__-prefixed variants are resolved by EnvConfig at load time
    and surfaced via provider_cfg.api_key, so they are covered by the first check.
    """
    if provider_cfg.api_key:
        return True
    bare_env = _BARE_ENV_VARS.get(provider_name)
    return bool(bare_env and os.environ.get(bare_env))


def resolve_agent_skills_selector(
    agent: AgentConfig, council: CouncilConfig
) -> list[str] | Literal["*"] | None:
    """Return the effective skill selector for an agent.

    Precedence:
    1. ``agent.skills`` if it is not None (including []).
    2. ``council.default_agent_skills`` if set.
    3. None.

    An explicit empty list on ``agent.skills`` is treated as an opt-out and
    returned as-is. Only ``None`` (truly unset) falls through to the default.
    """
    if agent.skills is not None:
        return agent.skills
    return council.default_agent_skills


def validate_skill_references(
    config: CouncilConfig,
    registry: Any,  # SkillRegistry — typed as Any to avoid circular import at module load
) -> None:
    """Check that every explicitly-named skill exists in the registry.

    The ``*`` sentinel is always valid. Only explicit name lists are checked.
    Checks both ``default_agent_skills`` and each agent's ``skills`` field.

    Args:
        config: Council configuration.
        registry: A SkillRegistry instance.

    Raises:
        ConfigError: Listing all (agent_context, skill_name) pairs that are missing.
    """
    from ai_council_review.exceptions import ConfigError

    missing: list[str] = []

    def _check(names: list[str], context: str) -> None:
        for name in names:
            if name not in registry:
                missing.append(f"  {context}: {name!r}")

    # Check top-level default
    if isinstance(config.default_agent_skills, list):
        _check(config.default_agent_skills, "default_agent_skills")

    # Check per-agent selectors
    for agent_name, agent_cfg in config.agents.items():
        if isinstance(agent_cfg.skills, list):
            _check(agent_cfg.skills, f"agents.{agent_name}.skills")

    if missing:
        raise ConfigError(
            "The following skills are referenced in config but not found on disk:\n"
            + "\n".join(missing)
            + f"\n\nSkills directory: {config.skills_path}\n"
            "Available skills: " + str(registry.names())
        )


def validate_skill_budgets(
    config: CouncilConfig,
    registry: Any,  # SkillRegistry — typed as Any to avoid circular import at module load
) -> None:
    """Fail fast at config-load time if any agent's resolved skills bust the hard budget.

    Mirrors what resolve_skills_for_agent would do at chain-build time, but
    runs once upfront so operators learn about budget issues at startup instead
    of mid-review. Soft-budget warnings also fire here.

    Args:
        config: Council configuration.
        registry: A SkillRegistry instance.

    Raises:
        ConfigError: When any agent's resolved skills exceed the hard token budget.
    """
    import structlog

    from ai_council_review.skills.resolution import resolve_skills_for_agent

    log = structlog.get_logger(__name__)

    for agent_name in get_canonical_agents():
        # resolve_skills_for_agent enforces both soft (warn) and hard (raise).
        skills = resolve_skills_for_agent(agent_name, config, registry)
        # Emit a per-agent INFO summary at startup so operators can confirm
        # the resolved bindings without grepping mid-run logs.
        log.info(
            "agent skill binding resolved",
            agent=agent_name,
            count=len(skills),
            names=[s.name for s in skills],
            total_tokens=sum(s.estimated_tokens() for s in skills),
        )


def validate_config(config: CouncilConfig) -> None:
    """Validate that the configuration is ready for a review run.

    Raises:
        ConfigError: If no API key is available for any enabled agent.
    """
    from ai_council_review.exceptions import ConfigError

    enabled_agents = [(name, cfg) for name, cfg in config.agents.items() if cfg.enabled]

    if not enabled_agents:
        # Default agents are implicitly enabled; if the user explicitly
        # disabled everything, we still need a key for the default set.
        # Use get_canonical_agents() (not the stale CANONICAL_AGENTS constant)
        # so the three new agents (performance, documentation, devops) are
        # included in API-key validation.
        enabled_agents = [(name, AgentConfig()) for name in get_canonical_agents()]

    missing: list[str] = []
    for name, agent_cfg in enabled_agents:
        provider = agent_cfg.model.lower()
        provider_cfg = config.providers.get(provider, ProviderConfig())
        if not _provider_has_key(provider, provider_cfg):
            missing.append(f"{name} ({provider})")

    if missing:
        raise ConfigError(
            "No LLM API key found for the following enabled agents: "
            f"{', '.join(missing)}. "
            "Set one of: FIREWORKS_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY "
            "(or the AI_COUNCIL__* prefixed variants) in your environment or "
            ".ai-council/config.yaml. See README.md > Quick Start."
        )
