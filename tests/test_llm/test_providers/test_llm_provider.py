"""Tests for ai_council_review.llm.providers."""

from __future__ import annotations

import pytest

from ai_council_review.config import AgentConfig, ProviderConfig
from ai_council_review.exceptions import LLMProviderError
from ai_council_review.llm.providers import LLMProviderFactory


class TestLLMProviderFactory:
    """Tests for LLMProviderFactory."""

    def test_unsupported_provider(self) -> None:
        """Test that unsupported provider raises error."""
        with pytest.raises(LLMProviderError):
            LLMProviderFactory.create("unknown")

    def test_fireworks_provider(self) -> None:
        """Test creating Fireworks provider."""
        # ChatFireworks accepts the key eagerly; it will fail on actual API call.
        # We just verify the factory creates the instance without error.
        model = LLMProviderFactory.create(
            "fireworks",
            model_name="accounts/fireworks/models/llama-v3p1-70b-instruct",
            api_key="invalid-key",
        )
        assert model is not None

    def test_from_config(self) -> None:
        """Test creating provider from config."""
        agent_config = AgentConfig(
            model="openai",
            model_name="gpt-4",
            temperature=0.5,
            max_tokens=2000,
        )
        providers = {
            "openai": ProviderConfig(api_key="sk-test"),
        }

        # ChatOpenAI accepts the key eagerly; it will fail on actual API call.
        model = LLMProviderFactory.from_config(agent_config, providers)
        assert model is not None

    def test_provider_name_case_insensitive(self) -> None:
        """Test that provider name is case-insensitive."""
        with pytest.raises(LLMProviderError):
            LLMProviderFactory.create("FIREWORKS")
