"""Tests for ai_council_review.utils.debug."""

from __future__ import annotations

import json
from pathlib import Path

from ai_council_review.models import PRMetadata, ReviewState
from ai_council_review.utils.debug import (
    _is_secret_key,
    _strip_secrets,
    dump_state,
)


class TestDumpState:
    """Tests for dump_state."""

    def test_dump_state_writes_file(self, tmp_path: Path) -> None:
        """dump_state writes JSON."""
        state = ReviewState(
            pr_metadata=PRMetadata(
                number=42,
                title="Test PR",
                state="open",
                author="test",
                author_association="OWNER",
                base_ref="main",
                base_sha="abc",
                head_ref="feat",
                head_sha="def",
            ),
        )
        output_path = tmp_path / "debug.json"
        result = dump_state(state, output_path=output_path)

        assert result == output_path
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["pr_metadata"]["number"] == 42

    def test_dump_state_strips_secrets(self, tmp_path: Path) -> None:
        """The dumped file has no secrets."""
        state = ReviewState(
            pr_metadata=PRMetadata(
                number=42,
                title="Test PR",
                body="API key is sk-abc123",
                state="open",
                author="test",
                author_association="OWNER",
                base_ref="main",
                base_sha="abc",
                head_ref="feat",
                head_sha="def",
            ),
        )
        output_path = tmp_path / "debug.json"
        result = dump_state(state, output_path=output_path)

        text = result.read_text()
        assert "sk-abc123" not in text
        assert "42" in text


class TestStripSecrets:
    """Tests for _strip_secrets."""

    def test_strip_secrets_redacts_dict_keys(self) -> None:
        """Secret keys are redacted."""
        data = {
            "api_key": "super-secret",
            "normal_key": "keep-this",
            "nested": {
                "token": "nested-token",
            },
        }
        result = _strip_secrets(data)

        assert result["api_key"] == "***REDACTED***"
        assert result["normal_key"] == "keep-this"
        assert result["nested"]["token"] == "***REDACTED***"

    def test_strip_secrets_redacts_api_keys(self) -> None:
        """API key strings are redacted."""
        data = {
            "message": "sk-abc123",
            "note": "ghp_abcdef",
            "normal": "hello world",
        }
        result = _strip_secrets(data)

        assert result["message"] == "***REDACTED***"
        assert result["note"] == "***REDACTED***"
        assert result["normal"] == "hello world"


class TestIsSecretKey:
    """Tests for _is_secret_key."""

    def test_is_secret_key(self) -> None:
        """Case-insensitive matching."""
        assert _is_secret_key("api_key") is True
        assert _is_secret_key("API_KEY") is True
        assert _is_secret_key("ApiKey") is True
        assert _is_secret_key("token") is True
        assert _is_secret_key("TOKEN") is True
        assert _is_secret_key("normal_key") is False
        assert _is_secret_key("description") is False
