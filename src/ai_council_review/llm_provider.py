"""LLM provider factory for Fireworks, OpenAI, and Anthropic."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
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
    def _is_transient_error(cls, exc: Exception) -> bool:
        """Check if an exception is a transient error that warrants retry.

        Args:
            exc: The exception to check.

        Returns:
            True if the error is transient, False otherwise.
        """
        if isinstance(exc, ConnectionError | TimeoutError):
            return True
        return "rate limit" in str(exc).lower()

    @classmethod
    def _with_retry(cls, func: Callable[[], BaseChatModel]) -> BaseChatModel:
        """Execute a function with retry logic for transient errors.

        Args:
            func: The function to execute.

        Returns:
            The result of the function.

        Raises:
            LLMProviderError: If the function fails after all retries.
        """
        max_retries = 3
        max_delay = 30.0
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if not cls._is_transient_error(e) or attempt >= max_retries - 1:
                    raise LLMProviderError(
                        f"Failed to initialize LLM provider: {e}"
                    ) from e
                delay = min(max_delay, (2 ** attempt) + random.uniform(0, 1))
                logger.warning(
                    "LLM initialization failed, retrying...",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    delay=delay,
                    error=str(e),
                )
                time.sleep(delay)
        raise LLMProviderError("Max retries exceeded")

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
                f"Unsupported provider: {provider_name}. "
                f"Supported: {list(cls._providers.keys())}"
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

        def _init() -> BaseChatModel:
            return model_cls(**init_kwargs)

        return cls._with_retry(_init)

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
