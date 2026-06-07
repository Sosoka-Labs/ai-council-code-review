"""Agent output parsing utilities."""

from __future__ import annotations

import json
import re

from ai_council_review.models import Finding


def parse_findings(text: str, agent_name: str | None = None) -> list[Finding]:
    """Parse findings from agent output string.

    Handles markdown code blocks, extra text, and extracts JSON arrays.

    Args:
        text: Raw agent output.
        agent_name: Optional agent name to tag each finding with.

    Returns:
        List of parsed findings. Empty list on failure.
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    # Strip markdown code blocks if present
    if text.startswith("```"):
        # Remove the opening ```json or ```
        text = text.split("\n", 1)[1] if "\n" in text else text
        # Remove the closing ```
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    # Try direct JSON parse first
    try:
        data = json.loads(text)
        if isinstance(data, list):
            findings = [Finding(**item) for item in data if isinstance(item, dict)]
            if agent_name:
                for f in findings:
                    f.agent = agent_name
            return findings
    except Exception:
        pass

    # Try to extract the first JSON array from the text
    try:
        # Find text that looks like a JSON array: starts with [ and ends with ]
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                findings = [Finding(**item) for item in data if isinstance(item, dict)]
                if agent_name:
                    for f in findings:
                        f.agent = agent_name
                return findings
    except Exception:
        pass

    return []
