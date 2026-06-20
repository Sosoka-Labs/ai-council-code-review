"""LangGraph state machine for AI Council Code Review."""

from __future__ import annotations

import os
from typing import Any

import structlog
from langgraph.graph import END, START, StateGraph

from ai_council_review.config import AgentConfig, CouncilConfig
from ai_council_review.github.client import GitHubClient
from ai_council_review.github.ingestor import PRIngestor
from ai_council_review.github.publisher import Publisher
from ai_council_review.llm.agents.registry import SPECIALIST_AGENTS, SPECIALIST_BY_NAME
from ai_council_review.llm.agents.router import run_router_agent
from ai_council_review.llm.agents.specialist import run_specialist_agent
from ai_council_review.llm.agents.synthesis import run_synthesis_agent
from ai_council_review.llm.cost_tracker import CostCallbackHandler, CostTracker
from ai_council_review.llm.selection import select_inline_findings
from ai_council_review.models import FileInfo, Finding, ReviewComment, ReviewState
from ai_council_review.skills.registry import SkillRegistry
from ai_council_review.utils.patch_parser import get_position_for_line

logger = structlog.get_logger()

# Max specialists when review_depth == "standard" (M4 guardrail).
# "deep" depth is uncapped so all requested specialists can run in parallel.
_MAX_SPECIALISTS_STANDARD = 4


def ingest_node(state: ReviewState, config: CouncilConfig) -> dict[str, Any]:
    """Ingest PR metadata and changed files.

    Args:
        state: Current review state.
        config: Council configuration.

    Returns:
        Updates to the state.
    """
    logger.info("Ingest node starting")
    ingestor = PRIngestor(config)

    # Load from environment if available
    payload = None
    if os.environ.get("GITHUB_EVENT_PATH"):
        payload = ingestor.load_event_payload()

    pr, files, skipped, skip_reason = ingestor.ingest(payload)

    if skipped:
        return {
            "pr_metadata": pr,
            "skipped": True,
            "skip_reason": skip_reason,
        }

    # Fetch files from GitHub if we have a token
    token = os.environ.get("GITHUB_TOKEN")
    if token and pr:
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if repo:
            client = GitHubClient(token, repo)
            raw_files = client.get_pr_files(pr.number)
            files = [
                FileInfo(
                    filename=f["filename"],
                    status=f["status"],
                    additions=f.get("additions", 0),
                    deletions=f.get("deletions", 0),
                    changes=f.get("changes", 0),
                    patch=f.get("patch"),
                    previous_filename=f.get("previous_filename"),
                    sha=f.get("sha"),
                    raw_url=f.get("raw_url"),
                )
                for f in raw_files
            ]
            files = ingestor.filter_files(files)

    return {
        "pr_metadata": pr,
        "changed_files": files,
        "skipped": skipped,
        "skip_reason": skip_reason,
    }


def router_node(
    state: ReviewState,
    config: CouncilConfig,
    registry: SkillRegistry | None = None,
) -> dict[str, Any]:
    """Run the router agent to decide which agents are needed.

    Args:
        state: Current review state.
        config: Council configuration.
        registry: Optional skill registry for descriptions-only catalog injection.

    Returns:
        Updates to the state with routing decision.
    """
    logger.info("Router node starting")

    if state.skipped:
        return {}

    if not state.changed_files:
        logger.info("No files to review")
        return {}

    result = run_router_agent(state, config, registry=registry)

    # Effective depth: escalate to "deep" if either the router or the user's
    # config requests it.  This means `review_depth: deep` in .ai-council/config.yaml
    # is always honored — previously config.review_depth was never consulted here.
    effective_depth = (
        "deep" if config.review_depth == "deep" or result.review_depth == "deep" else "standard"
    )

    # M4 guardrail: cap parallel specialists for standard depth.
    # "deep" depth is intentionally uncapped to allow all requested specialists.
    agents_needed = result.agents_needed
    if effective_depth == "standard":
        agents_needed = agents_needed[:_MAX_SPECIALISTS_STANDARD]
        if len(result.agents_needed) > _MAX_SPECIALISTS_STANDARD:
            logger.info(
                "M4: capped specialists for review depth",
                depth=effective_depth,
                original=result.agents_needed,
                capped=agents_needed,
            )

    logger.info(
        "Router complete",
        agents=agents_needed,
        depth=effective_depth,
    )

    return {
        "agents_needed": agents_needed,
        "review_depth": effective_depth,
    }


def _make_cost_callback(
    cost_tracker: CostTracker | None,
    agent_name: str,
    config: CouncilConfig,
) -> list[Any] | None:
    """Create a CostCallbackHandler if a tracker is available.

    Args:
        cost_tracker: CostTracker instance.
        agent_name: Agent identifier.
        config: Council configuration.

    Returns:
        List containing the handler, or None.
    """
    if cost_tracker is None:
        return None
    agent_config = config.agents.get(agent_name, AgentConfig())
    if agent_config.model_name is None:
        raise ValueError(
            f"model_name must not be None for agent '{agent_name}' — "
            "this is a bug in AgentConfig validator"
        )
    handler = CostCallbackHandler(
        cost_tracker=cost_tracker,
        agent_name=agent_name,
        model_name=agent_config.model_name,
        max_tokens=agent_config.max_tokens,
    )
    return [handler]


