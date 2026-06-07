"""Agent output parsing utilities."""

from __future__ import annotations

import json
import re
from typing import Any

import structlog

from ai_council_review.models import Finding

logger = structlog.get_logger()


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
        normalized["severity"] = str(item["severity"]).lower()
    elif "level" in item:
        normalized["severity"] = str(item["level"]).lower()
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
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
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
