"""Debug utilities — dump review state artifacts, strip secrets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from ai_council_review.models import ReviewState

logger = structlog.get_logger()

# Sensitive keys to strip from state dumps
_SECRET_KEYS = {
    "token",
    "api_key",
    "apikey",
    "api-key",
    "secret",
    "password",
    "auth",
    "authorization",
    "private_key",
    "fireworks_api_key",
    "openai_api_key",
    "anthropic_api_key",
    "github_token",
}

_DEBUG_FILENAME = "ai_council_review_debug.json"


def dump_state(state: ReviewState, output_path: str | Path | None = None) -> Path:
    """Dump the review state to a JSON file for debugging.

    Strips all secrets before writing.

    Args:
        state: The review state to dump.
        output_path: Path to write the debug file. If None, writes to
            the current working directory.

    Returns:
        Path to the written debug file.
    """
    output_path = Path.cwd() / _DEBUG_FILENAME if output_path is None else Path(output_path)

    data = state.model_dump(mode="json", exclude_none=True)
    safe_data = _strip_secrets(data)

    output_path.write_text(json.dumps(safe_data, indent=2, default=str), encoding="utf-8")
    logger.info("Debug state dumped", path=str(output_path))

    return output_path


def _strip_secrets(data: Any) -> Any:
    """Recursively strip secret values from a data structure.

    Args:
        data: The data structure to strip.

    Returns:
        The stripped data structure.
    """
    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            if _is_secret_key(key) or (isinstance(value, str) and _looks_like_secret(value)):
                result[key] = "***REDACTED***"
            else:
                result[key] = _strip_secrets(value)
        return result
    elif isinstance(data, list):
        return [_strip_secrets(item) for item in data]
    elif isinstance(data, str) and _looks_like_secret(data):
        return "***REDACTED***"
    return data


def _is_secret_key(key: str) -> bool:
    """Check if a key is a secret key.

    Args:
        key: The key to check.

    Returns:
        True if the key is a secret key.
    """
    return key.lower() in _SECRET_KEYS


def _looks_like_secret(value: str) -> bool:
    """Check if a string looks like a secret (API key, token, etc.).

    Args:
        value: The string to check.

    Returns:
        True if the string looks like a secret.
    """
    prefixes = ("sk-", "fw-", "ghp_", "ghs_", "github_pat_")
    return any(value.startswith(prefix) for prefix in prefixes)