def _make_specialist_node(
    agent_name: str,
    config: CouncilConfig,
    cost_tracker: CostTracker | None,
    registry: SkillRegistry | None,
) -> Any:
    """Factory that returns a callable graph node for the given specialist.

    Args:
        agent_name: Agent name matching an entry in SPECIALIST_BY_NAME.
        config: Council configuration.
        cost_tracker: Optional cost tracker.
        registry: Optional skill registry.

    Returns:
        Callable ``(state) -> dict`` for LangGraph.
    """
    spec = SPECIALIST_BY_NAME[agent_name]

    def _node(state: ReviewState) -> dict[str, Any]:
        if state.skipped:
            return {}
        callbacks = _make_cost_callback(cost_tracker, agent_name, config)
        findings = run_specialist_agent(spec, state, config, callbacks=callbacks, registry=registry)
        return {"agent_outputs": {agent_name: findings}}

    _node.__name__ = f"{agent_name}_node"
    return _node


def synthesis_node(
    state: ReviewState,
    config: CouncilConfig,
    cost_tracker: CostTracker | None = None,
) -> dict[str, Any]:
    """Run the synthesis agent to merge findings.

    Args:
        state: Current review state.
        config: Council configuration.
        cost_tracker: Optional cost tracker for budget enforcement.

    Returns:
        Updates to the state.
    """
    logger.info("Synthesis node starting")

    if state.skipped:
        return {}

    if not state.agent_outputs:
        logger.info("No agent outputs to synthesize")
        return {}

    callbacks = _make_cost_callback(cost_tracker, "synthesis", config)
    result = run_synthesis_agent(state, config, callbacks=callbacks)

    return {
        "summary": result.summary,
        "verdict": result.verdict,
        "agent_outputs": {"synthesis": result.findings},
    }


def post_node(state: ReviewState, config: CouncilConfig) -> dict[str, Any]:
    """Post the review to GitHub.

    Args:
        state: Current review state.
        config: Council configuration.

    Returns:
        Updates to the state.
    """
    logger.info("Post node starting")

    if state.skipped:
        logger.info("PR skipped, nothing to post", reason=state.skip_reason)
        return {}

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo or not state.pr_metadata:
        logger.warning("Missing token, repo, or PR metadata — skipping post")
        return {}

    client = GitHubClient(token, repo)
    publisher = Publisher(client)

    # Build findings from all agents (excluding synthesis)
    all_findings: list[Finding] = []
    for agent_name, agent_findings in state.agent_outputs.items():
        if agent_name != "synthesis":
            all_findings.extend(agent_findings)

    if not all_findings:
        logger.info("No findings to post")
        summary = "## AI Code Review\n\nNo issues found in this PR. ✅"
        publisher.post_review(
            pr_number=state.pr_metadata.number,
            summary=summary,
            comments=[],
            commit_id=state.pr_metadata.head_sha,
        )
        return {
            "summary": summary,
            "verdict": "approve",
        }

    # Build a patch lookup for position computation
    patch_lookup: dict[str, str] = {}
    for file in state.changed_files:
        if file.patch:
            patch_lookup[file.filename] = file.patch

    # Partition findings into those postable as inline comments (line resolves to
    # an added line in the patch) and those that can only appear in the body.
    postable: list[Finding] = []
    non_postable: list[Finding] = []
    for finding in all_findings:
        is_postable = False
        if finding.line is not None:
            patch = patch_lookup.get(finding.path)
            if patch:
                # get_position_for_line only returns a value for added lines
                is_postable = get_position_for_line(patch, finding.line) is not None

        if is_postable:
            postable.append(finding)
        else:
            non_postable.append(finding)
            logger.info(
                "Finding not postable as inline comment (not an added line in patch)",
                path=finding.path,
                line=finding.line,
            )

    # Apply confidence threshold and hard cap — operates on postable set only.
    selection = select_inline_findings(
        postable,
        max_comments=config.max_inline_comments,
        min_confidence=config.min_confidence,
    )

    logger.info(
        "Inline comment selection complete",
        selected=len(selection.selected),
        omitted_low_confidence=len(selection.omitted_low_confidence),
        omitted_over_cap=len(selection.omitted_over_cap),
        non_postable=len(non_postable),
    )

    # Build inline comment objects from the selected findings only.
    comments: list[ReviewComment] = []
    for finding in selection.selected:
        body_parts: list[str] = []
        if finding.agent:
            body_parts.append(f"**🤖 {finding.agent.capitalize()} Agent**")
            body_parts.append("")
        body_parts.append(finding.body)
        if finding.confidence is not None:
            body_parts.append("")
            body_parts.append(f"_Confidence: {finding.confidence:.0%}_")
        body = "\n".join(body_parts)

        comments.append(
            ReviewComment(
                path=finding.path,
                line=finding.line,
                side="RIGHT",
                body=body,
            )
        )

    # Validate comments against changed files
    comments = publisher.validate_comments(comments, state.changed_files)

    # Build summary from synthesis if available
    summary_text: str = state.summary or ""
    if not summary_text:
        summary_parts = ["## AI Code Review\n"]
        severity_counts: dict[str, int] = {}
        agent_counts: dict[str, int] = {}
        for finding in all_findings:
            severity_counts[finding.severity.value] = (
                severity_counts.get(finding.severity.value, 0) + 1
            )
            agent_name_str = finding.agent or "unknown"
            agent_counts[agent_name_str] = agent_counts.get(agent_name_str, 0) + 1

        summary_parts.append("\n**Findings by severity:**\n")
        for severity, count in sorted(
            severity_counts.items(),
            key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(x[0], 5),
        ):
            summary_parts.append(f"- {severity.capitalize()}: {count}")

        summary_parts.append("\n**Findings by agent:**\n")
        for agent_name_str, count in sorted(agent_counts.items()):
            summary_parts.append(f"- {agent_name_str.capitalize()}: {count}")

        summary_parts.append(f"\n**Total findings:** {len(all_findings)}")
        summary_parts.append(
            "\n---\n\n*This review was generated automatically. Please verify all suggestions before applying.*"
        )
        summary_text = "\n".join(summary_parts)

    # Append a withheld-findings note when any postable findings were not posted inline.
    withheld_findings = selection.omitted_low_confidence + selection.omitted_over_cap
    total_withheld = len(withheld_findings) + len(non_postable)
    if total_withheld > 0:
        n_selected = len(selection.selected)
        n_below_threshold = len(selection.omitted_low_confidence)
        n_over_cap = len(selection.omitted_over_cap)
        n_outside_lines = len(non_postable)

        withheld_parts: list[str] = [
            "",
            "---",
            "",
            f"ℹ️ {n_selected} comment(s) posted inline (ranked by severity, then "
            f"confidence). {total_withheld} finding(s) withheld — "
            f"{n_below_threshold} below the confidence threshold, "
            f"{n_over_cap} over the inline cap ({config.max_inline_comments}), "
            f"{n_outside_lines} outside changed lines. Full list below:",
            "",
            "**Withheld findings:**",
        ]
        for f in withheld_findings + non_postable:
            first_line = f.body.splitlines()[0] if f.body else ""
            withheld_parts.append(f"- `{f.path}:{f.line}` — {f.severity.value} — {first_line}")

        summary_text = summary_text + "\n" + "\n".join(withheld_parts)

    verdict = state.verdict or "comment"

    publisher.post_review(
        pr_number=state.pr_metadata.number,
        summary=summary_text,
        comments=comments,
        commit_id=state.pr_metadata.head_sha,
    )

    return {
        "summary": summary_text,
        "github_comments": comments,
        "verdict": verdict,
    }


