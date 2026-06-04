"""Synthesis agent — merges findings from all agents into a coherent review."""

from __future__ import annotations

import json
from typing import Any, cast

import structlog
from pydantic import BaseModel

from ai_council_review.config import AgentConfig, CouncilConfig
from ai_council_review.llm.prompts.loader import load_prompt
from ai_council_review.llm.providers.factory import LLMProviderFactory
from ai_council_review.models import Finding, ReviewState

logger = structlog.get_logger()


class SynthesisOutput(BaseModel):
    """Structured output from the synthesis agent."""

    summary: str
    verdict: str
    findings: list[Finding]
    categories: list[str]


def _build_synthesis_variables(state: ReviewState) -> dict[str, Any]:
    """Build prompt variables for the synthesis agent.

    Args:
        state: Current review state.

    Returns:
        Dict of prompt template variables.
    """
    all_findings: list[dict[str, Any]] = []
    for agent_name, findings in state.agent_outputs.items():
        for finding in findings:
            all_findings.append(
                {
                    "agent": agent_name,
                    "path": finding.path,
                    "position": finding.position,
                    "severity": finding.severity.value,
                    "category": finding.category,
                    "body": finding.body,
                    "confidence": finding.confidence,
                    "line": finding.line,
                }
            )

    findings_json = json.dumps(all_findings, indent=2)

    pr = state.pr_metadata
    pr_title = pr.title if pr else ""
    pr_number = pr.number if pr else 0
    repo = pr.html_url if pr else ""

    return {
        "repo": repo,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "findings_json": findings_json,
    }


def build_synthesis_chain(config: CouncilConfig) -> Any:
    """Build an LCEL chain for the synthesis agent.

    Args:
        config: Global council configuration.

    Returns:
        Runnable chain that outputs SynthesisOutput.
    """
    agent_config = config.agents.get("synthesis", None)
    if agent_config is None:
        agent_config = AgentConfig(
            enabled=True,
            model="fireworks",
            model_name="accounts/fireworks/models/llama-v3p1-70b-instruct",
            temperature=0.2,
            max_tokens=4000,
        )

    llm = LLMProviderFactory.from_config(agent_config, config.providers)
    prompt = load_prompt("synthesis")
    return prompt | llm.with_structured_output(SynthesisOutput)


def _fallback_synthesize(all_findings: list[dict[str, Any]]) -> SynthesisOutput:
    """Manual synthesis when LLM fails.

    Args:
        all_findings: Raw findings from all agents.

    Returns:
        SynthesisOutput.
    """
    # Deduplicate by (path, position, normalized_body)
    seen: set[str] = set()
    deduped: list[Finding] = []
    for f in all_findings:
        key = f"{f['path']}:{f.get('position', 'none')}:{f['body'][:50].lower().strip()}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(
            Finding(
                path=f["path"],
                position=f.get("position"),
                severity=f["severity"],
                category=f["category"],
                body=f["body"],
                confidence=f.get("confidence", 0.8),
                line=f.get("line"),
            )
        )

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    deduped.sort(key=lambda finding: severity_order.get(finding.severity.value, 5))

    # Build summary
    categories = sorted({finding.category for finding in deduped})
    severity_counts: dict[str, int] = {}
    for finding in deduped:
        severity_counts[finding.severity.value] = severity_counts.get(finding.severity.value, 0) + 1

    summary_parts = ["## AI Code Review\n"]
    summary_parts.append("\n**Findings by severity:**\n")
    for severity, count in sorted(
        severity_counts.items(),
        key=lambda x: severity_order.get(x[0], 5),
    ):
        summary_parts.append(f"- {severity.capitalize()}: {count}")
    summary_parts.append(f"\n**Total findings:** {len(deduped)}")
    summary_parts.append(
        "\n---\n\n*This review was generated automatically. Please verify all suggestions before applying.*"
    )
    summary = "\n".join(summary_parts)

    # Determine verdict
    if any(f.severity.value == "critical" for f in deduped):
        verdict = "request_changes"
    elif deduped:
        verdict = "comment"
    else:
        verdict = "approve"

    return SynthesisOutput(
        summary=summary,
        verdict=verdict,
        findings=deduped,
        categories=categories,
    )


def run_synthesis_agent(
    state: ReviewState,
    config: CouncilConfig,
    callbacks: list[Any] | None = None,
) -> SynthesisOutput:
    """Run the synthesis agent.

    Args:
        state: Current review state with agent_outputs populated.
        config: Council configuration.
        callbacks: Optional LangChain callbacks (e.g., CostCallbackHandler).

    Returns:
        SynthesisOutput with merged findings, summary, and verdict.
    """
    logger.info("Synthesis agent starting")
    chain = build_synthesis_chain(config)

    try:
        variables = _build_synthesis_variables(state)
        run_config = {"callbacks": callbacks} if callbacks else None
        result = chain.invoke(variables, config=run_config)
        synthesis_output = cast(SynthesisOutput, result)
        logger.info(
            "Synthesis complete",
            findings=len(synthesis_output.findings),
            verdict=synthesis_output.verdict,
            categories=synthesis_output.categories,
        )
        return synthesis_output
    except Exception as e:
        logger.error("Synthesis failed", error=str(e))
        all_findings: list[dict[str, Any]] = []
        for agent_name, findings in state.agent_outputs.items():
            for finding in findings:
                all_findings.append(
                    {
                        "agent": agent_name,
                        "path": finding.path,
                        "position": finding.position,
                        "severity": finding.severity.value,
                        "category": finding.category,
                        "body": finding.body,
                        "confidence": finding.confidence,
                        "line": finding.line,
                    }
                )
        return _fallback_synthesize(all_findings)
