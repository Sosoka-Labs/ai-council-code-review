"""LangGraph state machine for AI Council Code Review."""

from __future__ import annotations

import os
from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from ai_council_review.config import AgentConfig, CouncilConfig
from ai_council_review.github.browser import RepositoryBrowser
from ai_council_review.github.client import GitHubClient
from ai_council_review.github.ingestor import PRIngestor
from ai_council_review.github.publisher import Publisher
from ai_council_review.llm.agents.architecture import run_architecture_agent
from ai_council_review.llm.agents.quality import run_quality_agent
from ai_council_review.llm.agents.router import run_router_agent
from ai_council_review.llm.agents.security import run_security_agent
from ai_council_review.llm.agents.synthesis import run_synthesis_agent
from ai_council_review.llm.cost_tracker import CostCallbackHandler, CostTracker
from ai_council_review.models import FileInfo, Finding, ReviewComment, ReviewState

logger = structlog.get_logger()


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


def router_node(state: ReviewState, config: CouncilConfig) -> dict[str, Any]:
    """Run the router agent to decide which agents are needed.

    Args:
        state: Current review state.
        config: Council configuration.

    Returns:
        Updates to the state with routing decision.
    """
    logger.info("Router node starting")

    if state.skipped:
        return {}

    if not state.changed_files:
        logger.info("No files to review")
        return {}

    result = run_router_agent(state, config)

    logger.info(
        "Router complete",
        agents=result.agents_needed,
        depth=result.review_depth,
    )

    return {
        "agents_needed": result.agents_needed,
        "review_depth": result.review_depth,
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
    handler = CostCallbackHandler(
        cost_tracker=cost_tracker,
        agent_name=agent_name,
        model_name=agent_config.model_name,
        max_tokens=agent_config.max_tokens,
    )
    return [handler]


def security_node(
    state: ReviewState,
    config: CouncilConfig,
    cost_tracker: CostTracker | None = None,
) -> dict[str, Any]:
    """Run the security agent.

    Args:
        state: Current review state.
        config: Council configuration.
        cost_tracker: Optional cost tracker for budget enforcement.

    Returns:
        Updates to the state.
    """
    if state.skipped:
        return {}

    browser = _get_browser()
    callbacks = _make_cost_callback(cost_tracker, "security", config)
    findings = run_security_agent(state, config, browser, callbacks=callbacks)
    return {
        "agent_outputs": {"security": findings},
    }


def quality_node(
    state: ReviewState,
    config: CouncilConfig,
    cost_tracker: CostTracker | None = None,
) -> dict[str, Any]:
    """Run the quality agent.

    Args:
        state: Current review state.
        config: Council configuration.
        cost_tracker: Optional cost tracker for budget enforcement.

    Returns:
        Updates to the state.
    """
    if state.skipped:
        return {}

    browser = _get_browser()
    callbacks = _make_cost_callback(cost_tracker, "quality", config)
    findings = run_quality_agent(state, config, browser, callbacks=callbacks)
    return {
        "agent_outputs": {"quality": findings},
    }


def architecture_node(
    state: ReviewState,
    config: CouncilConfig,
    cost_tracker: CostTracker | None = None,
) -> dict[str, Any]:
    """Run the architecture agent.

    Args:
        state: Current review state.
        config: Council configuration.
        cost_tracker: Optional cost tracker for budget enforcement.

    Returns:
        Updates to the state.
    """
    if state.skipped:
        return {}

    browser = _get_browser()
    callbacks = _make_cost_callback(cost_tracker, "architecture", config)
    findings = run_architecture_agent(state, config, browser, callbacks=callbacks)
    return {
        "agent_outputs": {"architecture": findings},
    }


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

    # Convert findings to ReviewComments
    comments: list[ReviewComment] = []
    for finding in all_findings:
        if finding.position is not None:
            comments.append(
                ReviewComment(
                    path=finding.path,
                    position=finding.position,
                    body=finding.body,
                )
            )

    # Validate comments against changed files
    comments = publisher.validate_comments(comments, state.changed_files)

    # Build summary from synthesis if available
    summary_text: str = state.summary or ""
    if not summary_text:
        summary_parts = ["## AI Code Review\n"]
        severity_counts: dict[str, int] = {}
        for finding in all_findings:
            severity_counts[finding.severity.value] = (
                severity_counts.get(finding.severity.value, 0) + 1
            )

        summary_parts.append("\n**Findings by severity:**\n")
        for severity, count in sorted(
            severity_counts.items(),
            key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(x[0], 5),
        ):
            summary_parts.append(f"- {severity.capitalize()}: {count}")

        summary_parts.append(f"\n**Total findings:** {len(all_findings)}")
        summary_parts.append(
            "\n---\n\n*This review was generated automatically. Please verify all suggestions before applying.*"
        )
        summary_text = "\n".join(summary_parts)

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


def _get_browser() -> RepositoryBrowser | None:
    """Create a RepositoryBrowser if GitHub token is available.

    Returns:
        RepositoryBrowser or None.
    """
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if token and repo:
        client = GitHubClient(token, repo)
        return RepositoryBrowser(github_client=client)
    return None


def _route_from_router(state: ReviewState) -> list[str]:
    """Determine which agents to run based on router output.

    Args:
        state: Current review state.

    Returns:
        List of agent node names to execute.
    """
    agents = getattr(state, "agents_needed", ["security", "quality", "architecture"])
    valid_agents = {"security", "quality", "architecture"}
    return [a for a in agents if a in valid_agents]


def build_graph(config: CouncilConfig) -> Any:
    """Build the LangGraph state machine with multi-agent routing.

    Args:
        config: Council configuration.

    Returns:
        Compiled StateGraph.
    """
    workflow = StateGraph(ReviewState)

    # Initialize cost tracker for the entire graph run
    cost_tracker = CostTracker(config)

    # Nodes
    workflow.add_node("ingest", lambda state: ingest_node(state, config))
    workflow.add_node("router", lambda state: router_node(state, config))
    workflow.add_node("security", lambda state: security_node(state, config, cost_tracker))
    workflow.add_node("quality", lambda state: quality_node(state, config, cost_tracker))
    workflow.add_node("architecture", lambda state: architecture_node(state, config, cost_tracker))
    workflow.add_node("synthesis_agent", lambda state: synthesis_node(state, config, cost_tracker))
    workflow.add_node("post", lambda state: post_node(state, config))

    # Edges
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "router")

    # Conditional routing from router
    # Run all agents in parallel. In the future, we could use Send() for
    # dynamic conditional routing based on the router output.
    workflow.add_conditional_edges(
        "router",
        lambda state: ["security", "quality", "architecture"],  # type: ignore[arg-type]
        ["security", "quality", "architecture"],
    )

    # Parallel agents converge to synthesis
    workflow.add_edge("security", "synthesis_agent")
    workflow.add_edge("quality", "synthesis_agent")
    workflow.add_edge("architecture", "synthesis_agent")

    # Synthesis -> post
    workflow.add_edge("synthesis_agent", "post")
    workflow.add_edge("post", END)

    return workflow.compile()
