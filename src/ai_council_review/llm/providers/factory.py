"""LLM provider factory for Fireworks, OpenAI, and Anthropic."""

from __future__ import annotations

from typing import Any

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_fireworks import ChatFireworks
from langchain_openai import ChatOpenAI

from ai_council_review.config import AgentConfig, ProviderConfig
from ai_council_review.exceptions import LLMProviderError

logger = structlog.get_logger()


class LLMProviderFactory:
    """Factory for creating LangChain chat models from config."""

    _providers: dict[str, type[BaseChatModel]] = {
        "fireworks": ChatFireworks,
        "openai": ChatOpenAI,
        "anthropic": ChatAnthropic,
    }

    @classmethod
    def create(
        cls,
        provider_name: str,
        model_name: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        **kwargs: Any,
    ) -> BaseChatModel:
        """Create a LangChain chat model instance.

        Args:
            provider_name: Provider identifier ("fireworks", "openai", "anthropic").
            model_name: Model name/identifier. If None, uses provider default.
            api_key: API key. If None, relies on provider's default env var.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional provider-specific arguments.

        Returns:
            Configured BaseChatModel instance.

        Raises:
            LLMProviderError: If the provider is not supported or initialization fails.
        """
        provider_name = provider_name.lower()
        if provider_name not in cls._providers:
            raise LLMProviderError(
                f"Unsupported provider: {provider_name}. Supported: {list(cls._providers.keys())}"
            )

        model_cls = cls._providers[provider_name]
        init_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if model_name and provider_name in ("fireworks", "openai", "anthropic"):
            init_kwargs["model"] = model_name

        if api_key:
            if provider_name == "fireworks":
                init_kwargs["fireworks_api_key"] = api_key
            elif provider_name == "openai":
                init_kwargs["api_key"] = api_key
            elif provider_name == "anthropic":
                init_kwargs["anthropic_api_key"] = api_key

        init_kwargs.update(kwargs)

        try:
            return model_cls(**init_kwargs)
        except Exception as e:
            raise LLMProviderError(f"Failed to initialize LLM provider: {e}") from e

    @classmethod
    def from_config(
        cls, agent_config: AgentConfig, providers: dict[str, ProviderConfig]
    ) -> BaseChatModel:
        """Create a model from agent and provider config.

        Args:
            agent_config: Agent configuration with model settings.
            providers: Provider configurations with API keys.

        Returns:
            Configured BaseChatModel instance.
        """
        provider_name = agent_config.model
        provider_cfg = providers.get(provider_name, ProviderConfig())
        api_key = provider_cfg.api_key

        return cls.create(
            provider_name=provider_name,
            model_name=agent_config.model_name,
            api_key=api_key,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens,
        )