def _route_from_router(state: ReviewState) -> list[str]:
    """Determine which agents to run based on router output.

    Filters the router's agent list to only those present in the registry so
    unknown names from the LLM are silently dropped rather than causing a graph
    routing error.

    Args:
        state: Current review state.

    Returns:
        List of agent node names to execute.
    """
    return [a for a in state.agents_needed if a in SPECIALIST_BY_NAME]


def build_graph(config: CouncilConfig, registry: SkillRegistry | None = None) -> Any:
    """Build the LangGraph state machine with multi-agent routing.

    The graph is built entirely from ``SPECIALIST_AGENTS`` — adding a new agent
    to the registry automatically produces a new node and fan-in edge here without
    any further changes to this function.

    Args:
        config: Council configuration.
        registry: Optional skill registry. When provided, domain-knowledge skill
            files are injected into each specialist agent's system prompt at
            chain build time. Defaults to None for backwards compatibility.

    Returns:
        Compiled StateGraph.
    """
    workflow = StateGraph(ReviewState)

    # Initialize cost tracker for the entire graph run
    cost_tracker = CostTracker(config)

    # Fixed nodes
    workflow.add_node("ingest", lambda state: ingest_node(state, config))
    workflow.add_node("router", lambda state: router_node(state, config, registry=registry))
    workflow.add_node("synthesis", lambda state: synthesis_node(state, config, cost_tracker))
    workflow.add_node("post", lambda state: post_node(state, config))

    # Specialist nodes — built from the registry so adding an AgentSpec is enough.
    specialist_names: list[str] = []
    for spec in SPECIALIST_AGENTS:
        workflow.add_node(
            spec.name,
            _make_specialist_node(spec.name, config, cost_tracker, registry),
        )
        specialist_names.append(spec.name)

    # Edges
    workflow.add_edge(START, "ingest")
    workflow.add_edge("ingest", "router")

    # Conditional routing from router — agents are selected dynamically.
    workflow.add_conditional_edges(
        "router",
        _route_from_router,
        specialist_names,
    )

    # All specialist nodes converge to synthesis.
    for name in specialist_names:
        workflow.add_edge(name, "synthesis")

    workflow.add_edge("synthesis", "post")
    workflow.add_edge("post", END)

    return workflow.compile()
