"""Agent output parsing utilities."""

from __future__ import annotations

import json
from typing import Any

import structlog

from ai_council_review.models import Finding

logger = structlog.get_logger()

_SEVERITY_ALIASES: dict[str, str] = {
    "warning": "medium",
    "error": "high",
    "blocker": "critical",
    "info": "low",
    "note": "low",
}

_VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}


def _extract_first_json_array(text: str) -> str | None:
    """Extract the first balanced JSON array using brace counting.

    Unlike a greedy regex, this correctly handles nested arrays and is not
    susceptible to adversarial input that contains multiple ``[...]`` spans.
    """
    start = text.find("[")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(text[start:], start=start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _normalize_finding(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw finding dict to match the Finding schema.

    Handles common field name variations from different LLM outputs.
    """
    normalized: dict[str, Any] = {}

    # Map common field name variations
    if "path" in item:
        normalized["path"] = item["path"]
    elif "title" in item:
        normalized["path"] = item["title"]
    elif "file" in item:
        normalized["path"] = item["file"]
    else:
        normalized["path"] = "unknown"

    # Some LLMs return "position" when they mean a file line number; always
    # treat it as "line" so downstream code can compute the diff position.
    if "line" in item:
        normalized["line"] = item["line"]
    elif "position" in item:
        normalized["line"] = item["position"]
    # We intentionally do NOT set "position" here — the graph layer computes
    # the correct diff position from the file line number and the patch.

    if "severity" in item:
        raw = str(item["severity"]).lower()
        normalized["severity"] = _SEVERITY_ALIASES.get(raw, raw) if raw not in _VALID_SEVERITIES else raw
    elif "level" in item:
        raw = str(item["level"]).lower()
        normalized["severity"] = _SEVERITY_ALIASES.get(raw, raw) if raw not in _VALID_SEVERITIES else raw
    else:
        normalized["severity"] = "medium"

    normalized["category"] = item.get("category", "quality")

    if "body" in item:
        normalized["body"] = item["body"]
    elif "description" in item:
        normalized["body"] = item["description"]
    elif "message" in item:
        normalized["body"] = item["message"]
    else:
        normalized["body"] = "No description provided"

    if "confidence" in item:
        normalized["confidence"] = item["confidence"]
    elif "score" in item:
        normalized["confidence"] = item["score"]

    if "agent" in item:
        normalized["agent"] = item["agent"]

    return normalized


def parse_findings(text: str, agent_name: str | None = None, logger: Any = None) -> list[Finding]:
    """Parse findings from agent output string.

    Used by generalist agent only. Specialist agents use with_structured_output().

    Handles markdown code blocks, extra text, and extracts JSON arrays.
    Normalizes common field name variations from different LLM outputs.

    Args:
        text: Raw agent output.
        agent_name: Optional agent name to tag each finding with.
        logger: Optional logger for debugging parse failures.

    Returns:
        List of parsed findings. Empty list on failure.
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    # Strip markdown code blocks if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    # Try direct JSON parse first
    try:
        data = json.loads(text)
        if isinstance(data, list):
            findings = []
            for item in data:
                if isinstance(item, dict):
                    normalized = _normalize_finding(item)
                    if agent_name:
                        normalized["agent"] = agent_name
                    try:
                        findings.append(Finding(**normalized))
                    except Exception as e:
                        if logger:
                            logger.warning("Failed to create Finding", error=str(e), item=item)
            return findings
    except Exception:
        pass

    # Try to extract the first JSON array from the text
    try:
        extracted = _extract_first_json_array(text)
        if extracted:
            data = json.loads(extracted)
            if isinstance(data, list):
                findings = []
                for item in data:
                    if isinstance(item, dict):
                        normalized = _normalize_finding(item)
                        if agent_name:
                            normalized["agent"] = agent_name
                        try:
                            findings.append(Finding(**normalized))
                        except Exception as e:
                            if logger:
                                logger.warning("Failed to create Finding", error=str(e), item=item)
                return findings
    except Exception:
        pass

    return []
