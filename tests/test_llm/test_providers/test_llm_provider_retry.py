"""Tests for ai_council_review.llm_provider retry behavior."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_council_review.exceptions import LLMProviderError
from ai_council_review.llm.providers import LLMProviderFactory


class TestLLMProviderRetry:
    """Tests for LLM provider retry logic."""

    def test_create_retries_on_transient_error(self) -> None:
        """Verify retry on connection error."""
        mock_fireworks = MagicMock()
        mock_fireworks.side_effect = [
            ConnectionError("transient"),
            MagicMock(),
        ]

        with (
            patch.dict(
                LLMProviderFactory._providers,
                {"fireworks": mock_fireworks},
                clear=False,
            ),
            patch("ai_council_review.llm.providers.factory.time.sleep"),
            patch(
                "ai_council_review.llm.providers.factory.random.uniform",
                return_value=0.5,
            ),
        ):
            model = LLMProviderFactory.create(
                "fireworks",
                model_name="accounts/fireworks/models/llama-v3p1-70b-instruct",
                api_key="test-key",
            )

        assert model is not None
        assert mock_fireworks.call_count == 2

    def test_create_fails_fast_on_non_transient(self) -> None:
        """Verify no retry on non-transient error."""
        mock_fireworks = MagicMock()
        mock_fireworks.side_effect = TypeError("non-transient")

        with (
            patch.dict(
                LLMProviderFactory._providers,
                {"fireworks": mock_fireworks},
                clear=False,
            ),
            patch("ai_council_review.llm.providers.factory.time.sleep"),
            pytest.raises(LLMProviderError),
        ):
            LLMProviderFactory.create(
                "fireworks",
                model_name="accounts/fireworks/models/llama-v3p1-70b-instruct",
                api_key="test-key",
            )

        assert mock_fireworks.call_count == 1
